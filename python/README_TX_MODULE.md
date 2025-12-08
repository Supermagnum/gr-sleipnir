# gr-sleipnir TX Module - Quick Reference

Quick reference for the TX module. For complete documentation, see [examples/SLEIPNIR_TX_MODULE.md](../examples/SLEIPNIR_TX_MODULE.md).

## Quick Start

```python
from python.sleipnir_tx_hier import make_sleipnir_tx_hier

tx = make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_signing=False,
    enable_encryption=False
)
```

## Key Components

- **sleipnir_superframe_assembler.py** - Assembles superframes from Opus frames
- **sleipnir_tx_hier.py** - Hierarchical block wrapper
- **zmq_control_helper.py** - ZMQ control client

## Inputs

- **Audio**: `float32`, 8 kHz sample rate
- **Control**: PMT dict message port

## Outputs

- **RF**: `complex64`, RF sample rate

## Control Message Format

PMT dictionary with fields: `enable_signing`, `enable_encryption`, `recipient`, `message_type`, `mac_key`, etc.

For detailed documentation, see [examples/SLEIPNIR_TX_MODULE.md](../examples/SLEIPNIR_TX_MODULE.md).
