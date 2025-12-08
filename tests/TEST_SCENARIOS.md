# Test Scenarios Documentation

Detailed documentation of test scenarios for gr-sleipnir.

## Test Scenarios

### 1. Voice + Text Multiplexing

**Objective**: Verify voice and text can be transmitted simultaneously without breaking voice stream.

**Test Procedure**:
1. Create superframe with voice frames
2. Inject text data into reserved fields
3. Transmit superframe
4. Verify voice stream integrity
5. Extract text data from received frames

**Expected Results**:
- Voice frames transmitted successfully
- Text data embedded in frames
- Voice stream remains intact
- Text can be extracted at receiver

**Test File**: `test_voice_text_multiplex.py`

### 2. Encryption Enable/Disable Switching

**Objective**: Verify encryption can be enabled/disabled during transmission.

**Test Procedure**:
1. Start transmission without encryption
2. Enable encryption mid-session
3. Disable encryption mid-session
4. Verify MAC computation follows state
5. Check frame payloads match encryption state

**Expected Results**:
- Encryption state changes take effect immediately
- MAC present when encryption enabled
- MAC absent when encryption disabled
- No frame corruption during state changes

**Test File**: `test_encryption_switching.py`

### 3. Signature Verification

**Objective**: Verify ECDSA signatures are generated correctly and can be verified.

**Test Procedure**:
1. Generate test key pair (BrainpoolP256r1)
2. Generate signature for test data
3. Verify signature format (32 bytes)
4. Load key from file
5. Generate signature with loaded key
6. Verify signatures match

**Expected Results**:
- Signatures generated successfully
- Signature format correct (32 bytes)
- Keys load from file correctly
- Signatures reproducible

**Test File**: `test_signature_verification.py`

**Note**: Full signature verification requires storing 64-byte signature. Current implementation uses 32-byte hash.

### 4. Multi-Recipient Scenarios

**Objective**: Test various recipient counts and recipient list handling.

**Test Cases**:
- Single recipient
- Two recipients
- Three recipients
- Five recipients
- Ten recipients

**Test Procedure**:
1. Create superframe with recipient list
2. Verify recipient list parsing
3. Transmit superframe
4. Verify frame construction
5. Check recipient metadata

**Expected Results**:
- All recipient counts handled correctly
- Recipient list parsed correctly
- Frames constructed successfully
- Metadata includes all recipients

**Test File**: `test_multi_recipient.py`

### 5. APRS Injection

**Objective**: Verify APRS data can be injected without breaking voice stream.

**Test Procedure**:
1. Transmit voice-only superframe (baseline)
2. Inject APRS into single frame
3. Inject APRS into multiple frames
4. Verify voice stream integrity
5. Extract APRS data

**Expected Results**:
- Voice stream remains intact
- APRS data embedded correctly
- Multiple APRS updates work
- No frame corruption

**Test File**: `test_aprs_injection.py`

### 6. Backward Compatibility

**Objective**: Verify system handles unsigned and plaintext messages gracefully.

**Test Cases**:
- Unsigned message (no Frame 0)
- Plaintext message (no MAC)
- Parser with require_signatures=False
- Parser with require_signatures=True

**Test Procedure**:
1. Transmit unsigned message
2. Transmit plaintext message
3. Parse unsigned message (require_signatures=False)
4. Parse unsigned message (require_signatures=True)
5. Verify behavior matches configuration

**Expected Results**:
- Unsigned messages accepted when require_signatures=False
- Unsigned messages rejected when require_signatures=True
- Plaintext messages handled correctly
- Status messages indicate message type

**Test File**: `test_backward_compatibility.py`

### 7. Recipient Checking

**Objective**: Verify graceful handling when message is not addressed to receiving station.

**Test Cases**:
- Message addressed to this station
- Message not addressed to this station
- Broadcast message (empty recipients)
- Multi-recipient with this station included

**Test Procedure**:
1. Create message with recipient list
2. Set local callsign
3. Check if local callsign in recipient list
4. Process message accordingly
5. Verify status messages

**Expected Results**:
- Messages addressed to this station are processed
- Messages not addressed are handled gracefully
- Broadcast messages are processed
- Status indicates recipient match

**Test File**: `test_recipient_checking.py`

### 8. Latency Measurement

**Objective**: Compare latency between encrypted and plaintext modes.

**Test Procedure**:
1. Measure plaintext mode latency (10 iterations)
2. Measure encrypted mode latency (10 iterations)
3. Calculate statistics (mean, min, max, std dev)
4. Calculate encryption overhead
5. Compare results

**Expected Results**:
- Plaintext latency: < 50 ms per superframe
- Encrypted latency: < 60 ms per superframe
- Encryption overhead: < 10%
- Consistent results across iterations

**Test File**: `test_latency_measurement.py`

**Metrics**:
- Average latency
- Minimum latency
- Maximum latency
- Standard deviation
- Encryption overhead percentage

## Running Tests

### Individual Tests

```bash
# Voice + text multiplexing
python3 tests/test_voice_text_multiplex.py

# Encryption switching
python3 tests/test_encryption_switching.py

# Signature verification
python3 tests/test_signature_verification.py

# Multi-recipient
python3 tests/test_multi_recipient.py

# APRS injection
python3 tests/test_aprs_injection.py

# Backward compatibility
python3 tests/test_backward_compatibility.py

# Recipient checking
python3 tests/test_recipient_checking.py

# Latency measurement
python3 tests/test_latency_measurement.py
```

### All Tests

```bash
python3 tests/run_all_tests.py
```

## Test Data

### Synthetic Data

Tests use synthetic data for reproducibility:
- Dummy Opus frames: 40 bytes of zeros
- Test callsigns: TEST, N0CALL, N1ABC, etc.
- Generated MAC keys: Random 32 bytes
- Test coordinates: Oslo, Norway (59.9139, 10.7522)

### Real-World Testing

For production testing, replace with:
- Real Opus-encoded audio from microphone/file
- Actual callsigns from radio configuration
- Pre-shared MAC keys from key exchange
- Real GPS coordinates

## Expected Performance

### Latency Targets

| Mode | Target | Acceptable |
|------|--------|------------|
| Plaintext | < 30 ms | < 50 ms |
| Encrypted | < 40 ms | < 60 ms |
| Signed | < 50 ms | < 70 ms |
| Overhead | < 5% | < 10% |

### Throughput

- Superframes per second: 1 (25 frames = 1 second)
- Voice frames per superframe: 24
- Total voice capacity: 960 bytes/second (24 * 40 bytes)

### Error Rates

- Frame loss: < 1%
- Signature verification: 100% (when keys available)
- Decryption success: 100% (when addressed correctly)

## Troubleshooting

### Tests Fail to Run

- Check Python path includes project root
- Verify all dependencies installed
- Check file permissions (chmod +x)

### Signature Tests Fail

- Generate test keys first
- Verify cryptography library installed
- Check key file permissions

### Latency Tests Show High Values

- Check system load
- Verify no other processes running
- Consider hardware acceleration
- Check CPU frequency scaling

### Multi-Recipient Tests Fail

- Verify recipient list parsing
- Check frame construction logic
- Verify metadata handling

## Continuous Integration

For CI/CD:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    python3 tests/run_all_tests.py
  timeout-minutes: 10
```

## Test Coverage

Current coverage:
- Voice + text multiplexing
- Encryption switching
- Signature generation
- Multi-recipient scenarios
- APRS injection
- Backward compatibility
- Recipient checking
- Latency measurement

Future additions:
- [ ] End-to-end TX/RX loopback
- [ ] Real audio encoding/decoding
- [ ] Network PTT integration
- [ ] GPIO PTT integration
- [ ] Serial PTT integration
- [ ] VOX PTT integration

