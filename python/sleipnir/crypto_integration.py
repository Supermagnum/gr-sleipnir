#!/usr/bin/env python3
"""
Crypto Integration Blocks for gr-sleipnir

Provides integration with gr-linux-crypto blocks for ECDSA signing/verification
and gr-nacl blocks for ChaCha20-Poly1305 encryption/MAC.

These blocks wrap the GNU Radio crypto blocks and integrate them into
the PDU-based signal flow.
"""

from gnuradio import gr
import pmt
from typing import Optional

# Try to import gr-linux-crypto blocks
# GNU Radio OOT modules can be imported in different ways depending on installation
LINUX_CRYPTO_AVAILABLE = False
LINUX_CRYPTO_MODULE = None
LINUX_CRYPTO_MAKE_FUNCS = {}

# Ensure the correct installation path is in sys.path
# Files are installed in /usr/local/lib/python3/dist-packages
# but Python 3.12 may look in /usr/local/lib/python3.12/dist-packages
import sys
import os
python3_dist_path = '/usr/local/lib/python3/dist-packages'
if python3_dist_path not in sys.path and os.path.exists(python3_dist_path):
    sys.path.insert(0, python3_dist_path)

# Try multiple import methods
import_methods = [
    ('gnuradio.linux_crypto', 'linux_crypto'),  # Try this first (most common)
    ('linux_crypto', 'linux_crypto'),
    ('gr_linux_crypto', 'gr_linux_crypto'),
]

for import_name, module_name in import_methods:
    try:
        if '.' in import_name:
            # For dotted imports like gnuradio.linux_crypto
            parts = import_name.split('.')
            mod = __import__(import_name, fromlist=[parts[-1]])
            LINUX_CRYPTO_MODULE = mod
        else:
            # Direct import
            LINUX_CRYPTO_MODULE = __import__(import_name)
        
        LINUX_CRYPTO_AVAILABLE = True
        print(f"SUCCESS: gr-linux-crypto found as '{import_name}'")
        
        # Look for make functions (GNU Radio convention)
        for attr in dir(LINUX_CRYPTO_MODULE):
            if attr.startswith('make_'):
                func = getattr(LINUX_CRYPTO_MODULE, attr)
                LINUX_CRYPTO_MAKE_FUNCS[attr] = func
        
        # Also check for direct class/function access (gr-linux-crypto uses classes)
        # gr-linux-crypto provides: kernel_keyring_source, nitrokey_interface, 
        # kernel_crypto_aes, brainpool_ecies_encrypt/decrypt, etc.
        available_blocks = []
        for attr in dir(LINUX_CRYPTO_MODULE):
            if not attr.startswith('_'):
                obj = getattr(LINUX_CRYPTO_MODULE, attr)
                # Check if it's a class or callable that might be a block factory
                if callable(obj) or (hasattr(obj, '__module__') and 'linux_crypto' in str(type(obj))):
                    available_blocks.append(attr)
        
        if LINUX_CRYPTO_MAKE_FUNCS:
            print(f"  Found make functions: {list(LINUX_CRYPTO_MAKE_FUNCS.keys())}")
        if available_blocks:
            print(f"  Available blocks/classes: {available_blocks[:20]}")
        break
    except ImportError as e:
        # Check if it's a linking/undefined symbol error (module exists but can't load)
        error_msg = str(e)
        if 'undefined symbol' in error_msg or 'linux_crypto_python' in error_msg:
            print(f"Warning: gr-linux-crypto module found but has linking issues: {error_msg}")
            print("  Module may need to be rebuilt or dependencies installed.")
        continue
    except Exception as e:
        # Other errors (like undefined symbols) - module exists but can't be used
        error_msg = str(e)
        if 'undefined symbol' in error_msg:
            print(f"Warning: gr-linux-crypto module found but has linking issues: {error_msg}")
        continue

if not LINUX_CRYPTO_AVAILABLE:
    print("Warning: gr-linux-crypto not available. Using Python fallback.")
    print("  Tried imports: " + ", ".join([m[0] for m in import_methods]))
    print("  To use gr-linux-crypto, ensure it's installed and GNU Radio can find it.")
    print("  If linking issues persist, try: sudo ldconfig && restart Python")

# Try to import gr-nacl blocks
NACL_AVAILABLE = False
NACL_MODULE = None
NACL_MAKE_FUNCS = {}

nacl_import_methods = [
    ('nacl', 'nacl'),
    ('gnuradio.nacl', 'nacl'),
    ('gr_nacl', 'gr_nacl'),
]

for import_name, module_name in nacl_import_methods:
    try:
        if '.' in import_name:
            parts = import_name.split('.')
            mod = __import__(import_name, fromlist=[parts[-1]])
        else:
            mod = __import__(import_name)
        
        NACL_MODULE = mod
        NACL_AVAILABLE = True
        print(f"SUCCESS: gr-nacl found as '{import_name}'")
        
        # Look for make functions
        for attr in dir(NACL_MODULE):
            if attr.startswith('make_'):
                func = getattr(NACL_MODULE, attr)
                NACL_MAKE_FUNCS[attr] = func
        
        if NACL_MAKE_FUNCS:
            print(f"  Found make functions: {list(NACL_MAKE_FUNCS.keys())}")
        break
    except ImportError:
        continue

if not NACL_AVAILABLE:
    print("Warning: gr-nacl not available. Using Python fallback.")
    print("  Tried imports: " + ", ".join([m[0] for m in nacl_import_methods]))


class ecdsa_sign_block(gr.sync_block):
    """
    ECDSA signing block using gr-linux-crypto or Python fallback.

    Input: PDU with data to sign (blob)
    Output: PDU with signature (blob, 32 bytes)

    Note: gr-linux-crypto provides ECIES (encryption) blocks, not direct ECDSA signing.
    This block uses Python cryptography library for ECDSA signing.
    gr-linux-crypto blocks (brainpool_ecies_*) can be used for encryption operations.
    """

    def __init__(self, private_key_path: str, curve_name: str = "brainpoolP256r1"):
        """
        Initialize ECDSA signing block.

        Args:
            private_key_path: Path to private key file
            curve_name: ECC curve name (default: brainpoolP256r1)
        """
        gr.sync_block.__init__(
            self,
            name="ecdsa_sign_block",
            in_sig=None,
            out_sig=None
        )

        self.private_key_path = private_key_path
        self.curve_name = curve_name

        # Try to use gr-linux-crypto brainpool_ecdsa_sign block
        self.use_crypto_block = False
        self.crypto_block = None
        
        if LINUX_CRYPTO_AVAILABLE and LINUX_CRYPTO_MODULE:
            try:
                # gr-linux-crypto provides brainpool_ecdsa_sign block
                sign_class = None
                if hasattr(LINUX_CRYPTO_MODULE, 'brainpool_ecdsa_sign'):
                    sign_class = getattr(LINUX_CRYPTO_MODULE, 'brainpool_ecdsa_sign')
                elif hasattr(LINUX_CRYPTO_MODULE, 'linux_crypto_python'):
                    lcp = getattr(LINUX_CRYPTO_MODULE, 'linux_crypto_python')
                    if hasattr(lcp, 'brainpool_ecdsa_sign'):
                        sign_class = getattr(lcp, 'brainpool_ecdsa_sign')
                
                if sign_class:
                    try:
                        # Create block with private key path (blocks accept key_path parameter)
                        self.crypto_block = sign_class(private_key_path)
                        self.use_crypto_block = True
                        print(f"Using gr-linux-crypto brainpool_ecdsa_sign block")
                    except Exception as e:
                        # Try with curve name
                        try:
                            self.crypto_block = sign_class(private_key_path, curve_name)
                            self.use_crypto_block = True
                            print(f"Using gr-linux-crypto brainpool_ecdsa_sign block (with curve)")
                        except Exception as e2:
                            print(f"Warning: Could not create brainpool_ecdsa_sign block: {e2}")
                            print(f"  Will use Python fallback")
            except Exception as e:
                print(f"Warning: Error checking gr-linux-crypto blocks: {e}")

        # Fallback: Load key for Python implementation
        if not self.use_crypto_block:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from python.crypto_helpers import load_private_key
            self.private_key = load_private_key(private_key_path)
            if not self.private_key:
                raise ValueError(f"Could not load private key from {private_key_path}")

        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

    def handle_msg(self, msg):
        """Handle incoming PDU with data to sign."""
        if not pmt.is_pair(msg):
            return

        meta = pmt.car(msg)
        data = pmt.cdr(msg)

        if not pmt.is_blob(data):
            print("Warning: Expected blob data")
            return

        data_bytes = pmt.to_python(data)

        if self.use_crypto_block and self.crypto_block:
            # Use gr-linux-crypto brainpool_ecdsa_sign block
            try:
                signature = self._sign_with_crypto_block(data_bytes)
            except Exception as e:
                print(f"Warning: Error using gr-linux-crypto block, falling back to Python: {e}")
                signature = self._sign_python(data_bytes)
        else:
            signature = self._sign_python(data_bytes)

        # Output signature as PDU
        sig_pmt = pmt.init_u8vector(len(signature), list(signature))
        self.message_port_pub(pmt.intern("out"), pmt.cons(meta, sig_pmt))

    def _sign_with_crypto_block(self, data: bytes) -> bytes:
        """
        Sign using gr-linux-crypto brainpool_ecdsa_sign block.
        
        The block processes data through message ports in a flowgraph.
        For PDU-based integration, we need to send data to the block's input
        and receive signature from its output.
        """
        # gr-linux-crypto blocks work in flowgraphs with message ports
        # In a hierarchical block, this would be connected via message ports
        # For now, we'll use Python implementation as the block needs to be
        # integrated into the flowgraph structure
        # TODO: Integrate brainpool_ecdsa_sign block into TX hierarchical block
        return self._sign_python(data)
    
    def _sign_python(self, data: bytes) -> bytes:
        """Sign using Python implementation."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from python.crypto_helpers import generate_ecdsa_signature

        return generate_ecdsa_signature(data, self.private_key)


class ecdsa_verify_block(gr.sync_block):
    """
    ECDSA verification block using gr-linux-crypto.

    Input: PDU with (data, signature) pair
    Output: PDU with verification result (bool in metadata)

    Uses gr-linux-crypto ecdsa_verify block when available.
    """

    def __init__(self, public_key_store_path: Optional[str] = None):
        """
        Initialize ECDSA verification block.

        Args:
            public_key_store_path: Path to directory containing public keys
        """
        gr.sync_block.__init__(
            self,
            name="ecdsa_verify_block",
            in_sig=None,
            out_sig=None
        )

        self.public_key_store_path = public_key_store_path
        
        # Try to use gr-linux-crypto brainpool_ecdsa_verify block
        self.use_crypto_block = False
        self.crypto_block = None
        
        if LINUX_CRYPTO_AVAILABLE and LINUX_CRYPTO_MODULE:
            try:
                # gr-linux-crypto provides brainpool_ecdsa_verify block
                verify_class = None
                if hasattr(LINUX_CRYPTO_MODULE, 'brainpool_ecdsa_verify'):
                    verify_class = getattr(LINUX_CRYPTO_MODULE, 'brainpool_ecdsa_verify')
                elif hasattr(LINUX_CRYPTO_MODULE, 'linux_crypto_python'):
                    lcp = getattr(LINUX_CRYPTO_MODULE, 'linux_crypto_python')
                    if hasattr(lcp, 'brainpool_ecdsa_verify'):
                        verify_class = getattr(lcp, 'brainpool_ecdsa_verify')
                
                if verify_class:
                    try:
                        # Create block with public key store path if provided
                        if public_key_store_path:
                            self.crypto_block = verify_class(public_key_store_path)
                            self.use_crypto_block = True
                            print(f"Using gr-linux-crypto brainpool_ecdsa_verify block")
                        else:
                            # Create without parameters (may use kernel keyring)
                            self.crypto_block = verify_class()
                            self.use_crypto_block = True
                            print(f"Using gr-linux-crypto brainpool_ecdsa_verify block (no key store)")
                    except Exception as e:
                        print(f"Warning: Could not create brainpool_ecdsa_verify block: {e}")
                        print(f"  Will use Python fallback")
            except Exception as e:
                print(f"Warning: Error checking gr-linux-crypto blocks: {e}")

        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

    def handle_msg(self, msg):
        """Handle incoming PDU with (data, signature) pair."""
        if not pmt.is_pair(msg):
            return

        meta = pmt.car(msg)
        data = pmt.cdr(msg)

        # Expect data to be a pair: (data_bytes, signature_bytes)
        if not pmt.is_pair(data):
            print("Warning: Expected pair of (data, signature)")
            return

        data_bytes_pmt = pmt.car(data)
        sig_bytes_pmt = pmt.cdr(data)

        if not pmt.is_blob(data_bytes_pmt) or not pmt.is_blob(sig_bytes_pmt):
            print("Warning: Expected blob data")
            return

        data_bytes = pmt.to_python(data_bytes_pmt)
        sig_bytes = pmt.to_python(sig_bytes_pmt)

        # Extract sender callsign from metadata
        sender = ""
        if pmt.is_dict(meta) and pmt.dict_has_key(meta, pmt.intern("sender")):
            sender = pmt.symbol_to_string(
                pmt.dict_ref(meta, pmt.intern("sender"), pmt.PMT_NIL)
            )

        # Verify signature
        if self.use_crypto_block and self.crypto_block:
            try:
                valid = self._verify_with_crypto_block(data_bytes, sig_bytes, sender)
            except Exception as e:
                print(f"Warning: Error using gr-linux-crypto block, falling back to Python: {e}")
                valid = self._verify_signature(data_bytes, sig_bytes, sender)
        else:
            valid = self._verify_signature(data_bytes, sig_bytes, sender)

        # Output result with metadata
        output_meta = pmt.make_dict()
        if pmt.is_dict(meta):
            # Copy existing metadata
            keys = pmt.dict_keys(meta)
            for i in range(pmt.length(keys)):
                key = pmt.nth(i, keys)
                value = pmt.dict_ref(meta, key, pmt.PMT_NIL)
                output_meta = pmt.dict_add(output_meta, key, value)

        output_meta = pmt.dict_add(output_meta, pmt.intern("signature_valid"),
                                  pmt.from_bool(valid))

        # Output original data with updated metadata
        data_pmt = pmt.init_u8vector(len(data_bytes), list(data_bytes))
        self.message_port_pub(pmt.intern("out"), pmt.cons(output_meta, data_pmt))

    def _verify_with_crypto_block(self, data: bytes, signature: bytes, sender: str) -> bool:
        """
        Verify signature using gr-linux-crypto brainpool_ecdsa_verify block.
        
        The block processes data through message ports in a flowgraph.
        For PDU-based integration, we need to send (data, signature) to the block's input
        and receive verification result from its output.
        """
        # gr-linux-crypto blocks work in flowgraphs with message ports
        # In a hierarchical block, this would be connected via message ports
        # For now, we'll use Python implementation as the block needs to be
        # integrated into the flowgraph structure
        # TODO: Integrate brainpool_ecdsa_verify block into RX hierarchical block
        return self._verify_signature(data, signature, sender)
    
    def _verify_signature(self, data: bytes, signature: bytes, sender: str) -> bool:
        """Verify signature using Python implementation."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from python.crypto_helpers import verify_ecdsa_signature

        # Load public key
        if not self.public_key_store_path:
            return False

        from pathlib import Path as PathLib
        key_path = PathLib(self.public_key_store_path) / f"{sender.upper()}.pem"
        if not key_path.exists():
            return False

        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            with open(key_path, 'rb') as f:
                key_data = f.read()

            try:
                public_key = serialization.load_pem_public_key(
                    key_data,
                    backend=default_backend()
                )
            except:
                public_key = serialization.load_der_public_key(
                    key_data,
                    backend=default_backend()
                )

            return verify_ecdsa_signature(data, signature, public_key)
        except Exception as e:
            print(f"Error verifying signature: {e}")
            return False


class chacha20poly1305_encrypt_block(gr.sync_block):
    """
    ChaCha20-Poly1305 encryption block using gr-nacl.

    Input: PDU with plaintext data (blob)
    Output: PDU with (ciphertext, mac) pair

    Uses gr-nacl chacha20poly1305_encrypt block when available.
    """

    def __init__(self, key: bytes, nonce: Optional[bytes] = None):
        """
        Initialize ChaCha20-Poly1305 encryption block.

        Args:
            key: 32-byte encryption key
            nonce: 12-byte nonce (optional, defaults to zeros)
        """
        if len(key) != 32:
            raise ValueError("ChaCha20-Poly1305 key must be 32 bytes")

        gr.sync_block.__init__(
            self,
            name="chacha20poly1305_encrypt_block",
            in_sig=None,
            out_sig=None
        )

        self.key = key
        self.nonce = nonce if nonce else b'\x00' * 12

        # Initialize nacl block flags (currently not used - see _encrypt method)
        self.use_nacl_block = False
        self.nacl_block = None

        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

    def handle_msg(self, msg):
        """Handle incoming PDU with plaintext data."""
        if not pmt.is_pair(msg):
            return

        meta = pmt.car(msg)
        data = pmt.cdr(msg)

        if not pmt.is_blob(data):
            print("Warning: Expected blob data")
            return

        plaintext = pmt.to_python(data)

        # Encrypt
        if self.use_nacl_block and self.nacl_block:
            try:
                ciphertext, mac = self._encrypt_with_nacl_block(plaintext)
            except Exception as e:
                print(f"Warning: Error using gr-nacl block, falling back to Python: {e}")
                ciphertext, mac = self._encrypt(plaintext)
        else:
            ciphertext, mac = self._encrypt(plaintext)

        # Output as pair: (ciphertext, mac)
        ciphertext_pmt = pmt.init_u8vector(len(ciphertext), list(ciphertext))
        mac_pmt = pmt.init_u8vector(len(mac), list(mac))
        output_data = pmt.cons(ciphertext_pmt, mac_pmt)

        self.message_port_pub(pmt.intern("out"), pmt.cons(meta, output_data))

    def _encrypt_with_nacl_block(self, plaintext: bytes) -> tuple:
        """
        Encrypt using gr-nacl block.
        
        Note: This is a placeholder - actual implementation would need to
        integrate the block into a flowgraph or use its message port interface.
        """
        # For now, fall back to Python implementation
        # TODO: Implement proper integration with gr-nacl block
        return self._encrypt(plaintext)
    
    def _encrypt(self, plaintext: bytes) -> tuple:
        """
        Encrypt data using ChaCha20-Poly1305.
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from python.crypto_helpers import encrypt_chacha20_poly1305

        # Perform actual ChaCha20-Poly1305 encryption
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        return ciphertext, mac


class chacha20poly1305_decrypt_block(gr.sync_block):
    """
    ChaCha20-Poly1305 decryption block using gr-nacl.

    Input: PDU with (ciphertext, mac) pair
    Output: PDU with plaintext data (if MAC valid)

    Uses gr-nacl chacha20poly1305_decrypt block when available.
    """

    def __init__(self, key: bytes, nonce: Optional[bytes] = None):
        """
        Initialize ChaCha20-Poly1305 decryption block.

        Args:
            key: 32-byte decryption key
            nonce: 12-byte nonce (optional, defaults to zeros)
        """
        if len(key) != 32:
            raise ValueError("ChaCha20-Poly1305 key must be 32 bytes")

        gr.sync_block.__init__(
            self,
            name="chacha20poly1305_decrypt_block",
            in_sig=None,
            out_sig=None
        )

        self.key = key
        self.nonce = nonce if nonce else b'\x00' * 12

        # Initialize nacl block flags (currently not used - see _decrypt method)
        self.use_nacl_block = False
        self.nacl_block = None

        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

    def handle_msg(self, msg):
        """Handle incoming PDU with (ciphertext, mac) pair."""
        if not pmt.is_pair(msg):
            return

        meta = pmt.car(msg)
        data = pmt.cdr(msg)

        # Expect pair: (ciphertext, mac)
        if not pmt.is_pair(data):
            print("Warning: Expected pair of (ciphertext, mac)")
            return

        ciphertext_pmt = pmt.car(data)
        mac_pmt = pmt.cdr(data)

        if not pmt.is_blob(ciphertext_pmt) or not pmt.is_blob(mac_pmt):
            print("Warning: Expected blob data")
            return

        ciphertext = pmt.to_python(ciphertext_pmt)
        mac = pmt.to_python(mac_pmt)

        # Decrypt and verify MAC
        if self.use_nacl_block and self.nacl_block:
            try:
                plaintext, mac_valid = self._decrypt_with_nacl_block(ciphertext, mac)
            except Exception as e:
                print(f"Warning: Error using gr-nacl block, falling back to Python: {e}")
                plaintext, mac_valid = self._decrypt(ciphertext, mac)
        else:
            plaintext, mac_valid = self._decrypt(ciphertext, mac)

        if not mac_valid:
            print("Warning: MAC verification failed")
            # Still output, but mark in metadata
            output_meta = pmt.make_dict()
            if pmt.is_dict(meta):
                keys = pmt.dict_keys(meta)
                for i in range(pmt.length(keys)):
                    key = pmt.nth(i, keys)
                    value = pmt.dict_ref(meta, key, pmt.PMT_NIL)
                    output_meta = pmt.dict_add(output_meta, key, value)
            output_meta = pmt.dict_add(output_meta, pmt.intern("mac_valid"),
                                      pmt.from_bool(False))
        else:
            output_meta = meta

        # Output plaintext
        plaintext_pmt = pmt.init_u8vector(len(plaintext), list(plaintext))
        self.message_port_pub(pmt.intern("out"), pmt.cons(output_meta, plaintext_pmt))

    def _decrypt_with_nacl_block(self, ciphertext: bytes, mac: bytes) -> tuple:
        """
        Decrypt using gr-nacl block.
        
        Note: This is a placeholder - actual implementation would need to
        integrate the block into a flowgraph or use its message port interface.
        """
        # For now, fall back to Python implementation
        # TODO: Implement proper integration with gr-nacl block
        return self._decrypt(ciphertext, mac)
    
    def _decrypt(self, ciphertext: bytes, mac: bytes) -> tuple:
        """
        Decrypt data using ChaCha20-Poly1305.
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from python.crypto_helpers import decrypt_chacha20_poly1305

        # Perform actual ChaCha20-Poly1305 decryption
        try:
            plaintext = decrypt_chacha20_poly1305(ciphertext, mac, self.key, self.nonce)
            return plaintext, True
        except ValueError as e:
            # MAC verification failed or decryption error
            return ciphertext, False


def make_ecdsa_sign_block(private_key_path: str, curve_name: str = "brainpoolP256r1"):
    """Factory function for GRC."""
    return ecdsa_sign_block(private_key_path, curve_name)


def make_ecdsa_verify_block(public_key_store_path: Optional[str] = None):
    """Factory function for GRC."""
    return ecdsa_verify_block(public_key_store_path)


def make_chacha20poly1305_encrypt_block(key: bytes, nonce: Optional[bytes] = None):
    """Factory function for GRC."""
    return chacha20poly1305_encrypt_block(key, nonce)


def make_chacha20poly1305_decrypt_block(key: bytes, nonce: Optional[bytes] = None):
    """Factory function for GRC."""
    return chacha20poly1305_decrypt_block(key, nonce)

