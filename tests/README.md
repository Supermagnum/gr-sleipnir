# gr-sleipnir Test Suite

Comprehensive test suite for gr-sleipnir superframe system.

## Test Coverage

### 1. Voice + Text Multiplexing
**File**: `test_voice_text_multiplex.py`

Tests simultaneous transmission of voice and text messages in superframe.

**What it tests**:
- Text injection into voice frames
- Voice stream integrity with text data
- Frame payload construction

**Run**:
```bash
python3 tests/test_voice_text_multiplex.py
```

### 2. Encryption Enable/Disable Switching
**File**: `test_encryption_switching.py`

Tests switching encryption on/off during transmission.

**What it tests**:
- Starting without encryption
- Enabling encryption mid-session
- Disabling encryption mid-session
- MAC computation enable/disable

**Run**:
```bash
python3 tests/test_encryption_switching.py
```

### 3. Signature Verification
**File**: `test_signature_verification.py`

Tests ECDSA signature generation and verification.

**What it tests**:
- Key pair generation
- Signature generation
- Key loading from file
- Signature format validation

**Run**:
```bash
python3 tests/test_signature_verification.py
```

**Note**: Full signature verification requires storing 64-byte signature (current implementation uses 32-byte hash).

### 4. Multi-Recipient Scenarios
**File**: `test_multi_recipient.py`

Tests various recipient counts and recipient list handling.

**What it tests**:
- Single recipient
- Multiple recipients (2, 3, 5, 10)
- Recipient list parsing
- Frame construction with multiple recipients

**Run**:
```bash
python3 tests/test_multi_recipient.py
```

### 5. APRS Injection
**File**: `test_aprs_injection.py`

Tests APRS data injection without breaking voice stream.

**What it tests**:
- Voice-only superframe
- Voice + APRS in same superframe
- Multiple APRS updates
- Voice stream integrity

**Run**:
```bash
python3 tests/test_aprs_injection.py
```

### 6. Backward Compatibility
**File**: `test_backward_compatibility.py`

Tests handling of unsigned and plaintext messages.

**What it tests**:
- Unsigned message transmission
- Plaintext message transmission
- Parser handling unsigned messages
- require_signatures flag behavior

**Run**:
```bash
python3 tests/test_backward_compatibility.py
```

### 7. Recipient Checking
**File**: `test_recipient_checking.py`

Tests graceful handling when message is not addressed to receiving station.

**What it tests**:
- Message addressed to this station
- Message not addressed to this station
- Broadcast messages (empty recipients)
- Multi-recipient with this station included

**Run**:
```bash
python3 tests/test_recipient_checking.py
```

### 8. Latency Measurement
**File**: `test_latency_measurement.py`

Compares latency between encrypted and plaintext modes.

**What it tests**:
- Plaintext mode latency
- Encrypted mode latency (with MAC)
- Encryption overhead calculation
- Statistical analysis (mean, min, max, std dev)

**Run**:
```bash
python3 tests/test_latency_measurement.py
```

## Running All Tests

Run the complete test suite:

```bash
python3 tests/run_all_tests.py
```

This will:
1. Run all test modules
2. Display results for each test
3. Provide a summary with pass/fail counts

## Test Requirements

### Dependencies

- Python 3.8+
- numpy
- cryptography library
- GNU Radio Python bindings

### Optional Dependencies

- RPi.GPIO or libgpiod (for GPIO PTT tests)
- pyserial (for serial PTT tests)

## Test Data

Tests use synthetic data:
- Dummy Opus frames (40 bytes each, zeros)
- Test callsigns (TEST, N0CALL, etc.)
- Generated MAC keys (random 32 bytes)

For production testing, replace with:
- Real Opus-encoded audio
- Actual callsigns
- Pre-shared MAC keys

## Expected Results

### Latency Targets

- **Plaintext**: < 50 ms per superframe
- **Encrypted**: < 60 ms per superframe
- **Overhead**: < 10% increase

### Signature Verification

- Signature generation: < 10 ms
- Signature format: 32 bytes (hash of 64-byte ECDSA signature)

### Multi-Recipient

- Supports up to 10+ recipients
- Recipient list parsing: < 1 ms

## Troubleshooting

### Tests Fail to Import Modules

Ensure Python path includes project root:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Signature Tests Fail

Generate test keys:
```bash
# Generate test key pair (see test_signature_verification.py)
python3 tests/test_signature_verification.py
```

### Latency Tests Show High Overhead

- Check system load
- Verify cryptography library is optimized
- Consider hardware acceleration

### GPIO Tests Fail

- Verify GPIO library installed
- Check permissions (may need sudo or gpio group)
- Verify GPIO pin number

## Continuous Integration

For CI/CD integration:

```bash
# Run tests with output to file
python3 tests/run_all_tests.py > test_results.txt 2>&1

# Check exit code
if [ $? -eq 0 ]; then
    echo "All tests passed"
else
    echo "Some tests failed"
    exit 1
fi
```

## Adding New Tests

1. Create test file: `tests/test_new_feature.py`
2. Follow existing test structure
3. Add to `TESTS` list in `run_all_tests.py`
4. Document in this README

## Test Coverage Goals

- [x] Voice + text multiplexing
- [x] Encryption switching
- [x] Signature verification
- [x] Multi-recipient scenarios
- [x] APRS injection
- [x] Backward compatibility
- [x] Recipient checking
- [x] Latency measurement

## Notes

- Tests use simplified data (dummy Opus frames)
- Real-world testing requires actual audio encoding
- Some tests require hardware (GPIO, serial ports)
- Latency measurements are system-dependent

