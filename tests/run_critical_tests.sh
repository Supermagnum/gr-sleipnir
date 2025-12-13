#!/bin/bash
# Run critical functionality tests
# These tests catch "looks plausible but doesn't work" issues

set -e

echo "=========================================="
echo "Running Critical Functionality Tests"
echo "=========================================="
echo ""

# Run LDPC functionality tests
echo "1. Testing LDPC Encoding/Decoding Functionality..."
python3 -m pytest tests/test_ldpc_functionality.py -v
if [ $? -ne 0 ]; then
    echo "ERROR: LDPC functionality tests failed!"
    exit 1
fi
echo ""

# Run Crypto functionality tests
echo "2. Testing Cryptographic Functionality..."
python3 -m pytest tests/test_crypto_functionality.py -v
if [ $? -ne 0 ]; then
    echo "ERROR: Cryptographic functionality tests failed!"
    exit 1
fi
echo ""

# Run Critical tests (catch common bugs)
echo "3. Running Critical Bug Detection Tests..."
python3 -m pytest tests/test_critical_functionality.py -v
if [ $? -ne 0 ]; then
    echo "ERROR: Critical bug detection tests failed!"
    exit 1
fi
echo ""

echo "=========================================="
echo "All Critical Tests Passed!"
echo "=========================================="

