# gr-sleipnir Testing Guide

## Overview

The gr-sleipnir test suite focuses on **functional unit tests** that verify actual code behavior. These tests are designed to catch "plausible but broken" code that looks correct but doesn't actually work.

## Quick Start

### Run All Functional Tests

```bash
cd /home/haaken/github-projects/gr-sleipnir
./tests/run_all_functionality_tests.sh
```

This script runs all functional tests that verify:
- LDPC encoding actually encodes data
- LDPC decoding actually decodes and corrects errors
- Encryption actually encrypts data
- Decryption actually recovers plaintext
- Signatures are generated and verified correctly

### Run Individual Test Suites

```bash
# Critical functionality tests (catches passthrough, thresholding, etc.)
python3 -m pytest tests/test_critical_functionality.py -v

# LDPC encoding/decoding tests
python3 -m pytest tests/test_ldpc_functionality.py -v

# Cryptographic functionality tests
python3 -m pytest tests/test_crypto_functionality.py -v

# Meta-test to verify tests actually exercise code
python3 -m pytest tests/test_actual_code_exercise.py -v

# Signature verification
python3 tests/test_signature_verification.py

# Encryption switching
python3 tests/test_encryption_switching.py

# Recipient checking
python3 tests/test_recipient_checking.py

# Multi-recipient scenarios
python3 tests/test_multi_recipient.py
```

## Test Suites

### Critical Functionality Tests (`test_critical_functionality.py`)

These tests are specifically designed to catch the types of bugs that were identified in the code review:
- **LDPC Not Passthrough**: Verifies encoder actually changes data
- **LDPC Not Just Thresholding**: Verifies decoder corrects errors, not just thresholds
- **Encryption Not Just MAC**: Verifies encryption actually encrypts, not just computes MAC
- **Decryption Actually Decrypts**: Verifies decryption recovers plaintext

### LDPC Functionality Tests (`test_ldpc_functionality.py`)

Tests for LDPC encoding and decoding:
- **Encoding Tests**:
  - Encoding changes data (not passthrough)
  - Encoded codeword satisfies parity checks
  - Encoding is deterministic
  - Different inputs produce different outputs
- **Decoding Tests**:
  - Decoding recovers original data from perfect channel
  - Decoding corrects errors (not just thresholds)
  - Decoding works on noisy channels
  - Decoded codeword satisfies parity checks
- **Integration Tests**:
  - Full encode-decode cycle recovers original data
  - Multiple random inputs work correctly

### Crypto Functionality Tests (`test_crypto_functionality.py`)

Tests for cryptographic operations:
- **ChaCha20-Poly1305 Encryption**:
  - Encryption changes data
  - Different plaintexts produce different ciphertexts
  - Different nonces produce different ciphertexts
  - Encryption produces random-looking output
  - Encryption is deterministic with same nonce
- **ChaCha20-Poly1305 Decryption**:
  - Decryption recovers plaintext
  - Decryption fails with wrong MAC
  - Decryption fails with wrong key
  - Decryption fails with wrong nonce
  - Decryption fails with modified ciphertext
- **MAC Functionality**:
  - MAC is deterministic
  - MAC differs for different data
  - MAC is correct length

### Code Exercise Verification (`test_actual_code_exercise.py`)

Meta-test to verify that the critical tests themselves actually exercise the code:
- Verifies LDPC encoding test actually tests encoding
- Verifies LDPC decoding test actually tests decoding
- Verifies crypto tests actually test encryption/decryption
- Runs the critical test script and verifies success

### Other Functional Tests

- **`test_signature_verification.py`**: ECDSA signature generation and verification
- **`test_encryption_switching.py`**: Encryption enable/disable functionality
- **`test_recipient_checking.py`**: Multi-recipient message handling
- **`test_multi_recipient.py`**: Multi-recipient scenarios

## Test Philosophy

These tests are designed to:
1. **Verify actual functionality**, not just that code runs without crashing
2. **Catch "plausible but broken" code** that looks correct but doesn't work
3. **Run quickly** - all tests complete in seconds, not hours
4. **Exercise real code paths** - tests import and call actual functions from the codebase

## What Was Removed

The following long-running tests were removed because they:
- Took hours to run
- Didn't explicitly verify encoding/decoding occurred
- Only checked end-to-end audio quality metrics
- Couldn't catch "plausible but broken" code

Removed files:
- `test_sleipnir.py` - Long-running SNR test suite
- `test_comprehensive.py` - Comprehensive test suite
- `generate_fer_comparison_samples.py` - FER sample generation

## Running Tests in CI/CD

For continuous integration, run:

```bash
./tests/run_all_functionality_tests.sh
```

This script exits with code 0 if all tests pass, or non-zero if any test fails.

## Test Requirements

- Python 3.x
- pytest (for unit tests)
- numpy
- Access to LDPC matrix files in `ldpc_matrices/`
- `cryptography` library (for crypto tests)

## Troubleshooting

### Missing LDPC Matrix Files

Ensure LDPC matrix files exist:
- `ldpc_matrices/ldpc_voice_576_384.alist`
- `ldpc_matrices/ldpc_auth_1536_512.alist`

### Missing Dependencies

Install required Python packages:
```bash
pip3 install pytest numpy cryptography
```

### Test Failures

If tests fail, check:
1. Are LDPC matrix files present?
2. Are all dependencies installed?
3. Is the code actually implementing the functionality (not just placeholders)?

## Expected Runtime

All functional tests complete in **under 30 seconds** on typical hardware.

## Test Coverage

The functional tests verify:
- ✅ LDPC encoding actually encodes
- ✅ LDPC decoding actually decodes and corrects errors
- ✅ Encryption actually encrypts
- ✅ Decryption actually decrypts
- ✅ Signatures are generated and verified
- ✅ MAC computation and verification
- ✅ Multi-recipient message handling

These tests ensure the code actually works, not just that it looks plausible.
