#!/usr/bin/env python3
"""
Critical functionality tests that catch common "looks plausible but doesn't work" issues.

These tests are designed to catch:
1. Code that passes through data instead of processing it
2. Code that only does partial processing (e.g., thresholding instead of decoding)
3. Code that creates objects but never uses them
4. Code that has the right structure but wrong implementation
"""

import unittest
import numpy as np
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestLDPCNotPassthrough(unittest.TestCase):
    """
    CRITICAL: Test that LDPC encoding is not just passthrough.
    
    This catches the bug where encoding just returns input unchanged.
    """
    
    def test_encoder_output_different_from_input(self):
        """Test that encoder output is actually different from input."""
        try:
            from python.frame_aware_ldpc import frame_aware_ldpc_encoder
            
            # Create encoder
            auth_matrix = os.path.join(os.path.dirname(__file__), '..', 'ldpc_matrices', 'ldpc_auth_1536_512.alist')
            voice_matrix = os.path.join(os.path.dirname(__file__), '..', 'ldpc_matrices', 'ldpc_voice_576_384.alist')
            
            if not os.path.exists(auth_matrix) or not os.path.exists(voice_matrix):
                self.skipTest("Matrix files not found")
            
            encoder = frame_aware_ldpc_encoder(auth_matrix, voice_matrix)
            
            # Test with voice frame (48 bytes input)
            import secrets
            test_input = secrets.token_bytes(48)
            input_array = np.frombuffer(test_input, dtype=np.uint8)
            
            # Create output buffer (should be larger for encoded output)
            output_array = np.zeros(200, dtype=np.uint8)  # Large enough for encoded output
            
            # Process
            result = encoder.work([input_array], [output_array])
            
            # CRITICAL: Output should be different from input (unless it's a no-op)
            # For rate 2/3 code, 48 bytes (384 bits) should encode to 72 bytes (576 bits)
            output_bytes = output_array[:result].tobytes()
            
            # Output should be longer than input for rate 2/3 encoding
            # (48 bytes -> 72 bytes)
            if len(output_bytes) > len(test_input):
                # Good - encoding happened
                self.assertNotEqual(
                    output_bytes[:len(test_input)],
                    test_input,
                    "Encoded output should be different from input (even first part)"
                )
            else:
                # This might indicate passthrough - check if it's identical
                if output_bytes == test_input:
                    self.fail(
                        "CRITICAL: Encoder appears to be passing through data unchanged. "
                        "This indicates encoding is not working."
                    )
        
        except ImportError as e:
            self.skipTest(f"Could not import encoder: {e}")


class TestLDPCNotJustThresholding(unittest.TestCase):
    """
    CRITICAL: Test that LDPC decoding is not just thresholding.
    
    This catches the bug where decoding just does (soft > 0) instead of actual decoding.
    """
    
    def test_decoder_corrects_errors(self):
        """Test that decoder can correct errors, not just threshold."""
        try:
            from python.ldpc_utils import load_alist_matrix, compute_generator_matrix, ldpc_encode, ldpc_decode_soft
            
            matrix_file = os.path.join(os.path.dirname(__file__), '..', 'ldpc_matrices', 'ldpc_voice_576_384.alist')
            
            if not os.path.exists(matrix_file):
                self.skipTest("Matrix file not found")
            
            H, n, k = load_alist_matrix(matrix_file)
            G = compute_generator_matrix(H)
            
            # Create test data
            info_bits = np.random.randint(0, 2, size=k, dtype=np.uint8)
            
            # Encode
            codeword = ldpc_encode(info_bits, G)
            
            # Create soft decisions with errors
            # Introduce errors: flip some bits in codeword
            corrupted = codeword.copy()
            error_count = min(10, n // 20)  # Introduce ~5% errors
            error_positions = np.random.choice(n, size=error_count, replace=False)
            for pos in error_positions:
                corrupted[pos] = 1 - corrupted[pos]
            
            # Create soft decisions: correct bits have high confidence,
            # error bits have wrong/uncertain confidence
            soft_bits = np.zeros(n, dtype=np.float32)
            for i in range(n):
                if corrupted[i] == 0:
                    if i in error_positions:
                        soft_bits[i] = -2.0  # Wrong: says bit is 1
                    else:
                        soft_bits[i] = 5.0  # Correct: says bit is 0
                else:
                    if i in error_positions:
                        soft_bits[i] = 2.0  # Wrong: says bit is 0
                    else:
                        soft_bits[i] = -5.0  # Correct: says bit is 1
            
            # Decode
            decoded = ldpc_decode_soft(soft_bits, H, max_iter=50)
            
            # Simple thresholding would get many errors
            # Actual decoding should correct most errors
            threshold_result = (soft_bits > 0).astype(np.uint8)[:k]
            threshold_errors = np.sum(threshold_result != info_bits)
            decoded_errors = np.sum(decoded != info_bits)
            
            # Decoding should perform better than simple thresholding
            # (or at least not worse)
            self.assertLessEqual(
                decoded_errors,
                threshold_errors,
                f"Decoding should correct errors better than thresholding. "
                f"Threshold errors: {threshold_errors}, Decoded errors: {decoded_errors}"
            )
            
            # With moderate errors, decoding should recover most bits
            self.assertLess(
                decoded_errors,
                k * 0.2,  # Less than 20% errors
                f"Decoding should correct most errors. Got {decoded_errors}/{k} errors"
            )
        
        except ImportError as e:
            self.skipTest(f"Could not import decoder: {e}")


class TestEncryptionNotJustMAC(unittest.TestCase):
    """
    CRITICAL: Test that encryption actually encrypts, not just computes MAC.
    
    This catches the bug where encryption returns (plaintext, mac) instead of (ciphertext, mac).
    """
    
    def test_encryption_changes_data(self):
        """Test that encryption actually changes the data."""
        try:
            from python.crypto_helpers import encrypt_chacha20_poly1305
            
            key = b'\x00' * 32  # Test key
            nonce = b'\x00' * 12  # Test nonce
            plaintext = b"This is a test message that must be encrypted"
            
            ciphertext, mac = encrypt_chacha20_poly1305(plaintext, key, nonce)
            
            # CRITICAL: Ciphertext must be different from plaintext
            self.assertNotEqual(
                ciphertext,
                plaintext,
                "CRITICAL: Encryption must change data. If ciphertext == plaintext, encryption is not working."
            )
            
            # Ciphertext should have same length
            self.assertEqual(len(ciphertext), len(plaintext))
            
            # MAC should be 16 bytes
            self.assertEqual(len(mac), 16)
        
        except ImportError as e:
            self.skipTest(f"Could not import encryption: {e}")


class TestDecryptionActuallyDecrypts(unittest.TestCase):
    """
    CRITICAL: Test that decryption actually decrypts, not just verifies MAC.
    
    This catches the bug where decryption returns ciphertext as plaintext.
    """
    
    def test_decryption_recovers_plaintext(self):
        """Test that decryption recovers the original plaintext."""
        try:
            from python.crypto_helpers import encrypt_chacha20_poly1305, decrypt_chacha20_poly1305
            
            key = b'\x00' * 32
            nonce = b'\x00' * 12
            plaintext = b"Original message that must be recovered"
            
            # Encrypt
            ciphertext, mac = encrypt_chacha20_poly1305(plaintext, key, nonce)
            
            # Decrypt
            decrypted = decrypt_chacha20_poly1305(ciphertext, mac, key, nonce)
            
            # CRITICAL: Decrypted must equal original plaintext
            self.assertEqual(
                decrypted,
                plaintext,
                "CRITICAL: Decryption must recover original plaintext. "
                "If decrypted != plaintext, decryption is not working."
            )
            
            # Decrypted should NOT equal ciphertext
            self.assertNotEqual(
                decrypted,
                ciphertext,
                "CRITICAL: Decrypted data should not equal ciphertext. "
                "If decrypted == ciphertext, decryption is not working."
            )
        
        except ImportError as e:
            self.skipTest(f"Could not import decryption: {e}")


if __name__ == '__main__':
    unittest.main()

