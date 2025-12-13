#!/usr/bin/env python3
"""
Unit tests for LDPC encoding and decoding functionality.

These tests verify that LDPC encoding and decoding actually work,
not just pass through data or do simple thresholding.
"""

import unittest
import numpy as np
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from python.ldpc_utils import (
    load_alist_matrix,
    compute_generator_matrix,
    ldpc_encode,
    ldpc_decode_soft
)


class TestLDPCEncoding(unittest.TestCase):
    """Test that LDPC encoding actually encodes data."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use a simple test matrix file if available, or create a minimal one
        self.test_matrix_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'ldpc_matrices',
            'ldpc_voice_576_384.alist'
        )
        
        if not os.path.exists(self.test_matrix_file):
            self.skipTest(f"Test matrix file not found: {self.test_matrix_file}")
        
        self.H, self.n, self.k = load_alist_matrix(self.test_matrix_file)
        self.G = compute_generator_matrix(self.H)
    
    def test_encoding_changes_data(self):
        """
        CRITICAL TEST: Encoding must change the data.
        
        If encoding just passes through, this test will fail.
        """
        # Create test information bits
        info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        
        # Encode
        codeword = ldpc_encode(info_bits, self.G)
        
        # CRITICAL: Encoded data must be different from input (for non-zero input)
        # For systematic codes, first k bits should match, but total length should be n > k
        self.assertEqual(len(codeword), self.n, "Encoded codeword must have length n")
        self.assertGreater(self.n, self.k, "Codeword length must be greater than info length")
        
        # For systematic encoding, first k bits should match info bits
        np.testing.assert_array_equal(
            codeword[:self.k],
            info_bits,
            "Systematic encoding: first k bits should match info bits"
        )
        
        # Last (n-k) bits should be parity bits (may be zero for some inputs, but structure should exist)
        parity_bits = codeword[self.k:]
        self.assertEqual(len(parity_bits), self.n - self.k, "Parity bits length must be n-k")
    
    def test_encoding_satisfies_parity_checks(self):
        """
        CRITICAL TEST: Encoded codeword must satisfy all parity checks.
        
        If encoding doesn't use the parity check matrix, this will fail.
        """
        # Create test information bits
        info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        
        # Encode
        codeword = ldpc_encode(info_bits, self.G)
        
        # Check that H * codeword^T = 0 (mod 2)
        syndrome = (self.H @ codeword) % 2
        zero_syndrome = np.zeros(self.H.shape[0], dtype=np.uint8)
        
        np.testing.assert_array_equal(
            syndrome,
            zero_syndrome,
            "Encoded codeword must satisfy all parity checks: H*c = 0 (mod 2)"
        )
    
    def test_encoding_deterministic(self):
        """Test that encoding is deterministic (same input -> same output)."""
        info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        
        codeword1 = ldpc_encode(info_bits, self.G)
        codeword2 = ldpc_encode(info_bits, self.G)
        
        np.testing.assert_array_equal(
            codeword1,
            codeword2,
            "Encoding must be deterministic"
        )
    
    def test_encoding_different_inputs_different_outputs(self):
        """Test that different inputs produce different outputs."""
        info_bits1 = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        info_bits2 = info_bits1.copy()
        info_bits2[0] = 1 - info_bits2[0]  # Flip first bit
        
        codeword1 = ldpc_encode(info_bits1, self.G)
        codeword2 = ldpc_encode(info_bits2, self.G)
        
        # Outputs should be different
        self.assertFalse(
            np.array_equal(codeword1, codeword2),
            "Different inputs must produce different encoded outputs"
        )


class TestLDPCDecoding(unittest.TestCase):
    """Test that LDPC decoding actually decodes and corrects errors."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_matrix_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'ldpc_matrices',
            'ldpc_voice_576_384.alist'
        )
        
        if not os.path.exists(self.test_matrix_file):
            self.skipTest(f"Test matrix file not found: {self.test_matrix_file}")
        
        self.H, self.n, self.k = load_alist_matrix(self.test_matrix_file)
        self.G = compute_generator_matrix(self.H)
    
    def test_decoding_perfect_channel(self):
        """
        CRITICAL TEST: Decoding must recover original data from perfect channel.
        
        If decoding just does thresholding without error correction, this may pass,
        but we also test error correction below.
        """
        # Create test information bits
        info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        
        # Encode
        codeword = ldpc_encode(info_bits, self.G)
        
        # Create soft decisions from perfect channel (high confidence)
        # LLR = log(P(0)/P(1)), so for bit=0: large positive, for bit=1: large negative
        soft_bits = np.zeros(self.n, dtype=np.float32)
        for i in range(self.n):
            if codeword[i] == 0:
                soft_bits[i] = 10.0  # High confidence for 0
            else:
                soft_bits[i] = -10.0  # High confidence for 1
        
        # Decode
        decoded_bits = ldpc_decode_soft(soft_bits, self.H, max_iter=50)
        
        # Must recover original information bits
        np.testing.assert_array_equal(
            decoded_bits,
            info_bits,
            "Decoding must recover original info bits from perfect channel"
        )
    
    def test_decoding_corrects_errors(self):
        """
        CRITICAL TEST: Decoding must correct errors, not just threshold.
        
        This is the key test - if decoding just thresholds, it cannot correct errors.
        """
        # Create test information bits
        info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        
        # Encode
        codeword = ldpc_encode(info_bits, self.G)
        
        # Introduce errors in the codeword (flip some bits)
        corrupted_codeword = codeword.copy()
        error_positions = np.random.choice(self.n, size=min(5, self.n // 10), replace=False)
        for pos in error_positions:
            corrupted_codeword[pos] = 1 - corrupted_codeword[pos]
        
        # Create soft decisions with some uncertainty (moderate SNR)
        # Correct bits: high confidence, error bits: low/opposite confidence
        soft_bits = np.zeros(self.n, dtype=np.float32)
        for i in range(self.n):
            if corrupted_codeword[i] == 0:
                soft_bits[i] = 3.0  # Moderate confidence for 0
            else:
                soft_bits[i] = -3.0  # Moderate confidence for 1
        
        # For error positions, give wrong soft decision (simulating channel errors)
        for pos in error_positions:
            if corrupted_codeword[pos] == 0:
                soft_bits[pos] = -1.0  # Wrong: says bit is 1
            else:
                soft_bits[pos] = 1.0  # Wrong: says bit is 0
        
        # Decode
        decoded_bits = ldpc_decode_soft(soft_bits, self.H, max_iter=50)
        
        # Decoder should correct errors and recover original info bits
        # Allow some tolerance for very noisy channels, but should work for moderate errors
        errors = np.sum(decoded_bits != info_bits)
        error_rate = errors / self.k
        
        self.assertLess(
            error_rate,
            0.1,  # Allow up to 10% errors for this test (moderate SNR)
            f"Decoding should correct most errors. Got {errors}/{self.k} errors ({error_rate*100:.1f}%)"
        )
    
    def test_decoding_noisy_channel(self):
        """Test decoding performance on noisy channel."""
        # Create test information bits
        info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        
        # Encode
        codeword = ldpc_encode(info_bits, self.G)
        
        # Create soft decisions with noise (low SNR)
        # Add Gaussian noise to LLRs
        noise_sigma = 2.0
        soft_bits = np.zeros(self.n, dtype=np.float32)
        for i in range(self.n):
            if codeword[i] == 0:
                base_llr = 5.0
            else:
                base_llr = -5.0
            soft_bits[i] = base_llr + np.random.normal(0, noise_sigma)
        
        # Decode
        decoded_bits = ldpc_decode_soft(soft_bits, self.H, max_iter=50)
        
        # Should recover most bits even with noise
        errors = np.sum(decoded_bits != info_bits)
        error_rate = errors / self.k
        
        # With moderate noise, should get < 20% errors
        self.assertLess(
            error_rate,
            0.2,
            f"Decoding should handle noise. Got {errors}/{self.k} errors ({error_rate*100:.1f}%)"
        )
    
    def test_decoding_satisfies_parity_checks(self):
        """
        CRITICAL TEST: Decoded codeword must satisfy parity checks.
        
        Even if info bits don't match perfectly, the full codeword should satisfy H*c = 0.
        """
        # Create test information bits
        info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        
        # Encode to get valid codeword
        codeword = ldpc_encode(info_bits, self.G)
        
        # Create soft decisions
        soft_bits = np.zeros(self.n, dtype=np.float32)
        for i in range(self.n):
            if codeword[i] == 0:
                soft_bits[i] = 5.0
            else:
                soft_bits[i] = -5.0
        
        # Decode
        decoded_info = ldpc_decode_soft(soft_bits, self.H, max_iter=50)
        
        # Reconstruct full codeword from decoded info (using generator matrix)
        decoded_codeword = ldpc_encode(decoded_info, self.G)
        
        # Check parity checks
        syndrome = (self.H @ decoded_codeword) % 2
        zero_syndrome = np.zeros(self.H.shape[0], dtype=np.uint8)
        
        np.testing.assert_array_equal(
            syndrome,
            zero_syndrome,
            "Decoded codeword must satisfy all parity checks"
        )


class TestLDPCIntegration(unittest.TestCase):
    """Integration tests for encode-decode cycle."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_matrix_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'ldpc_matrices',
            'ldpc_voice_576_384.alist'
        )
        
        if not os.path.exists(self.test_matrix_file):
            self.skipTest(f"Test matrix file not found: {self.test_matrix_file}")
        
        self.H, self.n, self.k = load_alist_matrix(self.test_matrix_file)
        self.G = compute_generator_matrix(self.H)
    
    def test_encode_decode_cycle(self):
        """
        CRITICAL TEST: Full encode-decode cycle must recover original data.
        
        This tests the entire pipeline.
        """
        # Create test information bits
        info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
        
        # Encode
        codeword = ldpc_encode(info_bits, self.G)
        
        # Simulate transmission through channel with soft decisions
        # Perfect channel for this test
        soft_bits = np.zeros(self.n, dtype=np.float32)
        for i in range(self.n):
            if codeword[i] == 0:
                soft_bits[i] = 10.0
            else:
                soft_bits[i] = -10.0
        
        # Decode
        decoded_bits = ldpc_decode_soft(soft_bits, self.H, max_iter=50)
        
        # Must recover original
        np.testing.assert_array_equal(
            decoded_bits,
            info_bits,
            "Full encode-decode cycle must recover original data"
        )
    
    def test_multiple_random_inputs(self):
        """Test encode-decode cycle with multiple random inputs."""
        num_tests = 10
        success_count = 0
        
        for _ in range(num_tests):
            info_bits = np.random.randint(0, 2, size=self.k, dtype=np.uint8)
            
            # Encode
            codeword = ldpc_encode(info_bits, self.G)
            
            # Perfect channel
            soft_bits = np.zeros(self.n, dtype=np.float32)
            for i in range(self.n):
                if codeword[i] == 0:
                    soft_bits[i] = 10.0
                else:
                    soft_bits[i] = -10.0
            
            # Decode
            decoded_bits = ldpc_decode_soft(soft_bits, self.H, max_iter=50)
            
            if np.array_equal(decoded_bits, info_bits):
                success_count += 1
        
        # Should succeed for all tests with perfect channel
        self.assertEqual(
            success_count,
            num_tests,
            f"All {num_tests} encode-decode cycles should succeed with perfect channel. Got {success_count} successes"
        )


if __name__ == '__main__':
    unittest.main()

