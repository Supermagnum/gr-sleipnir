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
- **aprs_in**: APRS packet input (PMT blob/u8vector, optional) - APRS packets for transmission
- **text_in**: Text message input (PMT blob/u8vector/symbol, optional) - text messages for transmission

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

### aprs_in Message Port

Receives APRS packets for transmission. APRS packets are multiplexed into voice frames within the superframe.

**Input format**: PMT pair `(meta, data)` where:
- `meta`: PMT dictionary (optional metadata)
- `data`: PMT blob or u8vector containing APRS packet data (UTF-8 encoded)

**Example**:
```python
from gnuradio.gr import pmt

# Create APRS packet
aprs_data = b"TEST,59.9139,10.7522,100"  # callsign,lat,lon,alt
aprs_pmt = pmt.init_u8vector(len(aprs_data), list(aprs_data))
meta = pmt.make_dict()
tx.message_port_pub(pmt.intern("aprs_in"), pmt.cons(meta, aprs_pmt))
```

**Behavior**:
- APRS packets are queued and inserted into superframes with priority over voice frames
- Each APRS packet is split into 39-byte chunks (one per frame)
- APRS frames replace voice frames in the superframe when available
- APRS and voice can be transmitted simultaneously

### text_in Message Port

Receives text messages for transmission. Text messages are multiplexed into voice frames within the superframe.

**Input format**: PMT pair `(meta, data)` where:
- `meta`: PMT dictionary (optional metadata)
- `data`: PMT symbol (string), blob, or u8vector containing text message (UTF-8 encoded)

**Example**:
```python
from gnuradio.gr import pmt

# Create text message
text_data = b"Hello from gr-sleipnir!"
text_pmt = pmt.init_u8vector(len(text_data), list(text_data))
meta = pmt.make_dict()
tx.message_port_pub(pmt.intern("text_in"), pmt.cons(meta, text_pmt))
```

**Behavior**:
- Text messages are queued and inserted into superframes with priority over voice frames (but after APRS)
- Each text message is split into 39-byte chunks (one per frame)
- Text frames replace voice frames in the superframe when available
- Text and voice can be transmitted simultaneously

**Frame Priority**: APRS > Text > Voice

For detailed documentation, see [examples/SLEIPNIR_TX_MODULE.md](../examples/SLEIPNIR_TX_MODULE.md).
