#!/usr/bin/env python3
"""
gr-sleipnir RX Hierarchical Block

Complete RX chain combining:
- RF input from demodulator
- LDPC decoding
- Superframe parsing
- Signature verification
- Decryption
- Audio output
- Status reporting
"""

from gnuradio import gr, blocks, filter, analog, digital
from gnuradio.gr import sizeof_gr_complex, sizeof_float
import pmt
import numpy as np
import os
import math

# Import our custom blocks
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import gr-opus
try:
    from gnuradio import gr_opus
    OPUS_AVAILABLE = True
except ImportError:
    OPUS_AVAILABLE = False
    raise ImportError("gr-opus is required but not available. Please install gr-opus.")

# Import sleipnir blocks
from python.sleipnir_superframe_parser import make_sleipnir_superframe_parser

# Check FEC availability
try:
    from gnuradio import fec
    FEC_AVAILABLE = True
except ImportError:
    FEC_AVAILABLE = False
    fec = None
    print("Warning: GNU Radio FEC module not available")


class sleipnir_rx_hier(gr.hier_block2):
    """
    gr-sleipnir RX hierarchical block.

    Inputs:
    - Port 0: Complex baseband samples (complex64) - RF sample rate

    Outputs:
    - Port 0: Audio samples (float32) - 8 kHz

    Message Ports:
    - ctrl: Control messages (PMT dict)
    - key_source: Key source messages (PMT dict)
    - status: Status messages (PMT dict)
    - audio_pdu: Audio PDUs (PMT blob)
    """

    def __init__(
        self,
        local_callsign: str = "N0CALL",
        audio_samp_rate: float = 8000.0,
        rf_samp_rate: float = 48000.0,
        symbol_rate: float = 4800.0,
        fsk_deviation: float = 2400.0,
        fsk_levels: int = 4,  # 4 for 4FSK, 8 for 8FSK
        auth_matrix_file: str = "../ldpc_matrices/ldpc_auth_768_256.alist",
        voice_matrix_file: str = "../ldpc_matrices/ldpc_voice_576_384.alist",
        private_key_path: str = None,
        require_signatures: bool = False,
        public_key_store_path: str = None
    ):
        """
        Initialize sleipnir RX hierarchical block.

        Args:
            local_callsign: This station's callsign
            audio_samp_rate: Audio sample rate (Hz)
            rf_samp_rate: RF sample rate (Hz)
            symbol_rate: Symbol rate (symbols/sec)
            fsk_deviation: FSK deviation (Hz)
            fsk_levels: Number of FSK levels (4 or 8)
            auth_matrix_file: Path to auth LDPC matrix
            voice_matrix_file: Path to voice LDPC matrix
            private_key_path: Path to private key for decryption
            require_signatures: Require valid signatures
            public_key_store_path: Path to public key store directory
        """
        gr.hier_block2.__init__(
            self,
            "sleipnir_rx_hier",
            gr.io_signature(1, 1, sizeof_gr_complex),  # Complex input
            gr.io_signature(1, 1, sizeof_float)  # Audio output
        )

        # Parameters
        self.local_callsign = local_callsign
        self.audio_samp_rate = audio_samp_rate
        self.rf_samp_rate = rf_samp_rate
        self.symbol_rate = symbol_rate
        self.fsk_deviation = fsk_deviation
        self.fsk_levels = fsk_levels
        self.require_signatures = require_signatures

        # Calculate samples per symbol
        self.sps = int(rf_samp_rate / symbol_rate)

        # Resolve matrix file paths
        project_root = Path(__file__).parent.parent.resolve()
        if not os.path.isabs(auth_matrix_file):
            # Handle relative paths like "../ldpc_matrices/..." or "ldpc_matrices/..."
            if auth_matrix_file.startswith("../"):
                # Remove "../" prefix and join with project root
                auth_matrix_file = project_root / auth_matrix_file[3:]
            elif auth_matrix_file.startswith("ldpc_matrices/"):
                auth_matrix_file = project_root / auth_matrix_file
            else:
                # Just filename, assume it's in ldpc_matrices/
                auth_matrix_file = project_root / "ldpc_matrices" / auth_matrix_file
            auth_matrix_file = str(auth_matrix_file)
        if not os.path.isabs(voice_matrix_file):
            # Handle relative paths like "../ldpc_matrices/..." or "ldpc_matrices/..."
            if voice_matrix_file.startswith("../"):
                # Remove "../" prefix and join with project root
                voice_matrix_file = project_root / voice_matrix_file[3:]
            elif voice_matrix_file.startswith("ldpc_matrices/"):
                voice_matrix_file = project_root / voice_matrix_file
            else:
                # Just filename, assume it's in ldpc_matrices/
                voice_matrix_file = project_root / "ldpc_matrices" / voice_matrix_file
            voice_matrix_file = str(voice_matrix_file)

        # Build RX chain

        # 1. AGC (Automatic Gain Control)
        agc = analog.agc2_cc(1e-2, 1e-2, 1.0, 1.0)
        agc.set_max_gain(65536)

        # 2. Quadrature demodulator (FSK demodulation)
        sensitivity = rf_samp_rate / (2.0 * math.pi * fsk_deviation)
        quadrature_demod = analog.quadrature_demod_cf(sensitivity)

        # 3. Root raised cosine filter (matched filter)
        rrc_alpha = 0.35
        rrc_ntaps = 11 * self.sps
        rrc_taps = filter.firdes.root_raised_cosine(
            gain=1.0,
            sampling_freq=rf_samp_rate,
            symbol_rate=symbol_rate,
            alpha=rrc_alpha,
            ntaps=rrc_ntaps
        )
        rrc_filter = filter.fir_filter_fff(1, rrc_taps)

        # 4. Symbol sync (timing recovery)
        # For FSK, we use a simple approach: just use the symbol sync with basic parameters
        # Note: symbol_sync_ff may not be ideal for FSK, but we'll use it for now
        # Alternative: use a simple decimating FIR filter or polyphase clock sync
        try:
            # Try to create symbol sync - if it fails, use a simpler approach
            constellation = digital.constellation_bpsk()
            symbol_sync = digital.symbol_sync_ff(
                digital.TED_MUELLER_AND_MULLER,
                self.sps,
                0.045,  # loop bandwidth
                1.0,  # damping factor
                1.0,  # TED gain
                1.5,  # max deviation
                1,  # osps
                constellation.base(),  # slicer
                digital.IR_MMSE_8TAP,  # interp_type
                128,  # n_filters
                []  # taps
            )
        except Exception as e:
            # Fallback: use simple decimation for symbol timing
            logger.warning(f"Could not create symbol_sync, using simple decimation: {e}")
            # Simple decimation by sps
            symbol_sync = filter.rational_resampler_fff(1, self.sps)

        # 5. Symbol slicing (convert to bits)
        # Add offset to center symbols
        add_const = blocks.add_const_vff([1.0])  # Offset to center
        multiply_const = blocks.multiply_const_vff([0.5])  # Scale
        float_to_uchar = blocks.float_to_uchar(1, 1.0)
        
        # 6. Unpack bits
        unpack_bits = blocks.unpacked_to_packed_bb(1, gr.GR_MSB_FIRST)
        
        # 7. Convert to float for LDPC decoder (soft bits)
        uchar_to_float = blocks.uchar_to_float()

        # 8. FEC LDPC decoder (using GNU Radio-generated matrices)
        # Voice frames: 72 bytes (576 bits) input -> 49 bytes (386 bits) output
        # Temporarily disabled to debug crash
        ldpc_decoder = None
        USE_FEC = False  # Set to True once crash is fixed
        
        if USE_FEC and FEC_AVAILABLE and os.path.exists(voice_matrix_file):
            decoder_obj = fec.ldpc_decoder_make(voice_matrix_file, 50)  # max_iterations as positional arg
            # Wrap decoder object to make it a proper GNU Radio block
            # Decoder takes float32 (soft decisions) input, outputs uint8
            ldpc_decoder = fec.decoder(decoder_obj, gr.sizeof_float, gr.sizeof_char)
        
        # 9. Stream to PDU for superframe parser
        # LDPC decoder outputs uint8 stream, convert to PDU
        # Voice matrix: 386 bits input -> 576 bits output (72 bytes)
        # Auth matrix: TBD (currently using voice matrix, so 72 bytes)
        frame_size_bytes = 72  # 576 bits output from voice LDPC decoder
        ldpc_stream_to_tagged = blocks.stream_to_tagged_stream(
            itemsize=1,  # uint8
            vlen=1,
            packet_len=frame_size_bytes,
            len_tag_key="packet_len"
        )
        from gnuradio import pdu
        from gnuradio.gr import sizeof_char
        ldpc_tagged_to_pdu = pdu.tagged_stream_to_pdu(sizeof_char, "packet_len")
        char_to_short_ldpc = blocks.char_to_short(1)

        # 10. Superframe parser (PDU-based)
        superframe_parser = make_sleipnir_superframe_parser(
            local_callsign=local_callsign,
            private_key_path=private_key_path,
            require_signatures=require_signatures,
            public_key_store_path=public_key_store_path,
            enable_sync_detection=True
        )
        
        # Store references to Python blocks to prevent garbage collection
        self._superframe_parser = superframe_parser
        if ldpc_decoder:
            self._ldpc_decoder = ldpc_decoder

        # 11. PDU to stream for Opus decoder
        # Opus decoder expects stream of bytes
        from gnuradio import pdu
        from gnuradio.gr import sizeof_char
        pdu_to_stream = pdu.pdu_to_tagged_stream(sizeof_char, "packet_len")
        # pdu_to_tagged_stream outputs short (itemsize 2), convert to char (itemsize 1) for Opus decoder
        short_to_char_opus = blocks.short_to_char(1)

        # 12. Opus decoder (gr-opus)
        # Store reference to prevent garbage collection
        opus_decoder = gr_opus.opus_decoder(
            sample_rate=int(audio_samp_rate),
            channels=1
        )
        self._opus_decoder = opus_decoder

        # 13. Audio low-pass filter (post-processing)
        audio_lpf = filter.fir_filter_fff(
            1,
            filter.firdes.low_pass(
                1.0, audio_samp_rate, 3400.0, 400.0,
                1, 6.76  # Window type 1 = HAMMING
            )
        )

        # Connect the chain
        self.connect(self, agc, quadrature_demod)
        self.connect(quadrature_demod, rrc_filter)
        self.connect(rrc_filter, symbol_sync)
        self.connect(symbol_sync, add_const, multiply_const, float_to_uchar)
        self.connect(float_to_uchar, unpack_bits, uchar_to_float)
        # LDPC decoder is stream-based (float32 input, uint8 output)
        # LDPC decoder is stream-based (float32 input, uint8 output)
        if ldpc_decoder:
            self.connect(uchar_to_float, ldpc_decoder)
            # Convert LDPC decoder output (stream) to PDU for superframe parser
            self.connect(ldpc_decoder, ldpc_stream_to_tagged)
        else:
            # No FEC, pass through (hard decision)
            # Convert float to uchar, then uchar to char (uint8)
            float_to_uchar2 = blocks.float_to_uchar(1, 1.0)
            # uchar is already uint8, so we can use it directly with stream_to_tagged_stream
            self.connect(uchar_to_float, float_to_uchar2, ldpc_stream_to_tagged)
        self.connect(ldpc_stream_to_tagged, char_to_short_ldpc, ldpc_tagged_to_pdu)
        self.msg_connect(ldpc_tagged_to_pdu, "pdus", superframe_parser, "in")
        self.msg_connect(superframe_parser, "out", pdu_to_stream, "pdus")
        self.connect(pdu_to_stream, short_to_char_opus, opus_decoder)
        self.connect(opus_decoder, audio_lpf, self)

        # Message ports
        self.message_port_register_hier_in("ctrl")
        self.message_port_register_hier_in("key_source")
        self.message_port_register_hier_out("status")
        self.message_port_register_hier_out("audio_pdu")
        self.message_port_register_hier_out("aprs_out")
        self.message_port_register_hier_out("text_out")
        self._key_source_handler = self.handle_key_source_msg
        
        # Connect ctrl port to superframe parser
        self.msg_connect(self, "ctrl", superframe_parser, "ctrl")
        
        # Connect status output from parser
        self.msg_connect(superframe_parser, "status", self, "status")
        
        # Connect APRS and text outputs
        self.msg_connect(superframe_parser, "aprs_out", self, "aprs_out")
        self.msg_connect(superframe_parser, "text_out", self, "text_out")
        
        # Note: superframe_parser has "out" port for Opus frames, but we don't need to forward it
        # as the audio is already going through the stream connection via pdu_to_stream
        
        # Key source state
        self.key_source_private_key = None
        self.key_source_public_keys = {}

    def set_local_callsign(self, callsign: str):
        """Update local callsign."""
        self.local_callsign = callsign

    def set_require_signatures(self, require: bool):
        """Set require signatures flag."""
        self.require_signatures = require

    def set_private_key_path(self, key_path: str):
        """Update private key path."""
        pass
    
    def handle_key_source_msg(self, msg):
        """Handle key source messages from gr-linux-crypto blocks (kernel_keyring_source, nitrokey_interface)."""
        if not pmt.is_dict(msg):
            return
        
        try:
            # Extract private key if present (for decryption)
            if pmt.dict_has_key(msg, pmt.intern("private_key")):
                key_pmt = pmt.dict_ref(msg, pmt.intern("private_key"), pmt.PMT_NIL)
                if pmt.is_u8vector(key_pmt):
                    key_bytes = bytes(pmt.u8vector_elements(key_pmt))
                    # Load private key from bytes (PEM or DER format)
                    try:
                        from cryptography.hazmat.primitives import serialization
                        from cryptography.hazmat.backends import default_backend
                        # Try PEM format first
                        try:
                            self.key_source_private_key = serialization.load_pem_private_key(
                                key_bytes, password=None, backend=default_backend()
                            )
                        except:
                            # Try DER format
                            self.key_source_private_key = serialization.load_der_private_key(
                                key_bytes, password=None, backend=default_backend()
                            )
                        
                        # Forward private key to internal blocks via ctrl message
                        key_serialized = self.key_source_private_key.private_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.PKCS8,
                            encryption_algorithm=serialization.NoEncryption()
                        )
                        ctrl_msg = pmt.make_dict()
                        ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("private_key"), 
                                                pmt.init_u8vector(len(key_serialized), list(key_serialized)))
                        self.message_port_pub(pmt.intern("ctrl"), ctrl_msg)
                    except Exception as e:
                        print(f"Warning: Could not load private key from key_source: {e}")
            
            # Extract public key if present (for signature verification)
            if pmt.dict_has_key(msg, pmt.intern("public_key")):
                key_pmt = pmt.dict_ref(msg, pmt.intern("public_key"), pmt.PMT_NIL)
                key_id_pmt = pmt.dict_ref(msg, pmt.intern("key_id"), pmt.PMT_NIL) if pmt.dict_has_key(msg, pmt.intern("key_id")) else pmt.intern("default")
                key_id = pmt.symbol_to_string(key_id_pmt) if pmt.is_symbol(key_id_pmt) else "default"
                
                if pmt.is_u8vector(key_pmt):
                    key_bytes = bytes(pmt.u8vector_elements(key_pmt))
                    # Load public key from bytes (PEM or DER format)
                    try:
                        from cryptography.hazmat.primitives import serialization
                        from cryptography.hazmat.backends import default_backend
                        # Try PEM format first
                        try:
                            public_key = serialization.load_pem_public_key(
                                key_bytes, backend=default_backend()
                            )
                            self.key_source_public_keys[key_id] = public_key
                        except:
                            # Try DER format
                            public_key = serialization.load_der_public_key(
                                key_bytes, backend=default_backend()
                            )
                            self.key_source_public_keys[key_id] = public_key
                        
                        # Forward public key to internal blocks via ctrl message
                        key_serialized = public_key.public_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PublicFormat.SubjectPublicKeyInfo
                        )
                        ctrl_msg = pmt.make_dict()
                        ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("public_key"), 
                                               pmt.init_u8vector(len(key_serialized), list(key_serialized)))
                        ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("key_id"), pmt.intern(key_id))
                        self.message_port_pub(pmt.intern("ctrl"), ctrl_msg)
                    except Exception as e:
                        print(f"Warning: Could not load public key from key_source: {e}")
            
            # Extract key ID or other metadata
            if pmt.dict_has_key(msg, pmt.intern("key_id")):
                key_id = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("key_id"), pmt.PMT_NIL)
                )
                print(f"Received key from source: {key_id}")
        
        except Exception as e:
            print(f"Error handling key_source message: {e}")


def make_sleipnir_rx_hier(
    local_callsign: str = "N0CALL",
    audio_samp_rate: float = 8000.0,
    rf_samp_rate: float = 48000.0,
    symbol_rate: float = 4800.0,
    fsk_deviation: float = 2400.0,
    fsk_levels: int = 4,
    auth_matrix_file: str = "../ldpc_matrices/ldpc_auth_768_256.alist",
    voice_matrix_file: str = "../ldpc_matrices/ldpc_voice_576_384.alist",
    private_key_path: str = None,
    require_signatures: bool = False,
    public_key_store_path: str = None
):
    """Factory function for GRC."""
    return sleipnir_rx_hier(
        local_callsign=local_callsign,
        audio_samp_rate=audio_samp_rate,
        rf_samp_rate=rf_samp_rate,
        symbol_rate=symbol_rate,
        fsk_deviation=fsk_deviation,
        fsk_levels=fsk_levels,
        auth_matrix_file=auth_matrix_file,
        voice_matrix_file=voice_matrix_file,
        private_key_path=private_key_path,
        require_signatures=require_signatures,
        public_key_store_path=public_key_store_path
    )
