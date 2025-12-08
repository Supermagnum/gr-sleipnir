# gr-sleipnir RX Module - Quick Reference

Quick reference for the RX module. For complete documentation, see [examples/SLEIPNIR_RX_MODULE.md](../examples/SLEIPNIR_RX_MODULE.md).

## Quick Start

```python
from python.sleipnir_rx_hier import make_sleipnir_rx_hier

rx = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    require_signatures=False
)
```

## Key Components

- **sleipnir_superframe_parser.py** - Parses superframes and handles verification/decryption
- **sleipnir_rx_hier.py** - Hierarchical block wrapper
- **zmq_status_output.py** - ZMQ status and audio output

## Inputs

- **RF**: `complex64`, RF sample rate
- **Decoded Bits**: PDU message port from LDPC decoder

## Outputs

- **Audio**: `float32`, 8 kHz sample rate
- **Status**: PMT dict message port
- **ZMQ**: Status and audio via ZMQ PUB

## Status Message Format

PMT dictionary with fields: `signature_valid`, `encrypted`, `decrypted_successfully`, `sender`, `recipients`, `message_type`, etc.

For detailed documentation, see [examples/SLEIPNIR_RX_MODULE.md](../examples/SLEIPNIR_RX_MODULE.md).
