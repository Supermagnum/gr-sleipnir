# Crypto Block Wiring Guide

This document shows how to wire gr-linux-crypto and gr-nacl blocks into the gr-sleipnir TX/RX signal flow.

## TX Signal Flow with Crypto Blocks

### Complete TX Chain

```
Audio Input (float32, 8 kHz)
    ↓
[gr-opus] Opus Encoder
    ↓
[PDU: Opus frames, 24 frames × 40 bytes]
    ↓
[sleipnir] Superframe Assembler
    ├─ Collects 24 Opus frames
    ├─ Builds superframe data (960 bytes)
    └─ Outputs frame payloads
    ↓
[PDU: Frame payloads]
    ↓
┌─────────────────────────────────────────┐
│ Frame 0 Path (if signing enabled)      │
├─────────────────────────────────────────┤
│ Superframe Data (960 bytes)            │
│    ↓                                    │
│ [gr-linux-crypto] ECDSA Sign Block     │
│    Input: Superframe data (blob)       │
│    Output: Signature (32 bytes, blob)  │
│    ↓                                    │
│ Frame 0 Payload (32 bytes)             │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Frames 1-24 Path (if encryption)       │
├─────────────────────────────────────────┤
│ Opus Frame (40 bytes)                   │
│    ↓                                    │
│ [gr-nacl] ChaCha20-Poly1305 Encrypt    │
│    Input: Plaintext (blob)             │
│    Output: (ciphertext, mac) pair      │
│    ↓                                    │
│ Voice Frame Builder                     │
│    Combines: Opus + MAC + metadata     │
│    Output: Frame payload (48 bytes)    │
└─────────────────────────────────────────┘
    ↓
[PDU: Frame payloads, 25 frames]
    ↓
[sleipnir] Frame-Aware LDPC Encoder
    ├─ Frame 0: Auth matrix (rate 1/3)
    │   32 bytes → 96 bytes (768 bits)
    └─ Frames 1-24: Voice matrix (rate 2/3)
       48 bytes → 72 bytes (576 bits)
    ↓
[PDU: Encoded bits]
    ↓
[gr-digital] Symbol Mapper (4FSK/8FSK)
    ↓
[gr-analog] Frequency Modulator
    ↓
RF Output (complex64, RF sample rate)
```

### GRC Block Connections (TX)

```
Audio Source
    ↓
Opus Encoder (gr-opus)
    ↓
Stream to PDU
    ↓
Superframe Assembler (sleipnir)
    ├─ Message Port: "ctrl" (control messages)
    └─ Message Port: "out" (frame payloads)
    ↓
PDU Splitter (conditional routing)
    ├─ Frame 0 → ECDSA Sign Block (if signing)
    └─ Frames 1-24 → ChaCha20 Encrypt Block (if encryption)
    ↓
PDU Merger
    ↓
Frame-Aware LDPC Encoder (sleipnir)
    ├─ Auth matrix: ldpc_auth_768_256.alist
    └─ Voice matrix: ldpc_voice_576_384.alist
    ↓
PDU to Stream
    ↓
Symbol Mapper (gr-digital)
    ↓
Frequency Modulator (gr-analog)
    ↓
RF Sink
```

## RX Signal Flow with Crypto Blocks

### Complete RX Chain

```
RF Input (complex64, RF sample rate)
    ↓
[gr-analog] Frequency Demodulator
    ↓
[gr-digital] Symbol Demapper (4FSK/8FSK)
    ↓
[PDU: Soft bits]
    ↓
[sleipnir] Frame-Aware LDPC Decoder
    ├─ Frame 0: Auth matrix (rate 1/3)
    │   96 bytes (768 bits) → 32 bytes
    └─ Frames 1-24: Voice matrix (rate 2/3)
       72 bytes (576 bits) → 48 bytes
    ↓
[PDU: Decoded frame payloads]
    ↓
[sleipnir] Superframe Parser
    ├─ Extracts frames
    ├─ Identifies Frame 0 vs voice frames
    └─ Routes to appropriate crypto blocks
    ↓
┌─────────────────────────────────────────┐
│ Frame 0 Path (if signature present)    │
├─────────────────────────────────────────┤
│ Frame 0 Payload (32 bytes)            │
│    ↓                                    │
│ [gr-linux-crypto] ECDSA Verify Block   │
│    Input: (data, signature) pair     │
│    Output: Verified data + status      │
│    Metadata: signature_valid (bool)   │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Frames 1-24 Path (if encrypted)        │
├─────────────────────────────────────────┤
│ Voice Frame Payload (48 bytes)         │
│    Extract: Opus + MAC + metadata     │
│    ↓                                    │
│ [gr-nacl] ChaCha20-Poly1305 Decrypt   │
│    Input: (ciphertext, mac) pair      │
│    Output: Plaintext + MAC status      │
│    Metadata: mac_valid (bool)          │
│    ↓                                    │
│ Opus Frame (40 bytes)                  │
└─────────────────────────────────────────┘
    ↓
[PDU: Opus frames, 24 frames]
    ↓
[gr-opus] Opus Decoder
    ↓
Audio Output (float32, 8 kHz)
```

### GRC Block Connections (RX)

```
RF Source
    ↓
Frequency Demodulator (gr-analog)
    ↓
Symbol Demapper (gr-digital)
    ↓
Stream to PDU
    ↓
Frame-Aware LDPC Decoder (sleipnir)
    ├─ Auth matrix: ldpc_auth_768_256.alist
    └─ Voice matrix: ldpc_voice_576_384.alist
    ↓
PDU: Decoded frames
    ↓
Superframe Parser (sleipnir)
    ├─ Message Port: "in" (decoded frames)
    ├─ Message Port: "out" (Opus frames)
    ├─ Message Port: "status" (status messages)
    └─ Routes frames:
        ├─ Frame 0 → ECDSA Verify Block
        └─ Frames 1-24 → ChaCha20 Decrypt Block
    ↓
PDU Merger
    ↓
PDU to Stream
    ↓
Opus Decoder (gr-opus)
    ↓
Audio Sink
```

## Integration Points

### TX Integration

1. **Superframe Assembler** → **ECDSA Sign Block** (Frame 0)
   - Connection: Message port "out" → Message port "in"
   - Data flow: Superframe data (blob) → Signature (blob)

2. **Superframe Assembler** → **ChaCha20 Encrypt Block** (Frames 1-24)
   - Connection: Message port "out" → Message port "in"
   - Data flow: Opus frame (blob) → (ciphertext, mac) pair

3. **Crypto Blocks** → **LDPC Encoder**
   - Connection: Message port "out" → Message port "in"
   - Data flow: Frame payloads (blob) → Encoded bits

### RX Integration

1. **LDPC Decoder** → **Superframe Parser**
   - Connection: Message port "out" → Message port "in"
   - Data flow: Decoded frames (blob) → Parsed frames

2. **Superframe Parser** → **ECDSA Verify Block** (Frame 0)
   - Connection: Message port "out" → Message port "verify_in"
   - Data flow: (data, signature) pair → Verified data

3. **Superframe Parser** → **ChaCha20 Decrypt Block** (Frames 1-24)
   - Connection: Message port "out" → Message port "decrypt_in"
   - Data flow: (ciphertext, mac) pair → Plaintext

4. **Crypto Blocks** → **Opus Decoder**
   - Connection: Message port "out" → Message port "in"
   - Data flow: Opus frames (blob) → Audio samples

## Conditional Routing

### TX: Enable/Disable Crypto

Use PDU-based conditional routing:

```python
# In Superframe Assembler
if self.enable_signing:
    # Route Frame 0 to ECDSA Sign Block
    self.message_port_pub("sign_in", frame_0_pdu)
else:
    # Route Frame 0 directly to LDPC Encoder
    self.message_port_pub("ldpc_in", frame_0_pdu)

if self.enable_encryption:
    # Route voice frames to ChaCha20 Encrypt Block
    self.message_port_pub("encrypt_in", voice_frame_pdu)
else:
    # Route voice frames directly to LDPC Encoder
    self.message_port_pub("ldpc_in", voice_frame_pdu)
```

### RX: Detect Crypto Usage

Parse frame metadata to determine routing:

```python
# In Superframe Parser
if frame_type == "auth" and signature_present:
    # Route to ECDSA Verify Block
    self.message_port_pub("verify_in", auth_frame_pdu)
elif frame_type == "voice" and mac_present:
    # Route to ChaCha20 Decrypt Block
    self.message_port_pub("decrypt_in", voice_frame_pdu)
else:
    # Route directly to Opus Decoder (plaintext)
    self.message_port_pub("opus_in", frame_pdu)
```

## Performance Considerations

### Latency

- **ECDSA Signing**: ~5-10ms (adds to Frame 0 processing)
- **ECDSA Verification**: ~5-10ms (adds to Frame 0 processing)
- **ChaCha20 Encryption**: ~0.1-0.5ms per frame (minimal impact)
- **ChaCha20 Decryption**: ~0.1-0.5ms per frame (minimal impact)

### Throughput

- **ECDSA**: Limited by key operations (~100-200 ops/sec)
- **ChaCha20**: High throughput (~100+ MB/s)

### Memory

- **Frame buffers**: Store frames during crypto operations
- **Key storage**: Load keys at initialization
- **PDU buffers**: Temporary storage for PDU processing

## Error Handling

### TX Errors

- **ECDSA Signing Failure**: Emit Frame 0 with zeros (unsigned)
- **ChaCha20 Encryption Failure**: Emit plaintext frame (no MAC)

### RX Errors

- **ECDSA Verification Failure**: Mark signature_valid=False, continue processing
- **ChaCha20 MAC Failure**: Mark mac_valid=False, discard frame or emit with warning

## Testing

### Test Crypto Integration

1. **TX with signing**:
   - Enable signing
   - Verify Frame 0 contains valid signature
   - Check signature is 32 bytes

2. **RX with verification**:
   - Enable verification
   - Verify signature_valid=True for valid signatures
   - Verify signature_valid=False for invalid signatures

3. **TX with encryption**:
   - Enable encryption
   - Verify voice frames contain MAC
   - Check MAC is 8 bytes (truncated from 16)

4. **RX with decryption**:
   - Enable decryption
   - Verify MAC validation works
   - Check decrypted frames match original

