#!/usr/bin/env python3
"""
Flowgraph Builder for gr-sleipnir Test Suite

Programmatically builds GNU Radio flowgraphs for testing.
"""

import logging
import numpy as np
import os
from gnuradio import gr, blocks, filter, analog, digital, fec
try:
    from gnuradio import channels
    HAS_CHANNELS = True
except ImportError:
    HAS_CHANNELS = False
    logger.warning("gnuradio.channels module not available - fading will use simplified model")
from gnuradio.gr import sizeof_gr_complex, sizeof_float
import pmt
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from python.sleipnir_tx_hier import make_sleipnir_tx_hier
from python.sleipnir_rx_hier import make_sleipnir_rx_hier

logger = logging.getLogger(__name__)


class ChannelModel:
    """Channel model for testing."""
    
    def __init__(self, channel_type: str, **kwargs):
        """
        Initialize channel model.
        
        Args:
            channel_type: Type of channel ("clean", "awgn", "fading", "freq_offset")
            **kwargs: Channel-specific parameters
        """
        self.channel_type = channel_type
        self.params = kwargs
    
    def add_to_flowgraph(self, tb: gr.top_block, input_port, output_port):
        """
        Add channel model to flowgraph.
        
        Args:
            tb: Top block
            input_port: Input port (complex)
            output_port: Output port (complex)
        """
        if self.channel_type == "clean":
            # Clean channel = AWGN only (no fading)
            # Still adds noise based on SNR, just no fading impairments
            snr_db = self.params.get('snr_db', 10.0)
            noise_voltage = 10.0 ** (-snr_db / 20.0)
            import random
            noise_seed = random.randint(0, 2**31 - 1)
            noise = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, noise_seed)
            add_noise = blocks.add_cc(1)
            tb.connect(input_port, add_noise)
            tb.connect(noise, (add_noise, 1))
            tb.connect(add_noise, output_port)
        
        elif self.channel_type == "awgn":
            # AWGN channel
            snr_db = self.params.get('snr_db', 10.0)
            noise_voltage = 10.0 ** (-snr_db / 20.0)
            # Use a seed that changes to avoid potential issues with noise source state
            import random
            noise_seed = random.randint(0, 2**31 - 1)
            noise = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, noise_seed)
            add_noise = blocks.add_cc(1)
            tb.connect(input_port, add_noise)
            tb.connect(noise, (add_noise, 1))
            tb.connect(add_noise, output_port)
        
        elif self.channel_type == "fading":
            # Fading channel - simplified implementation using multiplicative fading + AWGN
            # For proper fading, we'd need channels.channel_model, but for now use simplified model
            fading_type = self.params.get('fading_type', 'rayleigh')
            doppler_freq = self.params.get('doppler_freq', 1.0)
            snr_db = self.params.get('snr_db', 10.0)
            sample_rate = self.params.get('sample_rate', 48000.0)
            
            # Apply fading using multiplicative complex noise (simplified fading model)
            # This creates amplitude variations similar to fading
            import random
            noise_seed = random.randint(0, 2**31 - 1)
            
            if fading_type == "rayleigh":
                # Rayleigh fading: multiplicative complex Gaussian (no LOS)
                # Use low-pass filtered noise for realistic fading
                fading_amplitude = 0.3  # Fading depth
                fading_noise = analog.noise_source_c(analog.GR_GAUSSIAN, fading_amplitude, noise_seed + 1)
                # Low-pass filter for realistic fading (smooth variations)
                # Cutoff frequency based on doppler_freq
                cutoff_freq = min(doppler_freq * 2, sample_rate * 0.1)  # Limit to reasonable value
                fading_taps = filter.firdes.low_pass(
                    1.0, sample_rate, cutoff_freq, cutoff_freq * 0.5
                )
                fading_filter = filter.fir_filter_ccf(1, fading_taps)
                fading_mult = blocks.multiply_cc(1)
                # Create fading: 1.0 + filtered_noise (ensures positive real part)
                add_fading = blocks.add_cc(1)
                const_one = analog.sig_source_c(sample_rate, analog.GR_CONST_WAVE, 0.0, 1.0, 0.0)
                tb.connect(const_one, (add_fading, 0))
                tb.connect(fading_noise, fading_filter, (add_fading, 1))
                tb.connect(input_port, (fading_mult, 0))
                tb.connect(add_fading, (fading_mult, 1))
                current_output = fading_mult
            elif fading_type == "rician":
                # Rician fading: LOS component + scattered (Rayleigh) component
                k_factor = self.params.get('k_factor', 3.0)
                # LOS component (constant)
                los_amplitude = np.sqrt(k_factor / (k_factor + 1.0))
                los_source = analog.sig_source_c(sample_rate, analog.GR_CONST_WAVE, 0.0, los_amplitude, 0.0)
                # Scattered component (Rayleigh-like)
                scattered_amplitude = np.sqrt(1.0 / (k_factor + 1.0)) * 0.3
                scattered_noise = analog.noise_source_c(analog.GR_GAUSSIAN, scattered_amplitude, noise_seed + 1)
                cutoff_freq = min(doppler_freq * 2, sample_rate * 0.1)
                scattered_taps = filter.firdes.low_pass(
                    1.0, sample_rate, cutoff_freq, cutoff_freq * 0.5
                )
                scattered_filter = filter.fir_filter_ccf(1, scattered_taps)
                # Combine LOS + scattered
                add_fading = blocks.add_cc(1)
                tb.connect(los_source, (add_fading, 0))
                tb.connect(scattered_noise, scattered_filter, (add_fading, 1))
                # Apply to signal
                fading_mult = blocks.multiply_cc(1)
                tb.connect(input_port, (fading_mult, 0))
                tb.connect(add_fading, (fading_mult, 1))
                current_output = fading_mult
            else:
                # Unknown fading - just use AWGN with penalty
                current_output = input_port
                effective_snr_db = snr_db - 4.0
                noise_voltage = 10.0 ** (-effective_snr_db / 20.0)
                noise = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, noise_seed)
                add_noise = blocks.add_cc(1)
                tb.connect(current_output, add_noise)
                tb.connect(noise, (add_noise, 1))
                tb.connect(add_noise, output_port)
                logger.warning(f"Unknown fading type: {fading_type}, using AWGN with penalty")
                return
            
            # Add AWGN after fading (with SNR penalty for fading)
            # Apply fading penalty to effective SNR
            if fading_type == "rayleigh":
                effective_snr_db = snr_db - 4.0  # ~4 dB penalty
            elif fading_type == "rician":
                k_factor = self.params.get('k_factor', 3.0)
                rician_penalty = 3.0 - (k_factor - 1.0) * 0.2
                effective_snr_db = snr_db - rician_penalty
            else:
                effective_snr_db = snr_db - 4.0
            
            noise_voltage = 10.0 ** (-effective_snr_db / 20.0)
            noise = analog.noise_source_c(analog.GR_GAUSSIAN, noise_voltage, noise_seed)
            add_noise = blocks.add_cc(1)
            tb.connect(current_output, (add_noise, 0))
            tb.connect(noise, (add_noise, 1))
            tb.connect(add_noise, output_port)
        
        elif self.channel_type == "freq_offset":
            # Frequency offset using analog.sig_source_c
            offset_hz = self.params.get('offset_hz', 100.0)
            sample_rate = self.params.get('sample_rate', 48000.0)
            
            # Create complex exponential signal for frequency offset
            freq_shift = analog.sig_source_c(
                sample_rate,
                analog.GR_SIN_WAVE,
                offset_hz,
                1.0,
                0.0
            )
            multiply = blocks.multiply_cc(1)
            tb.connect(input_port, multiply)
            tb.connect(freq_shift, (multiply, 1))
            tb.connect(multiply, output_port)
        
        else:
            logger.warning(f"Unknown channel type: {self.channel_type}, using clean channel")
            tb.connect(input_port, output_port)


def build_test_flowgraph(
    input_wav: str,
    output_wav: str,
    modulation: int = 4,
    crypto_mode: str = "none",
    channel: dict = None,
    snr_db: float = 10.0,
    audio_samp_rate: float = 48000.0,
    rf_samp_rate: float = 48000.0,
    symbol_rate: float = 4800.0,
    fsk_deviation: float = 2400.0,
    auth_matrix_file: str = None,
    voice_matrix_file: str = None,
    private_key_path: str = None,
    mac_key: bytes = None,
    test_duration: float = 5.0
) -> gr.top_block:
    """
    Build test flowgraph.
    
    Args:
        input_wav: Input WAV file path
        output_wav: Output WAV file path
        modulation: FSK levels (4 or 8)
        crypto_mode: Crypto mode ("none", "sign", "encrypt", "both")
        channel: Channel configuration dict
        snr_db: SNR in dB
        audio_samp_rate: Audio sample rate (Hz)
        rf_samp_rate: RF sample rate (Hz)
        symbol_rate: Symbol rate (symbols/sec)
        fsk_deviation: FSK deviation (Hz)
        auth_matrix_file: Auth LDPC matrix file path
        voice_matrix_file: Voice LDPC matrix file path
        private_key_path: Private key file path
        mac_key: MAC key bytes
        test_duration: Test duration (seconds)
        
    Returns:
        Configured top block
    """
    tb = gr.top_block()
    
    # Determine crypto settings
    enable_signing = crypto_mode in ["sign", "both"]
    enable_encryption = crypto_mode in ["encrypt", "both"]
    
    # Provide keys if crypto is enabled
    if enable_signing or enable_encryption:
        if private_key_path is None:
            # Use test keys if available
            test_key_path = "tests/test_keys/private.pem"
            if os.path.exists(test_key_path):
                private_key_path = test_key_path
            else:
                logger.warning(f"Crypto enabled but no private key provided and test keys not found at {test_key_path}")
        
        if enable_encryption and mac_key is None:
            # Generate a test MAC key (32 bytes)
            import secrets
            mac_key = secrets.token_bytes(32)
            logger.info("Generated test MAC key for encryption")
    
    # Determine FEC matrix files
    if auth_matrix_file is None:
        auth_matrix_file = "ldpc_matrices/ldpc_auth_1536_512.alist"
    if voice_matrix_file is None:
        # Use ldpc_voice_576_384.alist for both 4FSK and 8FSK (rate 2/3, 384 bits -> 576 bits)
        # This matches the superframe structure where voice frames are 48 bytes (384 bits)
        voice_matrix_file = "ldpc_matrices/ldpc_voice_576_384.alist"
    
    # 1. WAV file source
    wav_source = blocks.wavfile_source(input_wav, False)
    
    # Limit duration if needed
    max_samples = int(audio_samp_rate * test_duration)
    head_block = blocks.head(sizeof_float, max_samples)
    
    # 2. TX hierarchical block
    tx_block = make_sleipnir_tx_hier(
        callsign="TEST1",
        audio_samp_rate=audio_samp_rate,
        rf_samp_rate=rf_samp_rate,
        symbol_rate=symbol_rate,
        fsk_deviation=fsk_deviation,
        fsk_levels=modulation,
        auth_matrix_file=auth_matrix_file,
        voice_matrix_file=voice_matrix_file,
        enable_signing=enable_signing,
        enable_encryption=enable_encryption,
        private_key_path=private_key_path,
        mac_key=mac_key
    )
    
    # 3. Channel model
    if channel is None:
        channel = {"type": "awgn"}
    
    channel_model = ChannelModel(
        channel_type=channel.get("type", "awgn"),
        snr_db=snr_db,
        sample_rate=rf_samp_rate,  # Add sample_rate for fading channels
        **{k: v for k, v in channel.items() if k not in ["type", "snr_db"]}
    )
    
    # 4. RX hierarchical block
    # Provide public key store path if signing is enabled
    public_key_store_path = None
    if enable_signing:
        test_key_store = "tests/test_keys/public_key_store"
        if os.path.exists(test_key_store):
            public_key_store_path = test_key_store
        else:
            logger.warning(f"Signing enabled but public key store not found at {test_key_store}")
    
    rx_block = make_sleipnir_rx_hier(
        local_callsign="TEST1",
        audio_samp_rate=audio_samp_rate,
        rf_samp_rate=rf_samp_rate,
        symbol_rate=symbol_rate,
        fsk_deviation=fsk_deviation,
        fsk_levels=modulation,
        auth_matrix_file=auth_matrix_file,
        voice_matrix_file=voice_matrix_file,
        private_key_path=private_key_path,
        require_signatures=enable_signing,
        public_key_store_path=public_key_store_path
    )
    
    # 4.5. Metrics collector block (passes through audio, collects status messages)
    from metrics_collector import MetricsCollectorBlock
    metrics_block = MetricsCollectorBlock()
    
    # 5. WAV file sink
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_wav) if os.path.dirname(output_wav) else '.', exist_ok=True)
    
    # wavfile_sink requires format and subformat parameters
    # Use enum values: FORMAT_WAV (3) and FORMAT_PCM_16 (1)
    from gnuradio.blocks import wavfile_format_t, wavfile_subformat_t
    wav_sink = blocks.wavfile_sink(
        output_wav,
        1,  # 1 channel (mono)
        int(audio_samp_rate),
        wavfile_format_t.FORMAT_WAV,  # WAV format
        wavfile_subformat_t.FORMAT_PCM_16,  # 16-bit PCM
        False  # append
    )
    
    # Connect flowgraph
    tb.connect(wav_source, head_block, tx_block)
    
    # Add channel model between TX and RX
    channel_model.add_to_flowgraph(tb, tx_block, rx_block)
    
    # 4.5. Metrics collector block (passes through audio, collects status messages)
    from metrics_collector import MetricsCollectorBlock
    metrics_block = MetricsCollectorBlock()
    
    # Connect RX audio output to metrics block, then to WAV sink
    tb.connect(rx_block, metrics_block, wav_sink)
    
    # Connect RX status messages to metrics block
    tb.msg_connect(rx_block, "status", metrics_block, "status")
    
    # Store metrics block reference in top block for later access
    tb._metrics_block = metrics_block
    
    # Store references to hierarchical blocks for explicit cleanup
    tb._tx_block = tx_block
    tb._rx_block = rx_block
    
    return tb

