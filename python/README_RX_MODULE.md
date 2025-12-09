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
- **aprs_out**: APRS packet output (PMT blob, optional) - decoded APRS packets
- **text_out**: Text message output (PMT blob, optional) - decoded text messages
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

PMT dictionary with fields: `signature_valid`, `encrypted`, `decrypted_successfully`, `sender`, `recipients`, `message_type`, `aprs_count`, `text_count`, etc.

### aprs_out Message Port

Outputs decoded APRS packets received in superframes.

**Output format**: PMT pair `(meta, data)` where:
- `meta`: PMT dictionary containing:
  - `sender`: Sender callsign (symbol)
  - `message_type`: "aprs" (symbol)
  - `packet_count`: Number of APRS packet frames (long)
- `data`: PMT u8vector containing concatenated APRS packet data

**Example**:
```python
def handle_aprs(msg):
    meta = pmt.car(msg)
    data = pmt.cdr(msg)
    sender = pmt.symbol_to_string(pmt.dict_ref(meta, pmt.intern("sender"), pmt.PMT_NIL))
    aprs_data = bytes(pmt.u8vector_elements(data))
    print(f"APRS from {sender}: {aprs_data.decode('utf-8')}")

rx.set_msg_handler(pmt.intern("aprs_out"), handle_aprs)
```

**Behavior**:
- APRS packets are extracted from superframes and output separately from audio
- APRS data is guaranteed NOT to appear in audio output
- Multiple APRS frames are concatenated into a single output message

### text_out Message Port

Outputs decoded text messages received in superframes.

**Output format**: PMT pair `(meta, data)` where:
- `meta`: PMT dictionary containing:
  - `sender`: Sender callsign (symbol)
  - `message_type`: "text" (symbol)
  - `message_count`: Number of text message frames (long)
- `data`: PMT u8vector containing concatenated text message data

**Example**:
```python
def handle_text(msg):
    meta = pmt.car(msg)
    data = pmt.cdr(msg)
    sender = pmt.symbol_to_string(pmt.dict_ref(meta, pmt.intern("sender"), pmt.PMT_NIL))
    text_data = bytes(pmt.u8vector_elements(data))
    print(f"Text from {sender}: {text_data.decode('utf-8')}")

rx.set_msg_handler(pmt.intern("text_out"), handle_text)
```

**Behavior**:
- Text messages are extracted from superframes and output separately from audio
- Text data is guaranteed NOT to appear in audio output
- Multiple text frames are concatenated into a single output message

**Critical Validation**:
- APRS packets and text messages are completely separated from audio output
- Frame type identification ensures proper routing
- No cross-contamination between voice, APRS, and text data types

For detailed documentation, see [examples/SLEIPNIR_RX_MODULE.md](../examples/SLEIPNIR_RX_MODULE.md).
