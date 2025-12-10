#!/usr/bin/env python3
"""
Cryptographic helpers for gr-sleipnir superframe.

Provides ECDSA signature generation (BrainpoolP256r1) and
ChaCha20-Poly1305 MAC computation.

Uses cryptography library (available) for all operations.
"""

import hashlib
import hmac
from typing import Optional

# Use cryptography library (confirmed available)
try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    print("Warning: cryptography library not available. Using HMAC fallback for MAC.")


def load_private_key(key_path: str) -> Optional[object]:
    """
    Load private key from file.

    Supports:
    - PEM format (ECDSA private key, BrainpoolP256r1 preferred)
    - DER format

    Args:
        key_path: Path to private key file

    Returns:
        Private key object (from cryptography library)
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        print("Error: cryptography library not available for loading keys")
        return None

    try:
        with open(key_path, 'rb') as f:
            key_data = f.read()

        # Try PEM format first
        try:
            private_key = serialization.load_pem_private_key(
                key_data,
                password=None,
                backend=default_backend()
            )
            # Verify it's an EC key (for BrainpoolP256r1)
            if isinstance(private_key, ec.EllipticCurvePrivateKey):
                return private_key
            else:
                print("Warning: Key is not an EC private key")
                return private_key
        except:
            # Try DER format
            try:
                private_key = serialization.load_der_private_key(
                    key_data,
                    password=None,
                    backend=default_backend()
                )
                if isinstance(private_key, ec.EllipticCurvePrivateKey):
                    return private_key
                else:
                    print("Warning: Key is not an EC private key")
                    return private_key
            except Exception as e:
                raise ValueError(f"Key file is not in PEM or DER format: {e}")
    except Exception as e:
        print(f"Error loading private key: {e}")
        return None


def generate_ecdsa_signature(data: bytes, private_key: object) -> bytes:
    """
    Generate ECDSA signature using BrainpoolP256r1.

    Args:
        data: Data to sign
        private_key: Private key object (from cryptography library)

    Returns:
        64-byte signature (r + s, each 32 bytes, concatenated)
        The DER-encoded signature from cryptography is decoded to get r and s,
        then concatenated as 64 bytes for storage in frame 0.
    """
    # Hash the data first (SHA-256)
    data_hash = hashlib.sha256(data).digest()

    if not CRYPTOGRAPHY_AVAILABLE:
        print("Error: cryptography library not available for ECDSA signing")
        return b'\x00' * 64

    try:
        # Sign with ECDSA using BrainpoolP256r1
        # The private_key should be loaded with BrainpoolP256r1 curve
        signature_der = private_key.sign(
            data_hash,
            ec.ECDSA(hashes.SHA256())
        )

        # Decode DER-encoded signature to get r and s values
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        r, s = decode_dss_signature(signature_der)
        
        # Convert r and s to 32-byte big-endian integers
        r_bytes = r.to_bytes(32, 'big')
        s_bytes = s.to_bytes(32, 'big')
        
        # Concatenate r + s = 64 bytes total
        return r_bytes + s_bytes
    except Exception as e:
        print(f"Error signing with cryptography library: {e}")
        # Return zeros as fallback
        return b'\x00' * 64


def compute_chacha20_mac(data: bytes, key: bytes) -> bytes:
    """
    Compute ChaCha20-Poly1305 MAC (authentication tag).

    Args:
        data: Data to authenticate
        key: 32-byte ChaCha20-Poly1305 key

    Returns:
        16-byte Poly1305 authentication tag
    """
    if len(key) != 32:
        raise ValueError("ChaCha20-Poly1305 key must be 32 bytes")

    if CRYPTOGRAPHY_AVAILABLE:
        try:
            # Use cryptography library for ChaCha20-Poly1305
            nonce = b'\x00' * 12  # 96-bit nonce (zero for MAC-only)
            chacha = ChaCha20Poly1305(key)
            ciphertext = chacha.encrypt(nonce, data, None)
            # Return last 16 bytes (Poly1305 tag)
            return ciphertext[-16:]
        except Exception as e:
            print(f"Error computing MAC with cryptography library: {e}")
            # Fall through to fallback

    # Fallback: Use HMAC-SHA256 truncated to 16 bytes
    print("Warning: Using HMAC-SHA256 as fallback for ChaCha20-Poly1305 MAC")
    mac = hmac.new(key, data, hashlib.sha256).digest()
    return mac[:16]


def get_callsign_bytes(callsign: str) -> bytes:
    """
    Convert callsign to 5-byte format.

    Args:
        callsign: Callsign string (max 5 characters)

    Returns:
        5-byte callsign (padded with spaces, uppercase)
    """
    callsign = callsign.upper()[:5].ljust(5)
    return callsign.encode('ascii', errors='ignore')[:5].ljust(5, b' ')


def verify_ecdsa_signature(data: bytes, signature: bytes, public_key: object) -> bool:
    """
    Verify ECDSA signature.

    Args:
        data: Original data
        signature: Signature to verify (64 bytes r+s, or truncated/padded version)
        public_key: Public key object (from cryptography library)

    Returns:
        True if signature is valid, False otherwise
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        print("Error: cryptography library not available for ECDSA verification")
        return False

    try:
        # Hash the data first (SHA-256) - must match how signature was generated
        data_hash = hashlib.sha256(data).digest()

        # Handle truncated signatures: if signature is less than 64 bytes, pad with zeros
        # This handles cases where the signature was truncated to fit frame size
        if len(signature) < 64:
            # Pad to 64 bytes (truncated signatures can't be fully verified, but we try)
            # Note: This is a limitation - full verification requires full 64-byte signature
            signature_padded = signature + b'\x00' * (64 - len(signature))
        elif len(signature) > 64:
            # Truncate to 64 bytes (take first 64 bytes)
            signature_padded = signature[:64]
        else:
            signature_padded = signature

        # Extract r and s from concatenated signature (each 32 bytes)
        r_bytes = signature_padded[:32]
        s_bytes = signature_padded[32:64]
        
        # Convert bytes to integers
        r = int.from_bytes(r_bytes, 'big')
        s = int.from_bytes(s_bytes, 'big')
        
        # Encode r and s back to DER format for verification
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        signature_der = encode_dss_signature(r, s)

        # Verify signature using public key
        public_key.verify(
            signature_der,
            data_hash,
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except Exception as e:
        # Verification failed (invalid signature, wrong data, etc.)
        # Don't print error for every failed verification (too verbose)
        # Only print for debugging if needed
        return False


def verify_chacha20_mac(data: bytes, mac: bytes, key: bytes) -> bool:
    """
    Verify ChaCha20-Poly1305 MAC.

    Args:
        data: Original data
        mac: MAC to verify (16 bytes)
        key: 32-byte ChaCha20-Poly1305 key

    Returns:
        True if MAC is valid, False otherwise
    """
    computed_mac = compute_chacha20_mac(data, key)
    return computed_mac == mac

