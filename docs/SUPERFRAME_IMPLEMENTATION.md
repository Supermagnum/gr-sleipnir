# Superframe Implementation Guide

This guide explains how to implement and use the superframe transmission system for gr-sleipnir.

## Overview

The superframe system transmits 25 frames per second (1 second total):
- **Frame 0**: Authentication frame with ECDSA signature (256 bits -> 768 bits coded)
- **Frames 1-24**: Voice frames with Opus audio + MAC (384 bits -> 576 bits coded)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│         Superframe Controller (Python)                  │
│  - Frame timing (40ms per frame)                        │
│  - Payload construction                                 │
│  - Flowgraph orchestration                              │
└─────────────────────────────────────────────────────────┘
         │                    │
         │                    │
    ┌────▼────┐         ┌────▼────┐
    │  Auth   │         │  Voice  │
    │ Frame 0 │         │Frames 1-│
    │ Flowgraph│         │   24    │
    └─────────┘         │Flowgraph│
                         └─────────┘
```

## Components

### 1. Python Modules

Located in `python/`:

- **superframe_controller.py**: Main controller for frame timing and flowgraph execution
- **crypto_helpers.py**: ECDSA signatures and ChaCha20-Poly1305 MAC computation
- **voice_frame_builder.py**: Builds voice frame payloads from Opus audio
- **example_superframe_tx.py**: Example usage script

### 2. Flowgraphs

Located in `examples/`:

- **tx_auth_frame.grc**: Authentication frame transmitter (to be created)
- **tx_4fsk_opus_voice.grc**: Voice frame transmitter (modify from tx_4fsk_opus.grc)

### 3. LDPC Matrices

Located in `ldpc_matrices/`:

- **ldpc_auth_768_256.alist**: Rate 1/3 (256 -> 768 bits)
- **ldpc_voice_576_384.alist**: Rate 2/3 (384 -> 576 bits)

## Quick Start

### 1. Install Dependencies

```bash
# GNU Radio (already installed)
# Opus libraries (already installed)
# Optional: gr-linux-crypto for ECDSA
# Optional: gr-nacl for ChaCha20-Poly1305
# Fallback: cryptography library (pip install cryptography)
```

### 2. Create Flowgraphs

#### Voice Frame Flowgraph (tx_4fsk_opus_voice.grc)

Modify `tx_4fsk_opus.grc`:

1. Remove audio processing blocks:
   - Remove `blocks_wavfile_source_0`
   - Remove `low_pass_filter_0`
   - Remove `gr_opus_opus_encoder_0`

2. Add file source:
   - Add `blocks_file_source` block
   - Set type to `byte`
   - Set file to payload file variable
   - Set `repeat: False`

3. Update LDPC matrix:
   - Change `ldpc_matrix_file` to `"../ldpc_matrices/ldpc_voice_576_384.alist"`
   - Update `ldpc_encoder_def` file path

4. Update connections:
   - Connect file source directly to LDPC encoder

#### Authentication Frame Flowgraph (tx_auth_frame.grc)

Create new flowgraph based on voice frame flowgraph:

1. Use file source (32 bytes instead of 48)
2. Use `ldpc_auth_768_256.alist` matrix
3. Same 4FSK modulation chain

### 3. Test Superframe Transmission

```bash
cd python
python3 example_superframe_tx.py
```

## Frame Payload Structure

### Voice Frame (384 bits = 48 bytes)

```
Bytes 0-39:   Opus voice data (40 bytes)
Bytes 40-55:  ChaCha20-Poly1305 MAC (16 bytes)
Bytes 56-60:  Callsign (5 bytes, ASCII)
Byte 61:      Frame counter (1 byte, 1-24)
Bytes 62-64:  Reserved (3 bytes)
```

### Authentication Frame (256 bits = 32 bytes)

```
Bytes 0-31:   ECDSA signature (32 bytes, BrainpoolP256r1)
```

## Integration with gr-linux-crypto

When gr-linux-crypto is available:

```python
from python.crypto_helpers import load_private_key, generate_ecdsa_signature

# Load key from Nitrokey or kernel keyring
private_key = load_private_key("/path/to/key")

# Generate signature
signature = generate_ecdsa_signature(data, private_key)
```

The `crypto_helpers` module automatically detects and uses gr-linux-crypto when available.

## Integration with gr-nacl

When gr-nacl is available:

```python
from python.crypto_helpers import compute_chacha20_mac

# Compute MAC
mac = compute_chacha20_mac(data, key)  # 16 bytes
```

The `crypto_helpers` module automatically detects and uses gr-nacl when available.

## Production Usage

### 1. Audio Encoding

```python
from gnuradio import gr_opus

# Initialize Opus encoder (6 kbps, 8 kHz, mono)
opus_encoder = gr_opus.opus_encoder(
    sample_rate=8000,
    channels=1,
    bitrate=6000
)

# Encode 40ms of audio (320 samples at 8kHz)
audio_samples = get_audio_chunk()  # 640 bytes (320 samples * 2 bytes)
opus_frame = opus_encoder.encode(audio_samples)  # 40 bytes
```

### 2. Superframe Transmission

```python
from python.superframe_controller import SuperframeController

controller = SuperframeController(
    project_root="/path/to/gr-sleipnir",
    callsign="N0CALL",
    private_key_path="/path/to/key.pem",
    enable_auth=True,
    enable_mac=True
)

# Generate 24 Opus frames
opus_frames = []
for i in range(24):
    audio = get_audio_chunk(i)
    opus_frame = opus_encoder.encode(audio)
    opus_frames.append(opus_frame)

# Transmit superframe
mac_key = get_shared_mac_key()  # From key exchange
controller.transmit_superframe(opus_frames, mac_key=mac_key)
```

### 3. Key Management

- **ECDSA Keys**: Store in Nitrokey HSM or kernel keyring
- **MAC Keys**: Exchange via ECDH (off-air) or pre-shared
- **Key Rotation**: Implement periodic key updates

## Error Handling

The system gracefully handles:
- Missing crypto libraries (falls back to standard libraries)
- Missing keys (disables authentication/MAC)
- Flowgraph errors (returns False, logs error)
- Payload size mismatches (warns, continues)

## Performance Considerations

- **Frame Timing**: 40ms per frame, 1 second per superframe
- **LDPC Encoding**: ~1-2ms per frame (depends on CPU)
- **Crypto Operations**: 
  - ECDSA signing: ~5-10ms (software)
  - MAC computation: ~0.1ms
- **Flowgraph Execution**: ~10-20ms per frame

Total overhead: ~15-30ms per frame (within 40ms budget)

## Testing

### Without Cryptography

```python
controller = SuperframeController(
    project_root="/path/to/gr-sleipnir",
    callsign="TEST",
    enable_auth=False,
    enable_mac=False
)
```

### With Dummy Data

```python
opus_frames = [b'\x00' * 40] * 24
controller.transmit_superframe(opus_frames)
```

## Troubleshooting

### Flowgraph Not Found

- Verify flowgraph paths in `SuperframeController.__init__`
- Check that flowgraphs exist in `examples/` directory

### LDPC Matrix Not Found

- Verify matrix files exist in `ldpc_matrices/`
- Check matrix file paths in flowgraph variables

### Crypto Operations Fail

- Check if gr-linux-crypto/gr-nacl are installed
- Verify key file paths and formats
- Check fallback library availability (cryptography)

### Frame Timing Issues

- Verify system clock accuracy
- Check for flowgraph execution delays
- Consider using real-time scheduling

## Next Steps

1. **Create Flowgraphs**: Modify tx_4fsk_opus.grc and create tx_auth_frame.grc
2. **Test with Real Audio**: Integrate actual Opus encoding
3. **Implement Receiver**: Create rx flowgraphs for both frame types
4. **Key Exchange**: Implement ECDH for MAC key sharing
5. **Frame Synchronization**: Add superframe sync detection

## References

- `python/README_SUPERFRAME.md`: Detailed Python API documentation
- `examples/SUPERFRAME_FLOWGRAPHS.md`: Flowgraph modification guide
- `ldpc_matrices/SUPERFRAME_LDPC.md`: LDPC matrix specifications


