# Test Suite Summary

Quick reference summary for gr-sleipnir test suite. For detailed documentation, see [tests/README.md](README.md).

## Test Status

**Overall: 8/8 tests passing**

## Quick Reference

| Test | Status | File |
|------|--------|------|
| Voice + Text Multiplexing | PASS | `test_voice_text_multiplex.py` |
| Encryption Switching | PASS | `test_encryption_switching.py` |
| Signature Verification | PASS | `test_signature_verification.py` |
| Multi-Recipient | PASS | `test_multi_recipient.py` |
| APRS Injection | PASS | `test_aprs_injection.py` |
| Backward Compatibility | PASS | `test_backward_compatibility.py` |
| Recipient Checking | PASS | `test_recipient_checking.py` |
| Latency Measurement | PASS | `test_latency_measurement.py` |

## Running Tests

```bash
# Run all tests
python3 tests/run_all_tests.py

# Run individual test
python3 tests/test_voice_text_multiplex.py
```

## Performance Results

- Plaintext latency: ~0.001 ms per frame
- Encrypted latency: ~0.018 ms per frame
- Encryption overhead: ~0.017 ms per frame

For detailed test documentation, see [tests/README.md](README.md) and [tests/TEST_SCENARIOS.md](TEST_SCENARIOS.md).
