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

- **Audio**: `float32`, 8 kHz sample rate (stream)
- **ctrl**: Control messages (PMT dict, optional) - configuration updates
- **key_source**: Key source messages (PMT dict, optional) - keys from `gr-linux-crypto` blocks

## Outputs

- **RF**: `complex64`, RF sample rate (stream)

## Message Ports

### ctrl Message Port

PMT dictionary with fields:
- `enable_signing`: Enable/disable ECDSA signing
- `enable_encryption`: Enable/disable encryption
- `recipient`: Recipient callsign(s)
- `message_type`: Message type
- `mac_key`: MAC key (32 bytes, u8vector)
- `callsign`: Update callsign
- `private_key`: Private key (PEM/DER bytes, u8vector)

### key_source Message Port

Receives keys from `gr-linux-crypto` blocks (`kernel_keyring_source`, `nitrokey_interface`).

PMT dictionary with fields:
- `private_key`: Private key (PEM/DER bytes, u8vector)
- `mac_key`: MAC key (32 bytes, u8vector)
- `key_id`: Key identifier (symbol, optional)

Keys received on `key_source` are automatically forwarded to internal blocks via `ctrl` message port.

For detailed documentation, see [examples/SLEIPNIR_TX_MODULE.md](../examples/SLEIPNIR_TX_MODULE.md).
