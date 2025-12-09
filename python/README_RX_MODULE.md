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

- **RF**: `complex64`, RF sample rate (stream)
- **ctrl**: Control messages (PMT dict, optional) - configuration updates
- **key_source**: Key source messages (PMT dict, optional) - keys from `gr-linux-crypto` blocks

## Outputs

- **Audio**: `float32`, 8 kHz sample rate (stream)
- **status**: Status messages (PMT dict, optional) - signature/decryption status
- **audio_pdu**: Audio PDUs (PMT blob, optional) - decoded audio frames
- **ZMQ**: Status and audio via ZMQ PUB

## Message Ports

### ctrl Message Port

PMT dictionary with fields:
- `local_callsign`: Update local callsign
- `require_signatures`: Require valid signatures
- `private_key`: Private key for decryption (PEM/DER bytes, u8vector)
- `public_key`: Public key for verification (PEM/DER bytes, u8vector)
- `key_id`: Key identifier (symbol, optional)

### key_source Message Port

Receives keys from `gr-linux-crypto` blocks (`kernel_keyring_source`, `nitrokey_interface`).

PMT dictionary with fields:
- `private_key`: Private key for decryption (PEM/DER bytes, u8vector)
- `public_key`: Public key for verification (PEM/DER bytes, u8vector)
- `key_id`: Key identifier (symbol, optional)

Keys received on `key_source` are automatically forwarded to internal blocks via `ctrl` message port.

### status Message Port

PMT dictionary with fields: `signature_valid`, `encrypted`, `decrypted_successfully`, `sender`, `recipients`, `message_type`, etc.

For detailed documentation, see [examples/SLEIPNIR_RX_MODULE.md](../examples/SLEIPNIR_RX_MODULE.md).
