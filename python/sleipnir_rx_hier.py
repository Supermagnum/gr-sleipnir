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

from gnuradio import gr, blocks
from gnuradio.gr import sizeof_gr_complex, sizeof_float
import pmt

# Import our custom blocks
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class sleipnir_rx_hier(gr.hier_block2):
    """
    gr-sleipnir RX hierarchical block.

    Inputs:
    - Port 0: Complex baseband samples (complex64) - RF sample rate

    Outputs:
    - Port 0: Audio samples (float32) - 8 kHz

    Message Ports:
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

        # Calculate samples per symbol
        self.sps = int(rf_samp_rate / symbol_rate)

        # Blocks would be connected here in actual implementation
        # This is a template showing the structure

        # 1. Demodulator (assumed to be connected externally)
        # 2. Symbol sync (assumed to be connected externally)
        # 3. Symbol to bits conversion
        # 4. LDPC decoder
        # 5. Superframe parser
        # 6. Opus decoder
        # 7. Audio output

        # Message ports
        self.message_port_register_hier_in("ctrl")
        self.message_port_register_hier_in("key_source")
        # Note: Message handler will be connected in flowgraph
        # For now, store handler reference
        self._key_source_handler = self.handle_key_source_msg
        
        self.message_port_register_hier_out("status")
        self.message_port_register_hier_out("audio_pdu")
        
        # Key source state
        self.key_source_private_key = None
        self.key_source_public_keys = {}

    def set_local_callsign(self, callsign: str):
        """Update local callsign."""
        self.local_callsign = callsign

    def set_require_signatures(self, require: bool):
        """Set require signatures flag."""
        # Update parser
        pass

    def set_private_key_path(self, key_path: str):
        """Update private key path."""
        # Update parser
        pass
    
    def handle_key_source_msg(self, msg):
        """Handle key source messages from gr-linux-crypto blocks (kernel_keyring_source, nitrokey_interface)."""
        import pmt
        
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

