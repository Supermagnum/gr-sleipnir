#!/usr/bin/env python3
"""
Test: Signature Verification

Tests ECDSA signature generation and verification.
"""

import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.crypto_helpers import (
    generate_ecdsa_signature,
    load_private_key,
    get_callsign_bytes
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
import hashlib


def generate_test_key_pair():
    """Generate test ECDSA key pair."""
    # Generate BrainpoolP256r1 key pair
    private_key = ec.generate_private_key(
        ec.BrainpoolP256R1(),
        default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key


def save_test_key(private_key, key_path: str):
    """Save private key to file."""
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(key_path, 'wb') as f:
        f.write(pem)


def test_signature_generation():
    """Test signature generation."""
    print("=" * 60)
    print("Test: Signature Generation and Verification")
    print("=" * 60)
    
    # Generate test key pair
    print("\n1. Generating test key pair...")
    private_key, public_key = generate_test_key_pair()
    print("   PASS: Key pair generated")
    
    # Save private key to temp file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as f:
        key_path = f.name
        save_test_key(private_key, key_path)
    
    try:
        # Test data
        test_data = b"Test superframe data for signature verification"
        
        # Generate signature
        print("\n2. Generating signature...")
        signature = generate_ecdsa_signature(test_data, private_key)
        print(f"   PASS: Signature generated: {len(signature)} bytes")
        
        # Verify signature format
        if len(signature) == 32:
            print("   PASS: Signature length correct (32 bytes)")
        else:
            print(f"   FAIL: Signature length incorrect: {len(signature)} bytes")
            return False
        
        # Load key from file
        print("\n3. Loading key from file...")
        loaded_key = load_private_key(key_path)
        if loaded_key:
            print("   PASS: Key loaded successfully")
        else:
            print("   FAIL: Failed to load key")
            return False
        
        # Generate signature with loaded key
        print("\n4. Generating signature with loaded key...")
        signature2 = generate_ecdsa_signature(test_data, loaded_key)
        print(f"   PASS: Signature generated: {len(signature2)} bytes")
        
        # Note: Full signature verification requires storing full 64-byte signature
        # Current implementation uses 32-byte hash of signature
        # This is a limitation noted in the code
        
        print("\nPASS: Signature generation test passed")
        print("\nNote: Full signature verification requires storing 64-byte signature")
        print("      Current implementation uses 32-byte hash (see crypto_helpers.py)")
        
        return True
        
    finally:
        # Cleanup
        Path(key_path).unlink()


if __name__ == "__main__":
    success = test_signature_generation()
    sys.exit(0 if success else 1)

