# Integration Test Guide

Guide for running integration tests with actual GNU Radio flowgraphs.

## Prerequisites

1. GNU Radio flowgraphs created:
   - `examples/tx_4fsk_opus_voice.grc` - Voice frame transmitter
   - `examples/tx_auth_frame.grc` - Authentication frame transmitter
   - `examples/rx_4fsk_opus_voice.grc` - Voice frame receiver

2. Test keys generated:
   ```bash
   # Generate test key pair
   python3 tests/test_signature_verification.py
   ```

3. Public key store directory:
   ```bash
   mkdir -p tests/public_keys
   # Copy public keys to tests/public_keys/{callsign}.pem
   ```

## Test Scenarios

### 1. Voice + Text Multiplexing

**Flowgraph**: Use `tx_4fsk_opus_voice.grc` with text injection

**Procedure**:
1. Inject text into voice frame reserved fields
2. Transmit superframe
3. Receive and extract text
4. Verify voice stream integrity

**Expected**: Text extracted, voice intact

### 2. Encryption Switching

**Flowgraph**: Dynamic MAC enable/disable

**Procedure**:
1. Start transmission without MAC
2. Enable MAC mid-session
3. Disable MAC mid-session
4. Verify MAC presence matches state

**Expected**: MAC appears/disappears correctly

### 3. Signature Verification

**Flowgraph**: TX with signing, RX with verification

**Procedure**:
1. Transmit signed superframe
2. Receive and verify signature
3. Check signature_valid status

**Expected**: Signature verified successfully

### 4. Multi-Recipient

**Flowgraph**: TX with recipient list

**Procedure**:
1. Transmit to multiple recipients
2. Receive at each recipient station
3. Verify recipient checking

**Expected**: All recipients receive message

### 5. APRS Injection

**Flowgraph**: Voice + APRS multiplexing

**Procedure**:
1. Inject APRS into voice frames
2. Transmit superframe
3. Extract APRS data
4. Verify voice integrity

**Expected**: APRS extracted, voice intact

### 6. Backward Compatibility

**Flowgraph**: RX with require_signatures=False/True

**Procedure**:
1. Transmit unsigned message
2. Receive with require_signatures=False
3. Receive with require_signatures=True
4. Verify behavior

**Expected**: 
- Accepted when require_signatures=False
- Rejected when require_signatures=True

### 7. Recipient Checking

**Flowgraph**: RX with different local callsigns

**Procedure**:
1. Transmit to "N1ABC"
2. Receive at "N1ABC" (should process)
3. Receive at "N2DEF" (should handle gracefully)
4. Verify status messages

**Expected**: 
- Processed when addressed correctly
- Handled gracefully when not addressed

### 8. Latency Measurement

**Flowgraph**: End-to-end TX/RX loopback

**Procedure**:
1. Measure plaintext mode latency
2. Measure encrypted mode latency
3. Calculate overhead
4. Compare with targets

**Expected**: Overhead < 10%

## Running Integration Tests

### Setup

```bash
# Create test directories
mkdir -p tests/output
mkdir -p tests/public_keys

# Generate test keys
python3 tests/test_signature_verification.py
```

### Run Tests

```bash
# Individual tests
python3 tests/test_voice_text_multiplex.py
python3 tests/test_encryption_switching.py
# ... etc

# All tests
python3 tests/run_all_tests.py
```

## Test Data

### Synthetic Data

- Dummy Opus frames: 40 bytes of zeros
- Test callsigns: TEST, N0CALL, etc.
- Generated MAC keys: Random 32 bytes

### Real Data

For production testing:
- Real Opus-encoded audio
- Actual callsigns
- Pre-shared MAC keys
- Real GPS coordinates (for APRS)

## Performance Benchmarks

### Latency (per superframe)

- Plaintext: < 50 ms
- Encrypted: < 60 ms
- Signed: < 70 ms
- Overhead: < 10%

### Throughput

- Superframes per second: 1
- Voice frames per superframe: 24
- Total voice capacity: 960 bytes/second

## Troubleshooting

### Tests Fail

- Check Python path
- Verify dependencies installed
- Check file permissions

### Signature Tests Fail

- Generate test keys
- Verify key file permissions
- Check cryptography library

### Latency High

- Check system load
- Verify CPU frequency scaling
- Consider hardware acceleration

## Continuous Integration

For CI/CD:

```yaml
test:
  script:
    - python3 tests/run_all_tests.py
  timeout: 10m
```

