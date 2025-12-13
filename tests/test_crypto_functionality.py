#!/usr/bin/env python3
"""
Unit tests for cryptographic functionality.

These tests verify that encryption and decryption actually work,
not just compute MACs or pass through data.
"""

import unittest
import os
import sys
import secrets

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from python.crypto_helpers import (
    encrypt_chacha20_poly1305,
    decrypt_chacha20_poly1305,
    compute_chacha20_mac
)


class TestChaCha20Encryption(unittest.TestCase):
    """Test that ChaCha20 encryption actually encrypts data."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.key = secrets.token_bytes(32)
        self.nonce = secrets.token_bytes(12)
    
    def test_encryption_changes_data(self):
        """
        CRITICAL TEST: Encryption must change the data.
        
        If encryption just passes through or only computes MAC, this will fail.
        """
        plaintext = b"This is a test message that should be encrypted"
        
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        
        # CRITICAL: Encrypted data must be different from plaintext
        self.assertNotEqual(
            ciphertext,
            plaintext,
            "Encrypted data must be different from plaintext"
        )
        
        # Encrypted data should have same length as plaintext
        self.assertEqual(
            len(ciphertext),
            len(plaintext),
            "Encrypted data must have same length as plaintext"
        )
        
        # MAC should be 16 bytes
        self.assertEqual(
            len(mac),
            16,
            "Poly1305 MAC must be 16 bytes"
        )
    
    def test_encryption_different_plaintexts_different_ciphertexts(self):
        """
        CRITICAL TEST: Different plaintexts must produce different ciphertexts.
        
        If encryption is deterministic without nonce changes, similar plaintexts
        might produce similar ciphertexts, which is a security issue.
        """
        plaintext1 = b"Message one"
        plaintext2 = b"Message two"
        
        ciphertext1, mac1 = encrypt_chacha20_poly1305(plaintext1, self.key, self.nonce)
        ciphertext2, mac2 = encrypt_chacha20_poly1305(plaintext2, self.key, self.nonce)
        
        # Ciphertexts should be different
        self.assertNotEqual(
            ciphertext1,
            ciphertext2,
            "Different plaintexts must produce different ciphertexts"
        )
        
        # MACs should also be different
        self.assertNotEqual(
            mac1,
            mac2,
            "Different plaintexts must produce different MACs"
        )
    
    def test_encryption_different_nonces_different_ciphertexts(self):
        """Test that different nonces produce different ciphertexts."""
        plaintext = b"Same message, different nonces"
        nonce1 = secrets.token_bytes(12)
        nonce2 = secrets.token_bytes(12)
        
        # Ensure nonces are different
        self.assertNotEqual(nonce1, nonce2)
        
        ciphertext1, mac1 = encrypt_chacha20_poly1305(plaintext, self.key, nonce1)
        ciphertext2, mac2 = encrypt_chacha20_poly1305(plaintext, self.key, nonce2)
        
        # Ciphertexts should be different (with high probability)
        self.assertNotEqual(
            ciphertext1,
            ciphertext2,
            "Same plaintext with different nonces must produce different ciphertexts"
        )
    
    def test_encryption_produces_random_looking_output(self):
        """
        CRITICAL TEST: Encrypted data should look random.
        
        If encryption just passes through or does simple transformations,
        patterns in plaintext will be visible in ciphertext.
        """
        # Use plaintext with clear patterns
        plaintext = b"AAAA" * 100  # 400 bytes of repeated pattern
        
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        
        # Check that ciphertext doesn't have obvious patterns
        # Count byte frequencies - should be roughly uniform for good encryption
        byte_counts = [0] * 256
        for byte in ciphertext:
            byte_counts[byte] += 1
        
        # No single byte should dominate (chi-square test would be better, but this is simpler)
        max_count = max(byte_counts)
        total_bytes = len(ciphertext)
        max_frequency = max_count / total_bytes
        
        # For 400 bytes, no byte should appear more than ~5% of the time by chance
        # (allowing some margin for randomness)
        self.assertLess(
            max_frequency,
            0.15,  # 15% threshold
            f"Encrypted data should look random. Most frequent byte appears {max_frequency*100:.1f}% of the time"
        )
    
    def test_encryption_deterministic_with_same_nonce(self):
        """Test that encryption is deterministic with same key and nonce."""
        plaintext = b"Deterministic test message"
        
        ciphertext1, mac1 = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        ciphertext2, mac2 = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        
        # Should produce identical output with same key and nonce
        self.assertEqual(
            ciphertext1,
            ciphertext2,
            "Encryption must be deterministic with same key and nonce"
        )
        self.assertEqual(
            mac1,
            mac2,
            "MAC must be deterministic with same key and nonce"
        )


class TestChaCha20Decryption(unittest.TestCase):
    """Test that ChaCha20 decryption actually decrypts data."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.key = secrets.token_bytes(32)
        self.nonce = secrets.token_bytes(12)
    
    def test_decryption_recovers_plaintext(self):
        """
        CRITICAL TEST: Decryption must recover original plaintext.
        
        If decryption just returns ciphertext or only verifies MAC,
        this will fail.
        """
        plaintext = b"This is the original message that must be recovered"
        
        # Encrypt
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        
        # Decrypt
        decrypted = decrypt_chacha20_poly1305(ciphertext, mac, self.key, self.nonce)
        
        # Must recover original plaintext
        self.assertEqual(
            decrypted,
            plaintext,
            "Decryption must recover original plaintext"
        )
    
    def test_decryption_fails_with_wrong_mac(self):
        """
        CRITICAL TEST: Decryption must fail with wrong MAC.
        
        If decryption doesn't verify MAC, it's a security vulnerability.
        """
        plaintext = b"Test message"
        
        # Encrypt
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        
        # Try to decrypt with wrong MAC
        wrong_mac = bytes([b ^ 0xFF for b in mac])  # Flip all bits
        
        with self.assertRaises(ValueError):
            decrypt_chacha20_poly1305(ciphertext, wrong_mac, self.key, self.nonce)
    
    def test_decryption_fails_with_wrong_key(self):
        """Test that decryption fails with wrong key."""
        plaintext = b"Test message"
        wrong_key = secrets.token_bytes(32)
        
        # Encrypt with correct key
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        
        # Try to decrypt with wrong key
        with self.assertRaises(ValueError):
            decrypt_chacha20_poly1305(ciphertext, mac, wrong_key, self.nonce)
    
    def test_decryption_fails_with_wrong_nonce(self):
        """Test that decryption fails with wrong nonce."""
        plaintext = b"Test message"
        wrong_nonce = secrets.token_bytes(12)
        
        # Encrypt with correct nonce
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        
        # Try to decrypt with wrong nonce
        with self.assertRaises(ValueError):
            decrypt_chacha20_poly1305(ciphertext, mac, self.key, wrong_nonce)
    
    def test_decryption_fails_with_modified_ciphertext(self):
        """
        CRITICAL TEST: Decryption must fail if ciphertext is modified.
        
        Even if MAC is correct, modified ciphertext should fail.
        """
        plaintext = b"Test message"
        
        # Encrypt
        ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
        
        # Modify ciphertext
        modified_ciphertext = bytearray(ciphertext)
        modified_ciphertext[0] ^= 0x01  # Flip one bit
        
        # Decryption should fail (MAC won't verify)
        with self.assertRaises(ValueError):
            decrypt_chacha20_poly1305(bytes(modified_ciphertext), mac, self.key, self.nonce)


class TestCryptoIntegration(unittest.TestCase):
    """Integration tests for encrypt-decrypt cycle."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.key = secrets.token_bytes(32)
        self.nonce = secrets.token_bytes(12)
    
    def test_full_encrypt_decrypt_cycle(self):
        """
        CRITICAL TEST: Full encrypt-decrypt cycle must recover original data.
        
        This tests the entire pipeline.
        """
        test_messages = [
            b"Short message",
            b"A" * 100,  # Repeated pattern
            b"Mixed case: Hello World! 123 @#$%",
            b"\x00" * 50,  # Null bytes
            b"\xFF" * 50,  # All ones
            secrets.token_bytes(1000),  # Random data
        ]
        
        for plaintext in test_messages:
            with self.subTest(plaintext=plaintext[:20]):  # Use first 20 bytes for test name
                # Encrypt
                ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
                
                # Verify ciphertext is different
                self.assertNotEqual(ciphertext, plaintext)
                
                # Decrypt
                decrypted = decrypt_chacha20_poly1305(ciphertext, mac, self.key, self.nonce)
                
                # Must recover original
                self.assertEqual(
                    decrypted,
                    plaintext,
                    f"Full encrypt-decrypt cycle must recover original data (length {len(plaintext)})"
                )
    
    def test_multiple_encrypt_decrypt_cycles(self):
        """Test multiple encrypt-decrypt cycles with different data."""
        num_tests = 20
        success_count = 0
        
        for i in range(num_tests):
            # Generate random plaintext
            plaintext_len = secrets.randbelow(1000) + 1
            plaintext = secrets.token_bytes(plaintext_len)
            
            try:
                # Encrypt
                ciphertext, mac = encrypt_chacha20_poly1305(plaintext, self.key, self.nonce)
                
                # Decrypt
                decrypted = decrypt_chacha20_poly1305(ciphertext, mac, self.key, self.nonce)
                
                if decrypted == plaintext:
                    success_count += 1
            except Exception as e:
                self.fail(f"Encrypt-decrypt cycle {i} failed: {e}")
        
        # All cycles should succeed
        self.assertEqual(
            success_count,
            num_tests,
            f"All {num_tests} encrypt-decrypt cycles should succeed. Got {success_count} successes"
        )


class TestMACFunctionality(unittest.TestCase):
    """Test MAC computation (for backward compatibility)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.key = secrets.token_bytes(32)
    
    def test_mac_is_deterministic(self):
        """Test that MAC computation is deterministic."""
        data = b"Test data for MAC"
        
        mac1 = compute_chacha20_mac(data, self.key)
        mac2 = compute_chacha20_mac(data, self.key)
        
        self.assertEqual(mac1, mac2, "MAC computation must be deterministic")
    
    def test_mac_different_for_different_data(self):
        """Test that different data produces different MACs."""
        data1 = b"Message one"
        data2 = b"Message two"
        
        mac1 = compute_chacha20_mac(data1, self.key)
        mac2 = compute_chacha20_mac(data2, self.key)
        
        self.assertNotEqual(mac1, mac2, "Different data must produce different MACs")
    
    def test_mac_is_16_bytes(self):
        """Test that MAC is 16 bytes."""
        data = b"Test data"
        mac = compute_chacha20_mac(data, self.key)
        
        self.assertEqual(len(mac), 16, "MAC must be 16 bytes")


if __name__ == '__main__':
    unittest.main()

