# Superframe Python API - Quick Reference

Quick reference for superframe Python components. For complete implementation guide, see [SUPERFRAME_IMPLEMENTATION.md](../SUPERFRAME_IMPLEMENTATION.md).

## Quick Start

```python
from python.superframe_controller import SuperframeController
from python.voice_frame_builder import VoiceFrameBuilder

# Build voice frames
builder = VoiceFrameBuilder(callsign="N0CALL", enable_mac=False)
frame = builder.build_frame(opus_data, frame_num=1)

# Parse voice frames
parsed = builder.parse_frame(frame_payload)
```

## Key Components

- **superframe_controller.py** - Manages frame timing and flowgraph execution
- **voice_frame_builder.py** - Builds/parses voice frame payloads
- **crypto_helpers.py** - ECDSA signatures and ChaCha20-Poly1305 MAC

## Frame Structure

- **Frame 0**: Authentication (256 bits -> 768 bits coded, rate 1/3)
- **Frames 1-24**: Voice (384 bits -> 576 bits coded, rate 2/3)

## Voice Frame Payload

48 bytes total:
- Opus data: 40 bytes
- MAC: 8 bytes
- Callsign/metadata: In metadata, not payload

For detailed documentation, see [SUPERFRAME_IMPLEMENTATION.md](../SUPERFRAME_IMPLEMENTATION.md).
