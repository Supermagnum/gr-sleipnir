#!/bin/bash
# Run all functionality tests to ensure code actually works

set -e

echo "=========================================="
echo "Running All Functionality Tests"
echo "=========================================="
echo ""

FAILED=0

# Critical functionality tests (must pass)
echo "1. Critical Functionality Tests..."
python3 -m pytest tests/test_critical_functionality.py -v || FAILED=1
echo ""

# LDPC functionality tests
echo "2. LDPC Functionality Tests..."
python3 -m pytest tests/test_ldpc_functionality.py -v || FAILED=1
echo ""

# Crypto functionality tests
echo "3. Crypto Functionality Tests..."
python3 -m pytest tests/test_crypto_functionality.py -v || FAILED=1
echo ""

# Code exercise verification
echo "4. Code Exercise Verification..."
python3 -m pytest tests/test_actual_code_exercise.py -v || FAILED=1
echo ""

# Signature verification (updated to actually verify)
echo "5. Signature Verification Test..."
python3 tests/test_signature_verification.py || FAILED=1
echo ""

# Encryption switching (updated to check actual encryption)
echo "6. Encryption Switching Test..."
python3 tests/test_encryption_switching.py || FAILED=1
echo ""

# Recipient checking (updated with assertions)
echo "7. Recipient Checking Test..."
python3 tests/test_recipient_checking.py || FAILED=1
echo ""

# Multi-recipient (updated with parsing verification)
echo "8. Multi-Recipient Test..."
python3 tests/test_multi_recipient.py || FAILED=1
echo ""

echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "All Tests Passed!"
    echo "Code is actually working, not just looking plausible."
else
    echo "Some Tests Failed!"
    echo "Please fix the failing tests before submitting code."
fi
echo "=========================================="

exit $FAILED

