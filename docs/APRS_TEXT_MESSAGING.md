# APRS and Text Messaging Integration

This document describes the APRS and text messaging capabilities in gr-sleipnir, which allow simultaneous transmission of voice, APRS packets, and text messages within the same superframe structure.

## Overview

gr-sleipnir supports multiplexing of three data types within a single superframe:
- **Voice**: Opus-encoded audio (primary)
- **APRS**: Automatic Packet Reporting System packets (position, status, etc.)
- **Text**: Text messages for chat or data exchange

All three data types share the same frame structure (48 bytes payload) and are distinguished by a frame type identifier in the first byte of each frame.

## Frame Type Identification

Each frame in the superframe contains a frame type identifier:

| Frame Type | Value | Description |
|------------|-------|-------------|
| `FRAME_TYPE_VOICE` | `0x00` | Opus-encoded audio data |
| `FRAME_TYPE_APRS` | `0x01` | APRS packet data |
| `FRAME_TYPE_TEXT` | `0x02` | Text message data |
| `FRAME_TYPE_SYNC` | `0xFF` | Synchronization frame |

The frame type is stored in the first byte of the 48-byte payload, leaving 39 bytes for actual data (plus 8 bytes for MAC).

## Architecture

### Frame Structure

```
48-byte Frame Payload:
┌─────────┬──────────────┬──────────┐
│ Type    │ Data         │ MAC      │
│ (1 byte)│ (39 bytes)   │ (8 bytes)│
└─────────┴──────────────┴──────────┘
```

- **Type**: Frame type identifier (voice, APRS, or text)
- **Data**: Actual payload data (39 bytes max per frame)
- **MAC**: ChaCha20-Poly1305 MAC (8 bytes, truncated from 16)

### Superframe Multiplexing

A superframe consists of 25 frames (1 second total):
- **Frame 0**: Optional authentication frame (if signing enabled)
- **Frames 1-24**: Voice, APRS, or text frames

**Priority Order**: APRS > Text > Voice

When APRS or text messages are queued, they replace voice frames in the superframe. Remaining frames continue as voice frames.

## TX Side (Transmission)

### Message Ports

The TX hierarchical block (`sleipnir_tx_hier`) provides two message input ports:

1. **`aprs_in`**: APRS packet input
2. **`text_in`**: Text message input

### Sending APRS Packets

```python
from gnuradio import sleipnir
from gnuradio.gr import pmt

# Create TX block
tx = sleipnir.make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_signing=False,
    enable_encryption=False
)

# Create APRS packet (simplified format: callsign,lat,lon,alt)
aprs_data = b"TEST,59.9139,10.7522,100"
aprs_pmt = pmt.init_u8vector(len(aprs_data), list(aprs_data))
meta = pmt.make_dict()

# Send APRS packet
tx.message_port_pub(pmt.intern("aprs_in"), pmt.cons(meta, aprs_pmt))
```

**APRS Packet Format**:
- UTF-8 encoded string
- Format: `CALLSIGN,LATITUDE,LONGITUDE,ALTITUDE` (simplified)
- Can be extended to full APRS format
- Long packets are automatically split into multiple frames

### Sending Text Messages

```python
# Create text message
text_data = b"Hello from gr-sleipnir!"
text_pmt = pmt.init_u8vector(len(text_data), list(text_data))
meta = pmt.make_dict()

# Send text message
tx.message_port_pub(pmt.intern("text_in"), pmt.cons(meta, text_pmt))
```

**Text Message Format**:
- UTF-8 encoded string
- Can be sent as PMT symbol, blob, or u8vector
- Long messages are automatically split into multiple frames

### Simultaneous Transmission

Voice, APRS, and text can be transmitted simultaneously:

```python
# Voice continues on audio input stream
# APRS and text are sent via message ports

# Send APRS
aprs_data = b"TEST,59.9139,10.7522,100"
aprs_pmt = pmt.init_u8vector(len(aprs_data), list(aprs_data))
tx.message_port_pub(pmt.intern("aprs_in"), pmt.cons(pmt.make_dict(), aprs_pmt))

# Send text
text_data = b"Status update"
text_pmt = pmt.init_u8vector(len(text_data), list(text_data))
tx.message_port_pub(pmt.intern("text_in"), pmt.cons(pmt.make_dict(), text_pmt))

# Voice continues automatically on audio stream
```

## RX Side (Reception)

### Message Ports

The RX hierarchical block (`sleipnir_rx_hier`) provides two message output ports:

1. **`aprs_out`**: APRS packet output
2. **`text_out`**: Text message output

### Receiving APRS Packets

```python
from gnuradio import sleipnir
from gnuradio.gr import pmt

# Create RX block
rx = sleipnir.make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    require_signatures=False
)

def handle_aprs(msg):
    """Handle received APRS packet."""
    if not pmt.is_pair(msg):
        return
    
    meta = pmt.car(msg)
    data = pmt.cdr(msg)
    
    # Extract metadata
    sender = pmt.symbol_to_string(
        pmt.dict_ref(meta, pmt.intern("sender"), pmt.PMT_NIL)
    )
    packet_count = pmt.to_long(
        pmt.dict_ref(meta, pmt.intern("packet_count"), pmt.PMT_NIL)
    )
    
    # Extract APRS data
    aprs_data = bytes(pmt.u8vector_elements(data))
    
    # Parse APRS packet
    aprs_str = aprs_data.decode('utf-8').rstrip('\x00')
    print(f"APRS from {sender}: {aprs_str}")
    
    # Parse fields (simplified format)
    fields = aprs_str.split(',')
    if len(fields) >= 4:
        callsign = fields[0]
        latitude = float(fields[1])
        longitude = float(fields[2])
        altitude = int(fields[3])
        print(f"  Position: {latitude}, {longitude}, {altitude}m")

# Register handler
rx.set_msg_handler(pmt.intern("aprs_out"), handle_aprs)
```

### Receiving Text Messages

```python
def handle_text(msg):
    """Handle received text message."""
    if not pmt.is_pair(msg):
        return
    
    meta = pmt.car(msg)
    data = pmt.cdr(msg)
    
    # Extract metadata
    sender = pmt.symbol_to_string(
        pmt.dict_ref(meta, pmt.intern("sender"), pmt.PMT_NIL)
    )
    message_count = pmt.to_long(
        pmt.dict_ref(meta, pmt.intern("message_count"), pmt.PMT_NIL)
    )
    
    # Extract text data
    text_data = bytes(pmt.u8vector_elements(data))
    text_str = text_data.decode('utf-8').rstrip('\x00')
    
    print(f"Text from {sender}: {text_str}")

# Register handler
rx.set_msg_handler(pmt.intern("text_out"), handle_text)
```

## Data Separation and Validation

### Critical Requirements

1. **No Data Leakage**: APRS packets and text messages must NOT appear in audio output
2. **Frame Type Identification**: Frames must be correctly identified and routed
3. **Cross-Contamination Prevention**: Voice, APRS, and text must remain separate

### Implementation Guarantees

- **Frame Type Byte**: First byte of each frame identifies the data type
- **Separate Message Ports**: APRS and text are output on dedicated ports, not mixed with audio
- **Parser Validation**: RX parser checks frame type before routing to audio output
- **Zero Padding**: Non-voice frames are excluded from audio stream

### Validation Tests

The test suite (`tests/test_aprs_text_messaging.py`) verifies:

1. **Voice + APRS Simultaneous**: APRS doesn't corrupt voice frames
2. **Voice + Text Simultaneous**: Text doesn't impact voice quality
3. **APRS-Only Mode**: Pure APRS transmission works
4. **Text-Only Mode**: Pure text messaging works
5. **Mixed Mode Stress Test**: All three types simultaneously
6. **Data Leakage Validation**: APRS/text never appear in audio output

## Use Cases

### 1. Voice + APRS Position Reporting

Transmit voice while periodically sending position updates:

```python
import time

# Send position every 10 seconds
while True:
    # Send APRS position
    aprs_data = f"TEST,{lat:.6f},{lon:.6f},{alt}".encode('utf-8')
    aprs_pmt = pmt.init_u8vector(len(aprs_data), list(aprs_data))
    tx.message_port_pub(pmt.intern("aprs_in"), pmt.cons(pmt.make_dict(), aprs_pmt))
    
    # Voice continues on audio stream
    time.sleep(10)
```

### 2. Voice + Text Chat

Transmit voice while sending text messages:

```python
# Send text message during voice transmission
text_data = b"QSY to 145.500 MHz"
text_pmt = pmt.init_u8vector(len(text_data), list(text_data))
tx.message_port_pub(pmt.intern("text_in"), pmt.cons(pmt.make_dict(), text_pmt))
```

### 3. APRS-Only Beacon

Transmit APRS packets without voice:

```python
# No audio input needed
# Just send APRS packets
aprs_data = b"TEST,59.9139,10.7522,100"
aprs_pmt = pmt.init_u8vector(len(aprs_data), list(aprs_data))
tx.message_port_pub(pmt.intern("aprs_in"), pmt.cons(pmt.make_dict(), aprs_pmt))
```

### 4. Text-Only Data Exchange

Transmit text messages without voice:

```python
# No audio input needed
# Just send text messages
text_data = b"Data packet 12345"
text_pmt = pmt.init_u8vector(len(text_data), list(text_data))
tx.message_port_pub(pmt.intern("text_in"), pmt.cons(pmt.make_dict(), text_pmt))
```

## Performance Considerations

### Frame Capacity

- **Voice**: 40 bytes per frame (Opus-encoded audio)
- **APRS**: 39 bytes per frame (after type byte)
- **Text**: 39 bytes per frame (after type byte)

### Throughput

- **Superframe Rate**: 25 frames/second (1 superframe per second)
- **APRS Capacity**: Up to 24 APRS frames per superframe = 936 bytes/second
- **Text Capacity**: Up to 24 text frames per superframe = 936 bytes/second
- **Mixed Mode**: Capacity shared between voice, APRS, and text

### Latency

- **Frame Latency**: 40ms per frame
- **Superframe Latency**: 1 second per superframe
- **APRS/Text Latency**: Depends on queue position (typically < 1 second)

## Integration with GNU Radio Companion (GRC)

### TX Block Configuration

In GRC, the `sleipnir_tx_hier` block exposes:
- **aprs_in**: Message port (optional) - connect APRS source blocks
- **text_in**: Message port (optional) - connect text source blocks

### RX Block Configuration

In GRC, the `sleipnir_rx_hier` block exposes:
- **aprs_out**: Message port (optional) - connect APRS sink blocks
- **text_out**: Message port (optional) - connect text sink blocks

### Example GRC Flowgraph

```
[Audio Source] → [sleipnir_tx_hier]
                      ↑
[APRS Source] ────────┘ (aprs_in)
                      ↑
[Text Source] ────────┘ (text_in)

[sleipnir_rx_hier] → [Audio Sink]
         │
         ├─ (aprs_out) → [APRS Sink]
         └─ (text_out) → [Text Sink]
```

## Testing

Run the comprehensive test suite:

```bash
cd /home/haaken/github-projects/gr-sleipnir
python3 tests/test_aprs_text_messaging.py
```

The test suite verifies:
- Frame type identification
- Data separation
- No cross-contamination
- Simultaneous transmission
- All use cases

## Future Enhancements

Potential improvements:
- Full APRS protocol support (AX.25, digipeating, etc.)
- Text message acknowledgment
- Priority queuing for APRS/text
- Compression for text messages
- Multi-hop routing for APRS

## See Also

- [TX Module Documentation](python/README_TX_MODULE.md)
- [RX Module Documentation](python/README_RX_MODULE.md)
- [Test Suite](tests/test_aprs_text_messaging.py)

