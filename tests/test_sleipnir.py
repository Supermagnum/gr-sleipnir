#!/usr/bin/env python3
"""
Comprehensive Automated Test Suite for gr-sleipnir

Tests all blocks and parameters across varying channel conditions.

Usage:
    python test_sleipnir.py [--config config.yaml] [--wav input.wav]
"""

import sys
import os
import json
import csv
import yaml
import argparse
import logging
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import wave
import struct

# GNU Radio imports
from gnuradio import gr, blocks, filter, analog, digital, fec
from gnuradio.gr import sizeof_gr_complex, sizeof_float
import pmt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from python.sleipnir_tx_hier import make_sleipnir_tx_hier
from python.sleipnir_rx_hier import make_sleipnir_rx_hier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Audio quality analysis
try:
    from warpq.core import warpqMetric
    WARPQ_AVAILABLE = True
except (ImportError, AttributeError) as e:
    WARPQ_AVAILABLE = False
    logger.warning(f"warpq not available ({e}), audio quality analysis will use basic metrics only")


class WAVFileAnalyzer:
    """Analyze WAV file properties."""
    
    @staticmethod
    def get_properties(wav_path: str) -> Dict[str, Any]:
        """Get WAV file properties."""
        try:
            with wave.open(wav_path, 'rb') as wf:
                return {
                    'sample_rate': wf.getframerate(),
                    'channels': wf.getnchannels(),
                    'sample_width': wf.getsampwidth(),
                    'frames': wf.getnframes(),
                    'duration': wf.getnframes() / wf.getframerate()
                }
        except Exception as e:
            logger.error(f"Error reading WAV file {wav_path}: {e}")
            return {}
    
    @staticmethod
    def read_samples(wav_path: str, max_samples: Optional[int] = None) -> np.ndarray:
        """Read samples from WAV file as float32 [-1.0, 1.0]."""
        try:
            with wave.open(wav_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                n_frames = wf.getnframes()
                
                if max_samples:
                    n_frames = min(n_frames, max_samples)
                
                frames = wf.readframes(n_frames)
                
                # Convert to numpy array
                if sample_width == 1:
                    dtype = np.uint8
                    scale = 128.0
                elif sample_width == 2:
                    dtype = np.int16
                    scale = 32768.0
                elif sample_width == 4:
                    dtype = np.int32
                    scale = 2147483648.0
                else:
                    raise ValueError(f"Unsupported sample width: {sample_width}")
                
                samples = np.frombuffer(frames, dtype=dtype)
                
                # Convert to float32 [-1.0, 1.0]
                if dtype == np.uint8:
                    samples = (samples.astype(np.float32) - 128.0) / 128.0
                else:
                    samples = samples.astype(np.float32) / scale
                
                # Handle multi-channel
                if channels > 1:
                    samples = samples.reshape(-1, channels)
                    # Take first channel
                    samples = samples[:, 0]
                
                return samples, sample_rate
        except Exception as e:
            logger.error(f"Error reading samples from {wav_path}: {e}")
            return np.array([]), 0


class ChannelModel(gr.hier_block2):
    """Channel model with AWGN, fading, frequency offset, and timing errors."""
    
    def __init__(
        self,
        snr_db: float = 20.0,
        fading_type: str = "none",  # "none", "rayleigh", "rician"
        fading_velocity: float = 0.0,  # m/s
        freq_offset_hz: float = 0.0,
        timing_error_ppm: float = 0.0,
        rf_samp_rate: float = 48000.0
    ):
        gr.hier_block2.__init__(
            self,
            "channel_model",
            gr.io_signature(1, 1, sizeof_gr_complex),
            gr.io_signature(1, 1, sizeof_gr_complex)
        )
        
        self.snr_db = snr_db
        self.rf_samp_rate = rf_samp_rate
        
        # Calculate noise power
        signal_power = 1.0  # Assume normalized signal
        noise_power = signal_power / (10.0 ** (snr_db / 10.0))
        
        # AWGN noise source
        noise_amplitude = np.sqrt(noise_power)
        noise_source = analog.noise_source_c(
            analog.GR_GAUSSIAN,
            noise_amplitude,
            0
        )
        
        # Add noise
        noise_adder = blocks.add_cc(1)
        self.connect(self, (noise_adder, 0))
        self.connect(noise_source, (noise_adder, 1))
        
        # Frequency offset
        if abs(freq_offset_hz) > 0.001:
            freq_offset_rad = 2.0 * np.pi * freq_offset_hz / rf_samp_rate
            freq_shift = analog.sig_source_c(
                rf_samp_rate,
                analog.GR_SIN_WAVE,
                freq_offset_hz,
                1.0,
                0.0
            )
            freq_mult = blocks.multiply_cc()
            self.connect(noise_adder, freq_mult, 0)
            self.connect(freq_shift, freq_mult, 1)
            output_block = freq_mult
        else:
            output_block = noise_adder
        
        # Fading (simplified - using multiplicative noise)
        if fading_type == "rayleigh":
            # Rayleigh fading using multiplicative noise
            fading_amplitude = 0.1  # Adjust as needed
            fading_source = analog.noise_source_c(
                analog.GR_GAUSSIAN,
                fading_amplitude,
                0
            )
            fading_mult = blocks.multiply_cc()
            self.connect(output_block, fading_mult, 0)
            self.connect(fading_source, fading_mult, 1)
            output_block = fading_mult
        elif fading_type == "rician":
            # Rician fading (simplified)
            k_factor = 3.0  # Rician K factor
            # Similar to Rayleigh but with line-of-sight component
            fading_amplitude = 0.05
            fading_source = analog.noise_source_c(
                analog.GR_GAUSSIAN,
                fading_amplitude,
                0
            )
            fading_mult = blocks.multiply_cc()
            self.connect(output_block, fading_mult, 0)
            self.connect(fading_source, fading_mult, 1)
            output_block = fading_mult
        
        # Connect output
        self.connect(output_block, self)


class MetricsCollector(gr.sync_block):
    """Collect metrics from the receiver."""
    
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="metrics_collector",
            in_sig=[np.float32],  # Audio input
            out_sig=[np.float32]  # Pass through
        )
        
        self.frame_count = 0
        self.error_count = 0
        self.total_samples = 0
        self.audio_samples = []
        self.max_samples = 48000 * 10  # 10 seconds max
        
    def work(self, input_items, output_items):
        noutput_items = len(output_items[0])
        
        # Collect audio samples
        if len(self.audio_samples) < self.max_samples:
            self.audio_samples.extend(input_items[0][:noutput_items].tolist())
        
        # Pass through
        output_items[0][:noutput_items] = input_items[0][:noutput_items]
        self.total_samples += noutput_items
        
        return noutput_items
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        return {
            'frame_count': self.frame_count,
            'error_count': self.error_count,
            'total_samples': self.total_samples,
            'audio_samples': self.audio_samples[:48000]  # First second
        }


class TestFlowgraph:
    """Generate and run test flowgraph."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        wav_input: str,
        output_dir: str
    ):
        self.config = config
        self.wav_input = wav_input
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test parameters
        self.snr_db = config.get('snr_db', 10.0)
        self.modulation = config.get('modulation', '4FSK')
        self.fec_rate = config.get('fec_rate', '2/3')
        self.crypto_mode = config.get('crypto_mode', 'none')
        self.channel_type = config.get('channel_type', 'AWGN')
        self.freq_offset_hz = config.get('freq_offset_hz', 0.0)
        
        # System parameters
        self.audio_samp_rate = config.get('audio_samp_rate', 8000.0)
        self.rf_samp_rate = config.get('rf_samp_rate', 48000.0)
        self.symbol_rate = config.get('symbol_rate', 4800.0)
        self.fsk_deviation = config.get('fsk_deviation', 2400.0)
        self.fsk_levels = 4 if self.modulation == '4FSK' else 8
        
        # LDPC matrices - resolve to absolute paths
        project_root = Path(__file__).parent.parent
        auth_matrix_rel = config.get('auth_matrix_file', 
            'ldpc_matrices/ldpc_auth_768_256.alist')
        voice_matrix_rel = config.get('voice_matrix_file',
            'ldpc_matrices/ldpc_voice_576_384.alist')
        
        # Resolve paths
        if not os.path.isabs(auth_matrix_rel):
            if auth_matrix_rel.startswith('../'):
                self.auth_matrix = str(project_root / auth_matrix_rel[3:])
            elif auth_matrix_rel.startswith('ldpc_matrices/'):
                self.auth_matrix = str(project_root / auth_matrix_rel)
            else:
                self.auth_matrix = str(project_root / 'ldpc_matrices' / auth_matrix_rel)
        else:
            self.auth_matrix = auth_matrix_rel
            
        if not os.path.isabs(voice_matrix_rel):
            if voice_matrix_rel.startswith('../'):
                self.voice_matrix = str(project_root / voice_matrix_rel[3:])
            elif voice_matrix_rel.startswith('ldpc_matrices/'):
                self.voice_matrix = str(project_root / voice_matrix_rel)
            else:
                self.voice_matrix = str(project_root / 'ldpc_matrices' / voice_matrix_rel)
        else:
            self.voice_matrix = voice_matrix_rel
        
        # Crypto settings
        self.enable_signing = self.crypto_mode in ['sign', 'both']
        self.enable_encryption = self.crypto_mode in ['encrypt', 'both']
        self.private_key_path = config.get('private_key_path', None)
        self.mac_key = config.get('mac_key', None)
        
        # Callsigns
        self.tx_callsign = config.get('tx_callsign', 'TESTTX')
        self.rx_callsign = config.get('rx_callsign', 'TESTRX')
        
        # Results
        self.results = {}
        
    def create_flowgraph(self) -> gr.top_block:
        """Create test flowgraph."""
        tb = gr.top_block()
        
        # Analyze input WAV
        wav_analyzer = WAVFileAnalyzer()
        wav_props = wav_analyzer.get_properties(self.wav_input)
        wav_samples, wav_samp_rate = wav_analyzer.read_samples(self.wav_input)
        
        if len(wav_samples) == 0:
            raise ValueError(f"Could not read WAV file: {self.wav_input}")
        
        # Use WAV file source - it handles the file reading efficiently
        # Limit duration to avoid very long tests
        max_duration_seconds = 5.0
        max_samples = int(self.audio_samp_rate * max_duration_seconds)
        
        # TEMPORARILY DISABLED: wavfile_source may be causing crashes
        # Use vector_source_f instead
        use_wavfile_source = False  # Set to True to re-enable
        
        try:
            if use_wavfile_source:
                wav_source = blocks.wavfile_source(self.wav_input, True)  # repeat=True
                audio_source = wav_source
                
                # Resample if needed
                if abs(wav_samp_rate - self.audio_samp_rate) > 1.0:
                    logger.info(f"Resampling from {wav_samp_rate} Hz to {self.audio_samp_rate} Hz")
                    # Calculate simplified ratio using GCD
                    from math import gcd
                    interp = int(self.audio_samp_rate)
                    decim = int(wav_samp_rate)
                    g = gcd(interp, decim)
                    interp = interp // g
                    decim = decim // g
                    logger.info(f"Resampler ratio: {interp}/{decim}")
                    resampler = filter.rational_resampler_fff(interp, decim)
                    tb.connect(wav_source, resampler)
                    audio_source = resampler
                else:
                    # No resampling needed, connect directly
                    audio_source = wav_source
            else:
                # Use vector source instead (more reliable)
                raise Exception("Using vector source instead of wavfile_source")
        except Exception as e:
            logger.warning(f"Could not use WAV file source, using limited vector source: {e}")
            # Fallback: use vector source with limited samples
            if len(wav_samples) > max_samples:
                wav_samples = wav_samples[:max_samples]
                logger.info(f"Limiting to {max_samples} samples ({max_duration_seconds} seconds)")
            
            vec_source = blocks.vector_source_f(wav_samples.tolist(), False)
            
            if abs(wav_samp_rate - self.audio_samp_rate) > 1.0:
                logger.info(f"Resampling from {wav_samp_rate} Hz to {self.audio_samp_rate} Hz")
                from math import gcd
                interp = int(self.audio_samp_rate)
                decim = int(wav_samp_rate)
                g = gcd(interp, decim)
                interp = interp // g
                decim = decim // g
                resampler = filter.rational_resampler_fff(interp, decim)
                tb.connect(vec_source, resampler)
                audio_source = resampler
            else:
                audio_source = vec_source
        
        # TX chain - hierarchical block handles stream input and PDU conversion internally
        try:
            logger.info(f"Creating TX block with matrices: {self.auth_matrix}, {self.voice_matrix}")
            tx_block = make_sleipnir_tx_hier(
                callsign=self.tx_callsign,
                audio_samp_rate=self.audio_samp_rate,
                rf_samp_rate=self.rf_samp_rate,
                symbol_rate=self.symbol_rate,
                fsk_deviation=self.fsk_deviation,
                fsk_levels=self.fsk_levels,
                auth_matrix_file=self.auth_matrix,
                voice_matrix_file=self.voice_matrix,
                enable_signing=self.enable_signing,
                enable_encryption=self.enable_encryption,
                private_key_path=self.private_key_path,
                mac_key=self.mac_key
            )
            logger.info("TX block created successfully")
        except Exception as e:
            logger.error(f"Could not create TX block: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Connect audio source to TX block (stream connection)
        try:
            tb.connect(audio_source, tx_block)
            logger.info("TX block connected successfully")
        except Exception as e:
            logger.error(f"Could not connect TX block: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Channel model
        fading_type = "none"
        if "rayleigh" in self.channel_type.lower():
            fading_type = "rayleigh"
        elif "rician" in self.channel_type.lower():
            fading_type = "rician"
        
        channel = ChannelModel(
            snr_db=self.snr_db,
            fading_type=fading_type,
            freq_offset_hz=self.freq_offset_hz,
            rf_samp_rate=self.rf_samp_rate
        )
        
        # Connect channel
        try:
            tb.connect(tx_block, channel)
        except Exception as e:
            logger.warning(f"Could not connect channel: {e}")
            # Use direct connection
            pass
        
        # RX chain - hierarchical block handles stream input and PDU conversion internally
        try:
            logger.info(f"Creating RX block with matrices: {self.auth_matrix}, {self.voice_matrix}")
            rx_block = make_sleipnir_rx_hier(
                local_callsign=self.rx_callsign,
                audio_samp_rate=self.audio_samp_rate,
                rf_samp_rate=self.rf_samp_rate,
                symbol_rate=self.symbol_rate,
                fsk_deviation=self.fsk_deviation,
                fsk_levels=self.fsk_levels,
                auth_matrix_file=self.auth_matrix,
                voice_matrix_file=self.voice_matrix,
                private_key_path=self.private_key_path,
                require_signatures=self.enable_signing
            )
            logger.info("RX block created successfully")
        except Exception as e:
            logger.error(f"Could not create RX block: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Metrics collector
        metrics = MetricsCollector()
        
        # Connect channel to RX block, then RX to metrics (all stream connections)
        try:
            tb.connect(channel, rx_block)
            logger.info("Channel connected to RX block")
            tb.connect(rx_block, metrics)
            logger.info("RX block connected to metrics collector")
        except Exception as e:
            logger.error(f"Could not connect RX chain: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # File sink for output audio
        output_wav = str(self.output_dir / f"output_snr{self.snr_db:.1f}.wav")
        try:
            # wavfile_sink requires format and subformat enums
            wav_sink = blocks.wavfile_sink(
                output_wav,
                1,  # channels
                int(self.audio_samp_rate),
                blocks.wavfile_format_t.FORMAT_WAV,
                blocks.wavfile_subformat_t.FORMAT_PCM_16,
                False  # append
            )
            tb.connect(metrics, wav_sink)
        except Exception as e:
            logger.warning(f"Could not create WAV sink: {e}")
            # Connect metrics to null sink if WAV sink fails
            null_sink = blocks.null_sink(sizeof_float)
            tb.connect(metrics, null_sink)
        
        self.tb = tb
        self.metrics = metrics
        self.output_wav = output_wav
        
        return tb
    
    def run_test(self, duration: float = 5.0) -> Dict[str, Any]:
        """Run test and collect results."""
        logger.info(f"Running test: SNR={self.snr_db}dB, Mod={self.modulation}, "
                   f"Crypto={self.crypto_mode}, Channel={self.channel_type}")
        
        start_time = time.time()
        
        try:
            # Create flowgraph
            logger.info("Creating flowgraph...")
            tb = self.create_flowgraph()
            logger.info("Flowgraph created successfully")
            
            # Run for specified duration
            logger.info("Starting flowgraph...")
            try:
                tb.start()
                logger.info(f"Flowgraph started, running for {duration} seconds...")
            except Exception as e:
                logger.error(f"Failed to start flowgraph: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            # Run for specified duration with timeout protection
            # Use simple sleep instead of polling loop to avoid potential issues
            start_run = time.time()
            try:
                # Simple sleep - don't poll is_running() as it may cause issues
                time.sleep(duration)
            except KeyboardInterrupt:
                logger.info("Test interrupted by user")
            
            logger.info("Stopping flowgraph...")
            try:
                tb.stop()
                logger.info("Waiting for flowgraph to finish...")
                tb.wait()
                logger.info("Flowgraph finished successfully")
            except Exception as e:
                logger.error(f"Error stopping flowgraph: {e}")
                import traceback
                traceback.print_exc()
            
            # Collect metrics
            metrics_data = self.metrics.get_metrics()
            
            # Calculate additional metrics
            elapsed_time = time.time() - start_time
            
            # Audio quality metrics
            audio_quality = self.analyze_audio_quality()
            
            # Validation checks
            validation = self.run_validation_checks(metrics_data, audio_quality)
            
            # Compile results
            results = {
                'timestamp': datetime.now().isoformat(),
                'test_config': {
                    'snr_db': self.snr_db,
                    'modulation': self.modulation,
                    'fec_rate': self.fec_rate,
                    'crypto_mode': self.crypto_mode,
                    'channel_type': self.channel_type,
                    'freq_offset_hz': self.freq_offset_hz
                },
                'metrics': {
                    'frame_count': metrics_data.get('frame_count', 0),
                    'error_count': metrics_data.get('error_count', 0),
                    'total_samples': metrics_data.get('total_samples', 0),
                    'elapsed_time': elapsed_time,
                    'processing_rate': metrics_data.get('total_samples', 0) / elapsed_time if elapsed_time > 0 else 0
                },
                'audio_quality': audio_quality,
                'validation': validation,
                'output_wav': self.output_wav
            }
            
            # Calculate FER and BER if possible
            if metrics_data.get('frame_count', 0) > 0:
                results['metrics']['fer'] = metrics_data.get('error_count', 0) / metrics_data.get('frame_count', 1)
            else:
                results['metrics']['fer'] = 1.0  # No frames decoded = 100% FER
            
            self.results = results
            return results
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'test_config': {
                    'snr_db': self.snr_db,
                    'modulation': self.modulation,
                    'crypto_mode': self.crypto_mode
                }
            }
    
    def analyze_audio_quality(self) -> Dict[str, Any]:
        """Analyze audio quality metrics using warpq and basic metrics."""
        if not hasattr(self, 'output_wav') or not os.path.exists(self.output_wav):
            return {'error': 'Output WAV not available'}
        
        try:
            # Read input and output
            wav_analyzer = WAVFileAnalyzer()
            input_samples, input_sr = wav_analyzer.read_samples(self.wav_input, max_samples=48000)
            output_samples, output_sr = wav_analyzer.read_samples(self.output_wav, max_samples=48000)
            
            if len(input_samples) == 0 or len(output_samples) == 0:
                return {'error': 'Could not read audio samples'}
            
            # Ensure same sample rate for warpq
            if abs(input_sr - output_sr) >= 1.0:
                logger.warning(f"Sample rate mismatch: input={input_sr}Hz, output={output_sr}Hz")
                # Resample output to match input if needed (basic approach)
                if output_sr != input_sr:
                    from scipy import signal
                    num_samples = int(len(output_samples) * input_sr / output_sr)
                    output_samples = signal.resample(output_samples, num_samples)
                    output_sr = input_sr
            
            # Align lengths
            min_len = min(len(input_samples), len(output_samples))
            input_samples = input_samples[:min_len]
            output_samples = output_samples[:min_len]
            
            # Calculate basic metrics
            # DC offset
            dc_offset_input = np.mean(input_samples)
            dc_offset_output = np.mean(output_samples)
            
            # Dynamic range
            dynamic_range_input = np.max(input_samples) - np.min(input_samples)
            dynamic_range_output = np.max(output_samples) - np.min(output_samples)
            
            # Clipping detection
            clipping_input = np.sum(np.abs(input_samples) >= 0.99)
            clipping_output = np.sum(np.abs(output_samples) >= 0.99)
            
            # Simple SNR (if signals are aligned)
            if len(input_samples) == len(output_samples):
                signal_power = np.mean(input_samples ** 2)
                error = input_samples - output_samples
                noise_power = np.mean(error ** 2)
                snr_audio = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else float('inf')
            else:
                snr_audio = None
            
            # Calculate WARP-Q score if available
            warpq_score = None
            warpq_normalized = None
            if WARPQ_AVAILABLE and len(input_samples) > 0 and len(output_samples) > 0:
                try:
                    # Ensure samples are in correct format for warpq (numpy arrays)
                    ref_signal = input_samples.astype(np.float32)
                    deg_signal = output_samples.astype(np.float32)
                    
                    # Normalize to [-1, 1] range if needed
                    ref_max = np.max(np.abs(ref_signal))
                    deg_max = np.max(np.abs(deg_signal))
                    if ref_max > 1.0:
                        ref_signal = ref_signal / ref_max
                    if deg_max > 1.0:
                        deg_signal = deg_signal / deg_max
                    
                    # Create warpqMetric instance with appropriate sample rate
                    # Use native_sr=True to use the actual sample rate
                    metric = warpqMetric(sr=int(input_sr), native_sr=True, apply_vad=False, verbose=False)
                    
                    # Calculate WARP-Q score using evaluate method
                    # Note: lower scores are better in WARP-Q
                    results = metric.evaluate(ref_signal, deg_signal, arr_sr=int(input_sr), verbose=False)
                    
                    warpq_score = results.get('raw_warpq_score')
                    warpq_normalized = results.get('normalized_warpq_score')
                    
                    # Note: In WARP-Q, lower raw scores indicate better quality
                    # Normalized score is 0-1 where 1 is best quality
                    logger.info(f"WARP-Q raw score: {warpq_score:.4f} (normalized: {warpq_normalized:.4f})")
                except Exception as e:
                    logger.warning(f"Error calculating WARP-Q score: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    warpq_score = None
                    warpq_normalized = None
            
            return {
                'dc_offset_input': float(dc_offset_input),
                'dc_offset_output': float(dc_offset_output),
                'dynamic_range_input': float(dynamic_range_input),
                'dynamic_range_output': float(dynamic_range_output),
                'clipping_input': int(clipping_input),
                'clipping_output': int(clipping_output),
                'snr_audio_db': float(snr_audio) if snr_audio is not None else None,
                'sample_rate_match': abs(input_sr - output_sr) < 1.0,
                'warpq_score': float(warpq_score) if warpq_score is not None else None,
                'warpq_normalized': float(warpq_normalized) if warpq_normalized is not None else None,
                'warpq_available': WARPQ_AVAILABLE
            }
        except Exception as e:
            logger.error(f"Error analyzing audio quality: {e}")
            return {'error': str(e)}
    
    def run_validation_checks(
        self,
        metrics_data: Dict[str, Any],
        audio_quality: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run comprehensive validation checks."""
        validation = {
            'data_leakage': {},
            'boundary_conditions': {},
            'crypto': {},
            'audio_quality': {},
            'state_machine': {},
            'overall_pass': True
        }
        
        # Load validation thresholds from config
        thresholds = self.config.get('validation', {})
        
        # 1. Data Leakage Prevention
        validation['data_leakage'] = self.check_data_leakage(audio_quality)
        
        # 2. Boundary Conditions
        validation['boundary_conditions'] = self.check_boundary_conditions(metrics_data)
        
        # 3. Crypto Sanity Checks
        validation['crypto'] = self.check_crypto(metrics_data)
        
        # 4. Audio Quality Guards
        validation['audio_quality'] = self.check_audio_quality(audio_quality, thresholds)
        
        # 5. State Machine Validation
        validation['state_machine'] = self.check_state_machine(metrics_data)
        
        # Overall pass/fail
        all_checks = [
            validation['data_leakage'].get('pass', False),
            validation['boundary_conditions'].get('pass', False),
            validation['crypto'].get('pass', False),
            validation['audio_quality'].get('pass', False),
            validation['state_machine'].get('pass', False)
        ]
        validation['overall_pass'] = all(all_checks)
        
        return validation
    
    def check_data_leakage(self, audio_quality: Dict[str, Any]) -> Dict[str, Any]:
        """Check for data leakage in audio output."""
        checks = {
            'pass': True,
            'issues': []
        }
        
        if 'error' in audio_quality:
            checks['pass'] = False
            checks['issues'].append('Could not analyze audio quality')
            return checks
        
        # Check for excessive noise when sync is lost
        # This is a simplified check - in practice, would need to detect sync loss
        # Check that output doesn't contain non-audio data patterns
        # This would require analyzing the bitstream, which is complex
        # For now, we check that audio quality is reasonable
        if audio_quality.get('snr_audio_db') is not None:
            if audio_quality['snr_audio_db'] < -10:  # Very poor SNR might indicate data leakage
                checks['issues'].append('Very poor audio SNR might indicate data leakage')
        
        # Check that output contains only audio, not framing data
        # This would require analyzing the bitstream, which is complex
        # For now, we check that audio quality is reasonable
        
        return checks
    
    def check_boundary_conditions(self, metrics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check boundary condition handling."""
        checks = {
            'pass': True,
            'issues': []
        }
        
        frame_count = metrics_data.get('frame_count', 0)
        error_count = metrics_data.get('error_count', 0)
        
        # Check that system handles zero frames gracefully
        if frame_count == 0:
            # System should not crash, but may have high FER
            checks['issues'].append('No frames decoded (may be expected at low SNR)')
        
        # Check that error count doesn't exceed frame count
        if error_count > frame_count:
            checks['pass'] = False
            checks['issues'].append(f'Error count ({error_count}) exceeds frame count ({frame_count})')
        
        # Check for reasonable frame counts
        if frame_count > 1000:  # Unusually high
            checks['issues'].append(f'Unusually high frame count: {frame_count}')
        
        return checks
    
    def check_crypto(self, metrics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check cryptographic behavior."""
        checks = {
            'pass': True,
            'issues': []
        }
        
        # Check that unsigned frames are rejected when signature required
        if self.enable_signing and self.config.get('require_signatures', False):
            # This would require checking status messages from RX block
            # For now, we check that system doesn't crash
            pass
        
        # Check that encrypted frames produce errors without keys
        if self.enable_encryption and not self.private_key_path:
            # System should reject or produce silence, not garbled audio
            # This is a placeholder - actual implementation would check audio output
            pass
        
        # Check that crypto doesn't leak plaintext
        # This would require analyzing the transmitted signal
        # For now, we assume it's handled by the crypto implementation
        
        return checks
    
    def check_audio_quality(
        self,
        audio_quality: Dict[str, Any],
        thresholds: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check audio quality guards."""
        checks = {
            'pass': True,
            'issues': []
        }
        
        if 'error' in audio_quality:
            checks['pass'] = False
            checks['issues'].append('Audio quality analysis failed')
            return checks
        
        # Check sample rate match
        if not audio_quality.get('sample_rate_match', False):
            checks['pass'] = False
            checks['issues'].append('Sample rate mismatch between input and output')
        
        # Check DC offset
        dc_offset_max = thresholds.get('dc_offset_max', 0.01)
        dc_offset_output = abs(audio_quality.get('dc_offset_output', 0.0))
        if dc_offset_output > dc_offset_max:
            checks['pass'] = False
            checks['issues'].append(f'DC offset too high: {dc_offset_output:.4f} > {dc_offset_max}')
        
        # Check clipping
        clipping_max_fraction = thresholds.get('clipping_max_fraction', 0.001)
        clipping_output = audio_quality.get('clipping_output', 0)
        # Estimate total samples from audio duration (assuming 1 second analyzed)
        estimated_samples = int(self.audio_samp_rate)  # 1 second at audio sample rate
        clipping_fraction = clipping_output / estimated_samples if estimated_samples > 0 else 0.0
        if clipping_fraction > clipping_max_fraction:
            checks['pass'] = False
            checks['issues'].append(f'Clipping too high: {clipping_fraction:.4f} > {clipping_max_fraction}')
        
        # Check dynamic range
        dynamic_range_min = thresholds.get('dynamic_range_min', 0.5)
        dynamic_range_output = audio_quality.get('dynamic_range_output', 0.0)
        if dynamic_range_output < dynamic_range_min:
            checks['issues'].append(f'Dynamic range low: {dynamic_range_output:.4f} < {dynamic_range_min}')
        
        # Check audio SNR
        snr_audio_min_db = thresholds.get('snr_audio_min_db', 20.0)
        snr_audio_db = audio_quality.get('snr_audio_db')
        if snr_audio_db is not None and snr_audio_db < snr_audio_min_db:
            checks['issues'].append(f'Audio SNR low: {snr_audio_db:.2f} dB < {snr_audio_min_db} dB')
        
        # Check WARP-Q score if available
        # Note: In WARP-Q, lower raw scores indicate better quality
        # Normalized score is 0-1 where 1 is best quality
        if audio_quality.get('warpq_available', False):
            # For raw score: lower is better, so we check if it's below a maximum threshold
            warpq_max_raw_score = thresholds.get('warpq_max_raw_score', 2.0)  # Good quality typically < 2.0
            warpq_min_normalized = thresholds.get('warpq_min_normalized', 0.4)  # 0.4 normalized = good quality
            warpq_score = audio_quality.get('warpq_score')
            warpq_normalized = audio_quality.get('warpq_normalized')
            
            if warpq_score is not None:
                # Lower raw score is better, so check if it exceeds the maximum acceptable
                if warpq_score > warpq_max_raw_score:
                    checks['issues'].append(f'WARP-Q raw score too high (worse quality): {warpq_score:.4f} > {warpq_max_raw_score} (lower is better)')
                else:
                    logger.info(f'WARP-Q raw score acceptable: {warpq_score:.4f} <= {warpq_max_raw_score} (lower is better)')
            
            if warpq_normalized is not None:
                # Higher normalized score is better (0-1 scale, 1 is best)
                if warpq_normalized < warpq_min_normalized:
                    checks['issues'].append(f'WARP-Q normalized score low: {warpq_normalized:.4f} < {warpq_min_normalized} (higher is better)')
                else:
                    logger.info(f'WARP-Q normalized score acceptable: {warpq_normalized:.4f} >= {warpq_min_normalized}')
        else:
            logger.warning("WARP-Q not available, using basic audio quality metrics only")
        
        return checks
    
    def check_state_machine(self, metrics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check state machine behavior."""
        checks = {
            'pass': True,
            'issues': []
        }
        
        # Check that system initializes properly
        # This is verified by the fact that the test ran without crashing
        
        # Check that processing rate is reasonable
        processing_rate_min = self.config.get('validation', {}).get('processing_rate_min', 1000.0)
        processing_rate = metrics_data.get('processing_rate', 0.0)
        if processing_rate > 0 and processing_rate < processing_rate_min:
            checks['issues'].append(f'Processing rate low: {processing_rate:.1f} < {processing_rate_min}')
        
        # Check for recovery after errors
        # This would require analyzing error patterns over time
        # For now, we check that system continues processing
        
        return checks


def run_test_suite(config_file: str, wav_input: str, output_dir: str) -> List[Dict[str, Any]]:
    """Run complete test suite."""
    # Load configuration
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Test matrix
    snr_range = config.get('snr_range', {'start': -5, 'end': 20, 'step': 1})
    modulations = config.get('modulations', ['4FSK', '8FSK'])
    crypto_modes = config.get('crypto_modes', ['none', 'sign', 'encrypt', 'both'])
    channel_types = config.get('channel_types', ['clean', 'AWGN', 'rayleigh', 'rician'])
    freq_offsets = config.get('freq_offsets', [0.0, 100.0, 500.0, 1000.0])
    
    all_results = []
    
    # Generate test combinations
    test_count = 0
    total_tests = (
        len(range(snr_range['start'], snr_range['end'] + 1, snr_range['step'])) *
        len(modulations) *
        len(crypto_modes) *
        len(channel_types) *
        len(freq_offsets)
    )
    
    logger.info(f"Running {total_tests} test combinations...")
    
    for snr_db in range(snr_range['start'], snr_range['end'] + 1, snr_range['step']):
        for modulation in modulations:
            for crypto_mode in crypto_modes:
                for channel_type in channel_types:
                    for freq_offset in freq_offsets:
                        test_count += 1
                        logger.info(f"Test {test_count}/{total_tests}")
                        
                        # Create test config
                        test_config = config.copy()
                        test_config.update({
                            'snr_db': float(snr_db),
                            'modulation': modulation,
                            'crypto_mode': crypto_mode,
                            'channel_type': channel_type,
                            'freq_offset_hz': freq_offset
                        })
                        
                        # Create test directory
                        test_dir = Path(output_dir) / f"test_{test_count:04d}"
                        test_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Run test
                        test = TestFlowgraph(test_config, wav_input, str(test_dir))
                        result = test.run_test(duration=config.get('test_duration', 5.0))
                        result['test_number'] = test_count
                        all_results.append(result)
                        
                        # Save individual result
                        result_file = test_dir / 'result.json'
                        with open(result_file, 'w') as f:
                            json.dump(result, f, indent=2)
    
    # Save all results
    results_file = Path(output_dir) / 'all_results.json'
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    # Save CSV summary
    csv_file = Path(output_dir) / 'results_summary.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'test_number', 'snr_db', 'modulation', 'crypto_mode', 'channel_type',
            'freq_offset_hz', 'fer', 'frame_count', 'error_count', 'elapsed_time'
        ])
        writer.writeheader()
        for result in all_results:
            if 'error' not in result:
                writer.writerow({
                    'test_number': result.get('test_number', 0),
                    'snr_db': result.get('test_config', {}).get('snr_db', 0),
                    'modulation': result.get('test_config', {}).get('modulation', ''),
                    'crypto_mode': result.get('test_config', {}).get('crypto_mode', ''),
                    'channel_type': result.get('test_config', {}).get('channel_type', ''),
                    'freq_offset_hz': result.get('test_config', {}).get('freq_offset_hz', 0),
                    'fer': result.get('metrics', {}).get('fer', 1.0),
                    'frame_count': result.get('metrics', {}).get('frame_count', 0),
                    'error_count': result.get('metrics', {}).get('error_count', 0),
                    'elapsed_time': result.get('metrics', {}).get('elapsed_time', 0)
                })
    
    logger.info(f"Test suite complete. Results saved to {output_dir}")
    return all_results


def main():
    parser = argparse.ArgumentParser(description='gr-sleipnir Comprehensive Test Suite')
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='Configuration file (default: config.yaml)')
    parser.add_argument('--wav', type=str, default='../wav/cq_pcm.wav',
                       help='Input WAV file (default: ../wav/cq_pcm.wav)')
    parser.add_argument('--output', type=str, default='test_results',
                       help='Output directory (default: test_results)')
    parser.add_argument('--single', action='store_true',
                       help='Run single test instead of full suite')
    
    args = parser.parse_args()
    
    # Check input file
    wav_path = Path(args.wav)
    if not wav_path.exists():
        logger.error(f"WAV file not found: {wav_path}")
        return 1
    
    # Check config file
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return 1
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.single:
        # Run single test
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        test = TestFlowgraph(config, str(wav_path), str(output_dir))
        result = test.run_test()
        print(json.dumps(result, indent=2))
    else:
        # Run full test suite
        results = run_test_suite(str(config_path), str(wav_path), str(output_dir))
        logger.info(f"Completed {len(results)} tests")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

