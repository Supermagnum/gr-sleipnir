# gr-sleipnir RX Module Documentation

## Overview

The gr-sleipnir RX module provides a complete receive chain for superframe-based digital voice communication with signature verification and decryption.

## Architecture

```
RF Input (complex64, RF sample rate)
    ↓
4FSK/8FSK Demodulator
    ↓
Symbol Sync & Slicing
    ↓
LDPC Decoder (fec.ldpc_decoder)
    ├─ Auth frame: ldpc_auth_768_256.alist (rate 1/3)
    └─ Voice frames: ldpc_voice_576_384.alist (rate 2/3)
    ↓
Superframe Parser (Python block)
    ├─ Frame desynchronization
    ├─ Signature verification
    ├─ Recipient checking
    ├─ Decryption
    └─ Status reporting
    ↓
Opus Decoder (gr-opus)
    ↓
Audio Output (float32, 8 kHz)
```

## Components

### 1. Python Blocks

Located in `python/`:

- **sleipnir_superframe_parser.py**: Parses superframes, verifies signatures, decrypts
- **sleipnir_rx_block.py**: Main RX block (simplified)
- **sleipnir_rx_hier.py**: Hierarchical block wrapper
- **zmq_status_output.py**: ZMQ output for status and audio

### 2. Available GNU Radio Blocks

The module uses only available blocks:

- **gr-opus**: `gr_opus.opus_decoder` - Opus audio decoding
- **fec**: `fec.ldpc_decoder` - LDPC forward error correction
- **digital**: `digital.symbol_sync_xx` - Symbol timing recovery
- **filter**: `filter.root_raised_cosine` - Matched filtering
- **analog**: `analog.quadrature_demod_cf` - FSK demodulation
- **zeromq**: `zeromq.pub_sink` - ZMQ output
- **pdu**: `pdu.tagged_stream_to_pdu`, `pdu.pdu_to_tagged_stream` - PDU handling

## Usage

### Basic Usage in Python

```python
from gnuradio import gr, blocks
from python.sleipnir_rx_hier import make_sleipnir_rx_hier

# Create RX block
rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    private_key_path="/path/to/private.pem",
    require_signatures=False,
    public_key_store_path="/path/to/public_keys"
)

# Connect to flowgraph
tb = gr.top_block()
tb.connect(rf_source, rx_block)
tb.connect(rx_block, audio_sink)

# Connect status output
def handle_status(msg):
    # Process status message
    pass

rx_block.message_port_register_hier_out("status")
rx_block.set_msg_handler("status", handle_status)

tb.run()
```

### Configuration

#### Local Callsign

Read from radio configuration or set explicitly:

```python
rx_block.set_local_callsign("N0CALL")
```

#### Private Key

For decryption of messages addressed to this station:

```python
rx_block = make_sleipnir_rx_hier(
    private_key_path="/path/to/private.pem"
)
```

#### Require Signatures

Reject unsigned messages:

```python
rx_block = make_sleipnir_rx_hier(
    require_signatures=True
)
```

#### Public Key Store

Directory containing public keys for signature verification:

```
public_key_store/
├── N0CALL.pem
├── N1ABC.pem
└── N2DEF.pem
```

## Status Messages

Status messages are emitted as PMT dictionaries:

```python
{
    'signature_valid': bool,           # ECDSA signature valid
    'encrypted': bool,                 # Message was encrypted
    'decrypted_successfully': bool,    # Decryption succeeded
    'sender': str,                     # Sender callsign
    'recipients': str,                 # Recipient callsigns (comma-separated)
    'message_type': str,               # 'voice', 'text', 'aprs', etc.
    'frame_counter': int,              # Frames in superframe
    'superframe_counter': int          # Superframe sequence number
}
```

### Handling Status Messages

```python
def handle_status(msg):
    if not pmt.is_dict(msg):
        return
    
    signature_valid = pmt.to_bool(
        pmt.dict_ref(msg, pmt.intern("signature_valid"), pmt.PMT_F)
    )
    sender = pmt.symbol_to_string(
        pmt.dict_ref(msg, pmt.intern("sender"), pmt.PMT_NIL)
    )
    
    print(f"Message from {sender}: signature_valid={signature_valid}")

rx_block.message_port_register_hier_out("status")
rx_block.set_msg_handler("status", handle_status)
```

## ZMQ Output

### Status Messages

ZMQ PUB socket publishes status messages as JSON:

```python
from python.zmq_status_output import make_zmq_status_output

zmq_output = make_zmq_status_output(
    status_address="tcp://*:5556",
    audio_address="tcp://*:5557"
)

# Connect status port
rx_block.message_port_register_hier_out("status")
rx_block.msg_connect(rx_block, "status", zmq_output, "status")
```

### Audio Output

ZMQ PUB socket publishes audio PDUs:

```python
# Connect audio port
rx_block.message_port_register_hier_out("audio_pdu")
rx_block.msg_connect(rx_block, "audio_pdu", zmq_output, "audio")
```

### Remote Consumer

```python
import zmq
import json

# Status subscriber
status_context = zmq.Context()
status_socket = status_context.socket(zmq.SUB)
status_socket.connect("tcp://radio.local:5556")
status_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# Audio subscriber
audio_context = zmq.Context()
audio_socket = audio_context.socket(zmq.SUB)
audio_socket.connect("tcp://radio.local:5557")
audio_socket.setsockopt_string(zmq.SUBSCRIBE, "")

while True:
    # Receive status
    status_json = status_socket.recv_string()
    status = json.loads(status_json)
    print(f"Status: {status}")
    
    # Receive audio
    metadata_json = audio_socket.recv_string()
    audio_data = audio_socket.recv()
    metadata = json.loads(metadata_json)
    print(f"Audio from {metadata['sender']}: {len(audio_data)} bytes")
```

## Signature Verification

### Public Key Store

Store public keys in directory:

```
public_keys/
├── N0CALL.pem
├── N1ABC.pem
└── N2DEF.pem
```

### Verification Process

1. Extract sender callsign from Frame 1 (first voice frame)
2. Look up sender's public key from key store
3. Verify ECDSA signature from Frame 0
4. Set `signature_valid` status accordingly

### Handling Unsigned Messages

If `require_signatures=False`:
- Unsigned messages are accepted
- `signature_valid` is set to `False`
- Status message indicates unsigned message

If `require_signatures=True`:
- Unsigned messages are rejected
- Status message indicates rejection
- No audio output

## Recipient Checking

The parser checks if the local callsign matches recipients:

```python
# Recipients extracted from metadata
recipients = "N0CALL,N1ABC"

# Check if this station is recipient
if local_callsign in recipients.split(","):
    # Process message
    pass
```

## Decryption

### When Decryption Occurs

- Message is encrypted (`encrypted=True`)
- Local callsign is in recipient list
- Private key is available

### Decryption Process

1. Extract encrypted payload
2. Use local private key to decrypt
3. Set `decrypted_successfully` status
4. Extract decrypted Opus frames

### Handling Plaintext Messages

- `encrypted=False` in status
- No decryption attempted
- Opus frames extracted directly

## Message Types

Supported message types:

- **voice**: Voice frames (Opus audio)
- **text**: Text messages (extracted from payload)
- **aprs**: APRS data (extracted from payload)
- **rejected**: Message rejected (invalid signature or not recipient)

### Routing by Message Type

```python
def handle_status(msg):
    message_type = pmt.symbol_to_string(
        pmt.dict_ref(msg, pmt.intern("message_type"), pmt.PMT_NIL)
    )
    
    if message_type == "voice":
        # Route to audio output
        pass
    elif message_type == "text":
        # Route to text handler
        pass
    elif message_type == "aprs":
        # Route to APRS handler
        pass
```

## GRC Flowgraph Structure

To use in GNU Radio Companion:

1. **RF Input**: Use `blocks.file_source` or `uhd.usrp_source`
2. **Demodulator**: Use `analog.quadrature_demod_cf` for FSK
3. **Symbol Sync**: Use `digital.symbol_sync_xx`
4. **LDPC Decoder**: Use `fec.ldpc_decoder` block
5. **Superframe Parser**: Use Embedded Python block with `sleipnir_superframe_parser`
6. **Opus Decoder**: Use `gr_opus.opus_decoder` block
7. **Audio Output**: Connect to `blocks.audio_sink` or `blocks.wavfile_sink`
8. **Status Output**: Connect to `zmq_status_output` or custom handler
9. **ZMQ Output**: Use `zmq_status_output` block for remote consumers

## Configuration Parameters

### Required

- `local_callsign`: This station's callsign

### Optional

- `private_key_path`: Path to private key for decryption
- `require_signatures`: Require valid signatures (default: False)
- `public_key_store_path`: Path to public key store directory
- `auth_matrix_file`: Path to auth LDPC matrix
- `voice_matrix_file`: Path to voice LDPC matrix

## Example Flowgraph

See `examples/rx_sleipnir_complete.grc` for a complete example flowgraph.

## Testing

### Test Without Signatures

```python
rx_block = make_sleipnir_rx_hier(
    local_callsign="TEST",
    require_signatures=False
)
```

### Test With Signatures

```python
rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    require_signatures=True,
    public_key_store_path="/path/to/public_keys"
)
```

### Test Decryption

```python
rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    private_key_path="/path/to/private.pem"
)
```

## Troubleshooting

### Signature Verification Fails

- Check public key exists in key store
- Verify public key format (PEM)
- Check sender callsign extraction

### Decryption Fails

- Verify private key file exists
- Check private key format (PEM/DER)
- Verify local callsign is in recipient list

### No Audio Output

- Check status messages for rejection reasons
- Verify Opus decoder is connected
- Check frame parsing is working

### ZMQ Connection Fails

- Verify ZeroMQ is installed
- Check firewall settings
- Verify ZMQ address format

## Notes

1. **Superframe Desynchronization**: Parser handles frame sync recovery
2. **Key Management**: Public keys stored per callsign in key store
3. **Status Reporting**: All status messages include full metadata
4. **Error Handling**: Graceful handling of unsigned/plaintext messages
5. **ZMQ**: Status and audio published separately for flexibility

