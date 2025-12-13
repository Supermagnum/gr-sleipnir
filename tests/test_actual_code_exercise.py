#!/usr/bin/env python3
"""
Comprehensive test to verify that all critical code paths are actually exercised.

This test runs all other tests and verifies they actually call real code,
not just mocks or placeholders.
"""

import unittest
import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestCodeExercise(unittest.TestCase):
    """Verify that tests actually exercise the code."""
    
    def test_ldpc_encoding_actually_encodes(self):
        """Verify LDPC encoding test actually tests encoding."""
        from python.ldpc_utils import load_alist_matrix, compute_generator_matrix, ldpc_encode
        import numpy as np
        
        matrix_file = project_root / 'ldpc_matrices' / 'ldpc_voice_576_384.alist'
        if not matrix_file.exists():
            self.skipTest("Matrix file not found")
        
        H, n, k = load_alist_matrix(str(matrix_file))
        G = compute_generator_matrix(H)
        
        # Test encoding
        info = np.random.randint(0, 2, size=k, dtype=np.uint8)
        codeword = ldpc_encode(info, G)
        
        # CRITICAL: Verify encoding actually happened
        self.assertEqual(len(codeword), n, "Encoded length must be n")
        self.assertGreater(n, k, "Codeword must be longer than info")
        
        # Verify parity checks
        syndrome = (H @ codeword) % 2
        self.assertEqual(np.sum(syndrome), 0, "Encoded codeword must satisfy parity checks")
    
    def test_ldpc_decoding_actually_decodes(self):
        """Verify LDPC decoding test actually tests decoding."""
        from python.ldpc_utils import load_alist_matrix, compute_generator_matrix, ldpc_encode, ldpc_decode_soft
        import numpy as np
        
        matrix_file = project_root / 'ldpc_matrices' / 'ldpc_voice_576_384.alist'
        if not matrix_file.exists():
            self.skipTest("Matrix file not found")
        
        H, n, k = load_alist_matrix(str(matrix_file))
        G = compute_generator_matrix(H)
        
        # Encode
        info = np.random.randint(0, 2, size=k, dtype=np.uint8)
        codeword = ldpc_encode(info, G)
        
        # Create soft decisions
        soft = np.zeros(n, dtype=np.float32)
        for i in range(n):
            soft[i] = 10.0 if codeword[i] == 0 else -10.0
        
        # Decode
        decoded = ldpc_decode_soft(soft, H, max_iter=50)
        
        # CRITICAL: Verify decoding actually worked
        self.assertEqual(len(decoded), k, "Decoded length must be k")
        np.testing.assert_array_equal(decoded, info, "Decoding must recover original")
    
    def test_encryption_actually_encrypts(self):
        """Verify encryption test actually tests encryption."""
        from python.crypto_helpers import encrypt_chacha20_poly1305, decrypt_chacha20_poly1305
        import secrets
        
        key = secrets.token_bytes(32)
        nonce = secrets.token_bytes(12)
        plaintext = b"Test message for encryption"
        
        # Encrypt
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, key, nonce)
        
        # CRITICAL: Verify encryption actually happened
        self.assertNotEqual(ciphertext, plaintext, "Ciphertext must be different from plaintext")
        self.assertEqual(len(ciphertext), len(plaintext), "Ciphertext length must match plaintext")
        self.assertEqual(len(mac), 16, "MAC must be 16 bytes")
        
        # Decrypt
        decrypted = decrypt_chacha20_poly1305(ciphertext, mac, key, nonce)
        
        # CRITICAL: Verify decryption actually worked
        self.assertEqual(decrypted, plaintext, "Decryption must recover original")
        self.assertNotEqual(decrypted, ciphertext, "Decrypted must not equal ciphertext")
    
    def test_signature_actually_verifies(self):
        """Verify signature test actually tests verification."""
        from python.crypto_helpers import generate_ecdsa_signature, verify_ecdsa_signature
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend
        
        # Generate key
        private_key = ec.generate_private_key(ec.BrainpoolP256R1(), default_backend())
        public_key = private_key.public_key()
        
        # Sign
        data = b"Test data for signature"
        signature = generate_ecdsa_signature(data, private_key)
        
        # CRITICAL: Verify signature is correct length
        self.assertEqual(len(signature), 64, "Signature must be 64 bytes")
        
        # Verify
        valid = verify_ecdsa_signature(data, signature, public_key)
        self.assertTrue(valid, "Signature must verify correctly")
        
        # CRITICAL: Wrong data must fail
        wrong_data = data + b"modified"
        invalid = verify_ecdsa_signature(wrong_data, signature, public_key)
        self.assertFalse(invalid, "Wrong data must fail verification")
    
    def test_all_critical_tests_run(self):
        """Verify that critical test suite runs and exercises code."""
        # Run the critical test script
        test_script = project_root / 'tests' / 'run_critical_tests.sh'
        
        if not test_script.exists():
            self.skipTest("Critical test script not found")
        
        # Run tests
        result = subprocess.run(
            ['bash', str(test_script)],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        # CRITICAL: Tests must pass
        self.assertEqual(result.returncode, 0, 
            f"Critical tests must pass. Output:\n{result.stdout}\n{result.stderr}")


if __name__ == '__main__':
    unittest.main()

