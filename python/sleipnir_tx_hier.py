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

from gnuradio import gr, fec, blocks
from gnuradio.gr import sizeof_gr_complex, sizeof_float
import pmt
import math

# Import our custom blocks
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class sleipnir_tx_hier(gr.hier_block2):
    """
    gr-sleipnir TX hierarchical block.

    Inputs:
    - Port 0: Audio samples (float32) - 8 kHz

    Outputs:
    - Port 0: Complex baseband (complex64) - RF sample rate

    Message Ports:
    - ctrl: Control messages (PMT dict)
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

        # Calculate samples per symbol
        self.sps = int(rf_samp_rate / symbol_rate)

        # Blocks

        # 1. Opus encoder (from gr-opus)
        # Note: This would be gr_opus.opus_encoder in actual implementation
        # For now, we'll use a placeholder or pass through

        # 2. Superframe assembler (PDU-based)
        # Convert audio stream to PDU, then assemble superframes
        # This is complex - for now, we'll create a simplified version

        # 3. LDPC encoder
        # Load LDPC matrix
        try:
            ldpc_encoder_def = fec.ldpc_encoder_make(voice_matrix_file)
        except:
            print(f"Warning: Could not load LDPC matrix {voice_matrix_file}")
            ldpc_encoder_def = None

        # 4. Symbol mapping
        if fsk_levels == 4:
            symbol_table = [-3, -1, 1, 3]
            bits_per_symbol = 2
        elif fsk_levels == 8:
            symbol_table = [-7, -5, -3, -1, 1, 3, 5, 7]
            bits_per_symbol = 3
        else:
            raise ValueError(f"Invalid FSK levels: {fsk_levels}")

        # 5. Pulse shaping (Root Raised Cosine)
        # Note: This is a placeholder - actual implementation would use filter blocks
        # rrc_taps = filter.firdes.root_raised_cosine(...)
        rrc_taps = None

        # 6. Frequency modulator
        sensitivity = (2.0 * math.pi * fsk_deviation) / rf_samp_rate

        # Simplified chain (actual implementation would be more complex)
        # For now, this is a template

        # Connect blocks
        # self.connect(self, audio_input_block, ...)

        # Message ports
        self.message_port_register_hier_in("ctrl")
        self.message_port_register_hier_in("key_source")
        # Note: Message handler will be connected in flowgraph
        # For now, store handler reference
        self._key_source_handler = self.handle_key_source_msg
        
        # Key source state
        self.key_source_private_key = None
        self.key_source_mac_key = None

    def set_callsign(self, callsign: str):
        """Update callsign."""
        self.callsign = callsign

    def set_enable_signing(self, enable: bool):
        """Enable/disable signing."""
        # Update superframe assembler
        pass

    def set_enable_encryption(self, enable: bool):
        """Enable/disable encryption."""
        # Update superframe assembler
        pass
    
    def handle_key_source_msg(self, msg):
        """Handle key source messages from gr-linux-crypto blocks (kernel_keyring_source, nitrokey_interface)."""
        import pmt
        
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
                        # Convert key object back to bytes for transmission
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

