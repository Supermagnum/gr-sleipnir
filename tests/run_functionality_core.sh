#!/bin/bash
# Core functionality steps (pytest suites + script tests) without the meta-test that
# invokes this bundle. Used by test_actual_code_exercise.py to avoid recursion.

set -e

echo "=========================================="
echo "Running core functionality tests"
echo "=========================================="
echo ""

FAILED=0

echo "1. Critical Functionality Tests..."
python3 -m pytest tests/test_critical_functionality.py -v || FAILED=1
echo ""

echo "2. LDPC Functionality Tests..."
python3 -m pytest tests/test_ldpc_functionality.py -v || FAILED=1
echo ""

echo "3. Crypto Functionality Tests..."
python3 -m pytest tests/test_crypto_functionality.py -v || FAILED=1
echo ""

echo "4. Signature Verification Test..."
python3 tests/test_signature_verification.py || FAILED=1
echo ""

echo "5. Encryption Switching Test..."
python3 tests/test_encryption_switching.py || FAILED=1
echo ""

echo "6. Recipient Checking Test..."
python3 tests/test_recipient_checking.py || FAILED=1
echo ""

echo "7. Multi-Recipient Test..."
python3 tests/test_multi_recipient.py || FAILED=1
echo ""

echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
    echo "Core functionality tests passed."
else
    echo "Core functionality tests reported failures."
fi
echo "=========================================="

exit "$FAILED"
