# Superframe LDPC Integration Guide

This guide explains how to integrate the frame-aware LDPC matrices into gr-sleipnir flowgraphs.

## Superframe Structure

- **Superframe**: 25 frames (1 second total)
- **Frame 0**: Authentication frame with BrainpoolP256r1 signature
- **Frames 1-24**: Voice frames with Opus audio + MAC

## LDPC Matrix Usage

### Frame 0: Authentication Frame
- **Matrix**: `ldpc_auth_768_256.alist`
- **Rate**: 1/3 (256 bits info → 768 bits coded)
- **Purpose**: Protect signature (must be error-free)

### Frames 1-24: Voice Frames
- **Matrix**: `ldpc_voice_576_384.alist`
- **Rate**: 2/3 (384 bits info → 576 bits coded)
- **Purpose**: Protect voice + MAC + metadata

## Integration Methods

### Method 1: Separate Flowgraphs (Simplest)

Create two separate flowgraphs:
1. **Authentication flowgraph**: Uses `ldpc_auth_768_256.alist`
2. **Voice flowgraph**: Uses `ldpc_voice_576_384.alist`

Switch between them based on frame number in your application logic.

### Method 2: Frame-Aware Python Blocks

Use the `frame_aware_ldpc.py` module which automatically switches matrices:

```python
from frame_aware_ldpc import frame_aware_ldpc_encoder, frame_aware_ldpc_decoder

# In GRC, use Embedded Python block
encoder = frame_aware_ldpc_encoder(
    '../ldpc_matrices/ldpc_auth_768_256.alist',
    '../ldpc_matrices/ldpc_voice_576_384.alist'
)
```

### Method 3: Dual Path Architecture

Create parallel encoder/decoder paths:
- Path 1: Auth frame encoder/decoder (rate 1/3)
- Path 2: Voice frame encoder/decoder (rate 2/3)
- Use a frame detector to route frames to the correct path

## Current Flowgraph Updates

The following flowgraphs have been updated to use the voice frame matrix for testing:

- `som_4fsk_file.grc` - Now uses `ldpc_voice_576_384.alist` (rate 2/3)
- `som_8fsk_file.grc` - Now uses `ldpc_voice_576_384.alist` (rate 2/3)

These can be used to test the voice frame LDPC matrix.

## Testing the Matrices

### Test 1: Validate Matrix Files

```bash
cd examples
grcc som_4fsk_file.grc
```

Should show no "Bad AList file name!" errors.

### Test 2: Verify Matrix Loading

The flowgraphs should load without errors in GNU Radio Companion.

### Test 3: Frame Structure

For full superframe implementation:
1. Implement frame synchronization
2. Detect frame 0 vs frames 1-24
3. Route to appropriate LDPC encoder/decoder

## Frame Payload Sizes

### Authentication Frame (Frame 0)
- **Input**: 256 bits (32 bytes)
  - Signature: 256 bits (BrainpoolP256r1)
- **LDPC Encoded**: 768 bits (96 bytes)
- **Matrix**: Rate 1/3

### Voice Frame (Frames 1-24)
- **Input**: 384 bits (48 bytes)
  - Opus voice: 320 bits (40 bytes)
  - ChaCha20 MAC: 128 bits (16 bytes)
  - Callsign: 40 bits (5 bytes)
  - Frame counter: 8 bits (1 byte)
  - Reserved: 24 bits (3 bytes)
- **LDPC Encoded**: 576 bits (72 bytes)
- **Matrix**: Rate 2/3

## Next Steps

1. **Frame Synchronization**: Implement frame boundary detection
2. **Frame Counter**: Add frame counter for superframe tracking
3. **Authentication**: Integrate BrainpoolP256r1 signature in frame 0
4. **MAC Integration**: Add ChaCha20-Poly1305 MAC to voice frames
5. **Performance Testing**: Validate error correction performance

## References

- `ldpc_matrices/SUPERFRAME_LDPC.md` - Detailed matrix specifications
- `python/frame_aware_ldpc.py` - Frame-aware LDPC encoder/decoder implementation
- `ldpc_matrices/create_custom_ldpc.py` - Matrix generation script

