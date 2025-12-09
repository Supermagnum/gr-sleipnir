#!/usr/bin/env python3
"""
gr-sleipnir TX Hierarchical Block

Complete TX chain combining:
- Opus encoder input
- Superframe assembly
- LDPC encoding
- 4FSK/8FSK modulation
- RF output

This can be used as a hierarchical block in GRC.
"""

from gnuradio import gr, blocks, filter, analog, digital
from gnuradio.gr import sizeof_gr_complex, sizeof_float
import pmt
import math
import numpy as np
import os

# Check FEC availability
try:
    from gnuradio import fec
    FEC_AVAILABLE = True
except ImportError:
    FEC_AVAILABLE = False
    fec = None
    print("Warning: GNU Radio FEC module not available")

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
from python.sleipnir_superframe_assembler import make_sleipnir_superframe_assembler


class sleipnir_tx_hier(gr.hier_block2):
    """
    gr-sleipnir TX hierarchical block.

    Inputs:
    - Port 0: Audio samples (float32) - 8 kHz

    Outputs:
    - Port 0: Complex baseband (complex64) - RF sample rate

    Message Ports:
    - ctrl: Control messages (PMT dict)
    - key_source: Key source messages (PMT dict)
    """

    def __init__(
        self,
        callsign: str = "N0CALL",
        audio_samp_rate: float = 8000.0,
        rf_samp_rate: float = 48000.0,
        symbol_rate: float = 4800.0,
        fsk_deviation: float = 2400.0,
        fsk_levels: int = 4,  # 4 for 4FSK, 8 for 8FSK
        auth_matrix_file: str = "../ldpc_matrices/ldpc_auth_768_256.alist",
        voice_matrix_file: str = "../ldpc_matrices/ldpc_voice_576_384.alist",
        enable_signing: bool = False,
        enable_encryption: bool = False,
        private_key_path: str = None,
        mac_key: bytes = None
    ):
        """
        Initialize sleipnir TX hierarchical block.

        Args:
            callsign: Source callsign
            audio_samp_rate: Audio sample rate (Hz)
            rf_samp_rate: RF sample rate (Hz)
            symbol_rate: Symbol rate (symbols/sec)
            fsk_deviation: FSK deviation (Hz)
            fsk_levels: Number of FSK levels (4 or 8)
            auth_matrix_file: Path to auth LDPC matrix
            voice_matrix_file: Path to voice LDPC matrix
            enable_signing: Enable ECDSA signing
            enable_encryption: Enable encryption
            private_key_path: Path to private key file
            mac_key: MAC key (32 bytes)
        """
        gr.hier_block2.__init__(
            self,
            "sleipnir_tx_hier",
            gr.io_signature(1, 1, sizeof_float),  # Audio input
            gr.io_signature(1, 1, sizeof_gr_complex)  # Complex output
        )

        # Parameters
        self.callsign = callsign
        self.audio_samp_rate = audio_samp_rate
        self.rf_samp_rate = rf_samp_rate
        self.symbol_rate = symbol_rate
        self.fsk_deviation = fsk_deviation
        self.fsk_levels = fsk_levels
        self.enable_signing = enable_signing
        self.enable_encryption = enable_encryption

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

        # Build TX chain

        # 1. Audio low-pass filter (preprocessing)
        audio_lpf = filter.fir_filter_fff(
            1,
            filter.firdes.low_pass(
                1.0, audio_samp_rate, 3400.0, 400.0,
                1, 6.76  # Window type 1 = HAMMING
            )
        )

        # 2. Opus encoder (gr-opus)
        # Opus encoder outputs bytes (char stream)
        opus_bitrate = 9600 if fsk_levels == 4 else 8000
        opus_encoder = gr_opus.opus_encoder(
            sample_rate=int(audio_samp_rate),
            channels=1,
            bitrate=opus_bitrate,
            application="audio"  # "audio" for VOIP application
        )
        # Store reference to prevent garbage collection
        # Note: Storing as instance variable may cause recursion issues in some gr-opus versions
        # but is necessary to prevent garbage collection
        self._opus_encoder = opus_encoder
        # Try to set buffer sizes if available to help with threading issues
        try:
            if hasattr(opus_encoder, 'set_min_output_buffer'):
                opus_encoder.set_min_output_buffer(1024)  # Reasonable buffer size
        except:
            pass  # Buffer setting may not be available

        # 3. Packetize Opus frames and convert to PDU for superframe assembler
        # Opus encoder outputs variable-size frames (~23-29 bytes at 9600 bps)
        # We need fixed-size 40-byte frames for the superframe assembler
        from python.opus_frame_packetizer import opus_frame_packetizer
        opus_frame_size = 40  # Fixed frame size expected by superframe assembler
        opus_packetizer = opus_frame_packetizer(frame_size_bytes=opus_frame_size)
        # Store reference to prevent garbage collection
        self._opus_packetizer = opus_packetizer
        
        # Stream to tagged stream for PDU conversion
        stream_to_tagged = blocks.stream_to_tagged_stream(
            itemsize=1,  # uint8 (char)
            vlen=1,
            packet_len=opus_frame_size,
            len_tag_key="packet_len"
        )
        # Set buffer sizes to prevent forecast issues that might cause recursion
        try:
            stream_to_tagged.set_min_output_buffer(opus_frame_size * 4)
            stream_to_tagged.set_max_output_buffer(opus_frame_size * 16)
        except:
            pass  # Buffer setting methods may not be available in all GNU Radio versions
        
        # Convert tagged stream to PDU
        # tagged_stream_to_pdu expects itemsize matching the stream
        # Since stream_to_tagged outputs char (itemsize 1), we need to convert to short (itemsize 2)
        # because tagged_stream_to_pdu(sizeof_char) actually expects short input
        from gnuradio import pdu
        from gnuradio.gr import sizeof_char
        char_to_short_pdu = blocks.char_to_short(1)
        tagged_to_pdu = pdu.tagged_stream_to_pdu(sizeof_char, "packet_len")

        # 4. Superframe assembler (PDU-based)
        superframe_assembler = make_sleipnir_superframe_assembler(
            callsign=callsign,
            enable_signing=enable_signing,
            enable_encryption=enable_encryption,
            private_key_path=private_key_path,
            mac_key=mac_key,
            enable_sync_frames=True,
            sync_frame_interval=5
        )

        # 5. FEC LDPC encoder (using GNU Radio-generated matrices)
        # Voice frames: 48 bytes (384 bits) input -> 72 bytes (576 bits) output
        # Auth frames: 32 bytes (256 bits) input -> 96 bytes (768 bits) output
        ldpc_encoder = None
        encoder_obj = None
        frame_input_bytes = 48  # Default: 48 bytes (384 bits) for voice matrix
        
        # Temporarily disable FEC to debug segmentation fault
        # TODO: Fix FEC decoder integration - forecast crash still occurring
        USE_FEC = False
        
        if USE_FEC and FEC_AVAILABLE and os.path.exists(voice_matrix_file):
            encoder_obj = fec.ldpc_encoder_make(voice_matrix_file)
            # Get actual frame size from encoder (should be 384 bits = 48 bytes)
            frame_input_bits = encoder_obj.get_input_size()
            frame_input_bytes = (frame_input_bits + 7) // 8
            # Wrap encoder object to make it a proper GNU Radio block
            # Using tagged stream ensures proper buffer forecasting
            ldpc_encoder = fec.encoder(encoder_obj, gr.sizeof_char, gr.sizeof_char)
        
        # Convert PDU to stream for FEC encoder
        # The superframe assembler outputs concatenated frames, but FEC encoder
        # needs individual frames. We'll use stream_to_tagged_stream to split them.
        from gnuradio.gr import sizeof_char
        superframe_pdu_to_stream = pdu.pdu_to_tagged_stream(sizeof_char, "packet_len")
        short_to_char = blocks.short_to_char(1)
        
        # Split concatenated superframe into individual frames for FEC encoding
        # Each frame is frame_input_bytes long (48 bytes for voice matrix)
        # Only create frame_splitter if FEC is enabled
        frame_splitter = None
        if ldpc_encoder:
            frame_splitter = blocks.stream_to_tagged_stream(
                itemsize=1,  # uint8
                vlen=1,
                packet_len=frame_input_bytes,
                len_tag_key="packet_len"
            )
        
        # 6. Convert bytes to bits for symbol mapping
        # Follow GRC example flow: packed_to_unpacked -> char_to_short -> float_to_int -> chunks_to_symbols
        # chunks_to_symbols_if handles bit grouping internally based on symbol table size
        packed_to_unpacked = blocks.packed_to_unpacked_bb(1, gr.GR_MSB_FIRST)  # Unpack bytes to bits (1 bit per item)
        # Convert unpacked bits (uint8, values 0 or 1) to integers
        bits_to_short = blocks.char_to_short(1)  # Convert uint8 bits to int16
        short_to_float = blocks.short_to_float(1, 1.0)  # Convert int16 to float
        float_to_int = blocks.float_to_int(1, 1.0)  # Convert float to int (for chunks_to_symbols_if)

        # 9. Symbol mapping (4FSK or 8FSK)
        if fsk_levels == 4:
            symbol_table = [-3, -1, 1, 3]
            bits_per_symbol = 2
        elif fsk_levels == 8:
            symbol_table = [-7, -5, -3, -1, 1, 3, 5, 7]
            bits_per_symbol = 3
        else:
            raise ValueError(f"Invalid FSK levels: {fsk_levels}")

        symbol_mapper = digital.chunks_to_symbols_if(symbol_table, 1)

        # 10. Root raised cosine filter (pulse shaping)
        rrc_alpha = 0.35
        rrc_ntaps = 11 * self.sps  # Typical: 11 taps per symbol
        rrc_taps = filter.firdes.root_raised_cosine(
            gain=1.0,
            sampling_freq=rf_samp_rate,
            symbol_rate=symbol_rate,
            alpha=rrc_alpha,
            ntaps=rrc_ntaps
        )
        rrc_filter = filter.interp_fir_filter_fff(self.sps, rrc_taps)

        # 11. Frequency modulator (takes float input, outputs complex)
        sensitivity = (2.0 * math.pi * fsk_deviation) / rf_samp_rate
        freq_modulator = analog.frequency_modulator_fc(sensitivity)

        # Store references to Python blocks to prevent garbage collection
        self._superframe_assembler = superframe_assembler
        self._superframe_pdu_to_stream = superframe_pdu_to_stream
        if ldpc_encoder:
            self._ldpc_encoder = ldpc_encoder
        
        # Connect the chain
        self.connect(self, audio_lpf, opus_encoder)
        self.connect(opus_encoder, opus_packetizer)
        self.connect(opus_packetizer, stream_to_tagged)
        self.connect(stream_to_tagged, char_to_short_pdu, tagged_to_pdu)
        self.msg_connect(tagged_to_pdu, "pdus", superframe_assembler, "in")
        
        # Superframe assembler outputs PDU with concatenated frames
        # Convert to stream, then split into individual frames for FEC encoding
        self.msg_connect(superframe_assembler, "out", superframe_pdu_to_stream, "pdus")
        # pdu_to_tagged_stream outputs short (itemsize 2), convert to char (itemsize 1)
        if ldpc_encoder and frame_splitter:
            # Split into individual frames for FEC encoder
            self.connect(superframe_pdu_to_stream, short_to_char, frame_splitter)
            # FEC encoder processes each frame individually
            self.connect(frame_splitter, ldpc_encoder)
            # LDPC encoder outputs bytes (uint8), unpack to bits, convert to ints
            # Follow GRC example: packed_to_unpacked -> char_to_short -> float_to_int -> chunks_to_symbols
            self.connect(ldpc_encoder, packed_to_unpacked, bits_to_short, short_to_float, float_to_int)
        else:
            # No FEC, pass through directly (no frame splitting needed)
            # Convert bytes to bits, then to ints (following GRC example)
            self.connect(superframe_pdu_to_stream, short_to_char, packed_to_unpacked, bits_to_short, short_to_float, float_to_int)
        # chunks_to_symbols_if takes int input (bit patterns), outputs float (symbol values)
        self.connect(float_to_int, symbol_mapper)
        self.connect(symbol_mapper, rrc_filter)
        # frequency_modulator_fc takes float input (itemsize 4), outputs complex (itemsize 8)
        self.connect(rrc_filter, freq_modulator, self)

        # Message ports
        self.message_port_register_hier_in("ctrl")
        self.message_port_register_hier_in("key_source")
        self.message_port_register_hier_in("aprs_in")
        self.message_port_register_hier_in("text_in")
        self._key_source_handler = self.handle_key_source_msg
        
        # Connect ports to superframe assembler
        self.msg_connect(self, "ctrl", superframe_assembler, "ctrl")
        self.msg_connect(self, "aprs_in", superframe_assembler, "aprs_in")
        self.msg_connect(self, "text_in", superframe_assembler, "text_in")
        
        # Key source state
        self.key_source_private_key = None
        self.key_source_mac_key = None

    def set_callsign(self, callsign: str):
        """Update callsign."""
        self.callsign = callsign

    def set_enable_signing(self, enable: bool):
        """Enable/disable signing."""
        self.enable_signing = enable

    def set_enable_encryption(self, enable: bool):
        """Enable/disable encryption."""
        self.enable_encryption = enable
    
    def handle_key_source_msg(self, msg):
        """Handle key source messages from gr-linux-crypto blocks (kernel_keyring_source, nitrokey_interface)."""
        if not pmt.is_dict(msg):
            return
        
        try:
            # Extract private key if present
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
                            self.enable_signing = True
                        except:
                            # Try DER format
                            self.key_source_private_key = serialization.load_der_private_key(
                                key_bytes, password=None, backend=default_backend()
                            )
                            self.enable_signing = True
                        
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
            
            # Extract MAC key if present
            if pmt.dict_has_key(msg, pmt.intern("mac_key")):
                mac_key_pmt = pmt.dict_ref(msg, pmt.intern("mac_key"), pmt.PMT_NIL)
                if pmt.is_u8vector(mac_key_pmt):
                    self.key_source_mac_key = bytes(pmt.u8vector_elements(mac_key_pmt))
                    if len(self.key_source_mac_key) == 32:
                        self.enable_encryption = True
                        
                        # Forward MAC key to internal blocks via ctrl message
                        ctrl_msg = pmt.make_dict()
                        ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("mac_key"), 
                                               pmt.init_u8vector(32, list(self.key_source_mac_key)))
                        self.message_port_pub(pmt.intern("ctrl"), ctrl_msg)
            
            # Extract key ID or other metadata
            if pmt.dict_has_key(msg, pmt.intern("key_id")):
                key_id = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("key_id"), pmt.PMT_NIL)
                )
                print(f"Received key from source: {key_id}")
        
        except Exception as e:
            print(f"Error handling key_source message: {e}")


def make_sleipnir_tx_hier(
    callsign: str = "N0CALL",
    audio_samp_rate: float = 8000.0,
    rf_samp_rate: float = 48000.0,
    symbol_rate: float = 4800.0,
    fsk_deviation: float = 2400.0,
    fsk_levels: int = 4,
    auth_matrix_file: str = "../ldpc_matrices/ldpc_auth_768_256.alist",
    voice_matrix_file: str = "../ldpc_matrices/ldpc_voice_576_384.alist",
    enable_signing: bool = False,
    enable_encryption: bool = False,
    private_key_path: str = None,
    mac_key: bytes = None
):
    """Factory function for GRC."""
    return sleipnir_tx_hier(
        callsign=callsign,
        audio_samp_rate=audio_samp_rate,
        rf_samp_rate=rf_samp_rate,
        symbol_rate=symbol_rate,
        fsk_deviation=fsk_deviation,
        fsk_levels=fsk_levels,
        auth_matrix_file=auth_matrix_file,
        voice_matrix_file=voice_matrix_file,
        enable_signing=enable_signing,
        enable_encryption=enable_encryption,
        private_key_path=private_key_path,
        mac_key=mac_key
    )
