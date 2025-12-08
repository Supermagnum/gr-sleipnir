# gr-sleipnir TX Module Documentation

## Overview

The gr-sleipnir TX module provides a complete transmit chain for superframe-based digital voice communication with optional encryption and signing.

## Architecture

```
Audio Input (float32, 8kHz)
    ↓
Opus Encoder (gr-opus)
    ↓
Superframe Assembler (Python block)
    ├─ Frame 0: Authentication (ECDSA signature)
    └─ Frames 1-24: Voice frames (Opus + MAC + metadata)
    ↓
LDPC Encoder (fec.ldpc_encoder)
    ├─ Auth frame: ldpc_auth_768_256.alist (rate 1/3)
    └─ Voice frames: ldpc_voice_576_384.alist (rate 2/3)
    ↓
Symbol Mapping (digital.chunks_to_symbols)
    ├─ 4FSK: 2 bits → [-3, -1, 1, 3]
    └─ 8FSK: 3 bits → [-7, -5, -3, -1, 1, 3, 5, 7]
    ↓
Pulse Shaping (filter.root_raised_cosine)
    ↓
Frequency Modulator (analog.frequency_modulator_fc)
    ↓
RF Output (complex64, RF sample rate)
```

## Components

### 1. Python Blocks

Located in `python/`:

- **sleipnir_superframe_assembler.py**: Assembles superframes from Opus frames
- **sleipnir_tx_block.py**: Main TX block (simplified)
- **sleipnir_tx_hier.py**: Hierarchical block wrapper
- **zmq_control_helper.py**: ZMQ control client

### 2. Available GNU Radio Blocks

The module uses only available blocks:

- **gr-opus**: `gr_opus.opus_encoder` - Opus audio encoding
- **fec**: `fec.ldpc_encoder` - LDPC forward error correction
- **digital**: `digital.chunks_to_symbols_xx` - Symbol mapping
- **filter**: `filter.root_raised_cosine` - Pulse shaping
- **analog**: `analog.frequency_modulator_fc` - Frequency modulation
- **zeromq**: `zeromq.pull_msg_source` - ZMQ message input
- **pdu**: `pdu.tagged_stream_to_pdu` - PDU conversion

## Usage

### Basic Usage in Python

```python
from gnuradio import gr, blocks
from python.sleipnir_tx_hier import make_sleipnir_tx_hier

# Create TX block
tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    audio_samp_rate=8000.0,
    rf_samp_rate=48000.0,
    symbol_rate=4800.0,
    fsk_deviation=2400.0,
    fsk_levels=4,  # 4FSK
    enable_signing=True,
    private_key_path="/path/to/key.pem"
)

# Connect to flowgraph
tb = gr.top_block()
tb.connect(audio_source, tx_block)
tb.connect(tx_block, rf_sink)
tb.run()
```

### Control via Message Port

```python
import pmt
from python.zmq_control_helper import create_control_pmt

# Create control message
ctrl_msg = create_control_pmt(
    enable_signing=True,
    enable_encryption=False,
    key_source="/path/to/key.pem",
    recipient="N1ABC",
    from_callsign="N0CALL",
    to_callsign="N1ABC",
    message_type="voice"
)

# Send to block
tx_block.message_port_pub(pmt.intern("ctrl"), ctrl_msg)
```

### ZMQ Remote Control

```python
from python.zmq_control_helper import SleipnirControlClient

# Create ZMQ client
client = SleipnirControlClient("tcp://localhost:5555")

# Send control message
client.send_control(
    enable_signing=True,
    key_source="/path/to/key.pem",
    recipient="N1ABC,N2DEF",  # Multiple recipients
    from_callsign="N0CALL",
    message_type="voice"
)

client.close()
```

## Control Message Format

Control messages are PMT dictionaries with the following fields:

```python
{
    'enable_signing': bool,        # Enable ECDSA signing
    'enable_encryption': bool,      # Enable encryption
    'key_source': str,              # Path to private key file
    'recipient': str,               # Recipient(s), comma-separated
    'message_type': str,            # 'voice', 'text', etc.
    'payload': bytes,               # Optional payload
    'from_callsign': str,           # Source callsign
    'to_callsign': str,             # Destination callsign
    'mac_key': bytes,               # MAC key (32 bytes)
}
```

## GRC Flowgraph Structure

To use in GNU Radio Companion:

1. **Audio Input**: Use `blocks.audio_source` or `blocks.wavfile_source`
2. **Opus Encoder**: Use `gr_opus.opus_encoder` block
3. **Superframe Assembler**: Use Embedded Python block with `sleipnir_superframe_assembler`
4. **LDPC Encoder**: Use `fec.ldpc_encoder` block
5. **Symbol Mapping**: Use `digital.chunks_to_symbols_xx` block
6. **Pulse Shaping**: Use `filter.root_raised_cosine` block
7. **Frequency Modulator**: Use `analog.frequency_modulator_fc` block
8. **RF Output**: Connect to `blocks.audio_sink` or `uhd.usrp_sink`

### ZMQ Control Input

Add ZMQ message source for remote control:

```
zeromq.pull_msg_source (ZMQ address: tcp://*:5555)
    ↓
pdu.pdu_lambda (convert JSON to PMT dict)
    ↓
Message port connection to superframe assembler
```

## Frame Structure

### Voice Frame Payload (48 bytes)

```
Bytes 0-39:   Opus voice data (40 bytes)
Bytes 40-55:  ChaCha20-Poly1305 MAC (16 bytes)
Bytes 56-60:  Callsign (5 bytes, ASCII)
Byte 61:      Frame counter (1 byte, 1-24)
Bytes 62-64:  Reserved (3 bytes)
```

### Authentication Frame Payload (32 bytes)

```
Bytes 0-31:   ECDSA signature (32 bytes, BrainpoolP256r1)
```

## Encryption and Signing

### Signing (ECDSA)

- Uses BrainpoolP256r1 curve
- Signature generated from hash of superframe data
- Stored in Frame 0 (32 bytes)
- Protected by LDPC rate 1/3 (256 → 768 bits)

### MAC (ChaCha20-Poly1305)

- Computed for each voice frame
- Covers: Opus data + callsign + frame counter
- 16-byte authentication tag
- Uses cryptography library (available)

### Key Management

- Private keys: PEM or DER format files
- MAC keys: 32-byte shared secrets
- Key exchange: Off-air (not implemented in this module)

## Example Flowgraph

See `examples/tx_sleipnir_complete.grc` for a complete example flowgraph.

## Testing

Test without encryption/signing:

```python
tx_block = make_sleipnir_tx_hier(
    callsign="TEST",
    enable_signing=False,
    enable_encryption=False
)
```

Test with signing:

```python
tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_signing=True,
    private_key_path="keys/private.pem"
)
```

## Notes

1. **Superframe Timing**: 25 frames per second (40ms per frame)
2. **LDPC Matrices**: Must exist in `ldpc_matrices/` directory
3. **Key Files**: Private keys must be in PEM or DER format
4. **ZMQ**: Requires ZeroMQ library and Python zmq bindings
5. **Crypto**: Uses cryptography library (available)

## Troubleshooting

### LDPC Matrix Not Found

- Verify matrix files exist in `ldpc_matrices/`
- Check file paths in block parameters

### Key Loading Fails

- Verify key file format (PEM or DER)
- Check file permissions
- Ensure key is EC private key (BrainpoolP256r1)

### ZMQ Connection Fails

- Verify ZeroMQ is installed
- Check ZMQ address format
- Ensure firewall allows connections

### Superframe Assembly Errors

- Verify Opus encoder produces 40-byte frames
- Check frame counter is 1-24
- Ensure callsign is 5 bytes or less

