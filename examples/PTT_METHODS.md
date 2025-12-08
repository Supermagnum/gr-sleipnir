# PTT (Push-To-Talk) Control Methods

This document describes the various PTT control methods available for gr-sleipnir.

## Overview

PTT (Push-To-Talk) control determines when the radio transmits. gr-sleipnir supports multiple PTT methods:

1. **GPIO PTT** - Hardware GPIO pin control (Raspberry Pi, etc.)
2. **Serial PTT** - Serial port control (USB adapters, etc.)
3. **VOX** - Voice Operated Exchange (automatic voice detection)
4. **Network PTT** - TCP/IP or UDP network control
5. **ZMQ PTT** - ZeroMQ message-based control (existing)

## GPIO PTT

Hardware PTT via GPIO pins, suitable for Raspberry Pi and similar devices.

### Features

- Direct hardware control
- Low latency
- Debouncing support
- Active high/low configurable

### Usage

```python
from python.ptt_gpio import make_ptt_gpio

ptt = make_ptt_gpio(
    gpio_pin=18,          # GPIO pin number (BCM)
    active_low=True,      # PTT active low (default)
    sample_rate=8000.0,   # Audio sample rate
    debounce_ms=50        # Debounce time
)
```

### Hardware Requirements

- Raspberry Pi GPIO (RPi.GPIO or libgpiod)
- GPIO pin connected to PTT input
- Pull-up/pull-down resistor as needed

### Configuration

- **gpio_pin**: GPIO pin number (BCM numbering)
- **active_low**: True if PTT is active when pin is LOW
- **debounce_ms**: Debounce time in milliseconds

### Integration

```python
from gnuradio import gr
from python.ptt_gpio import make_ptt_gpio
from python.sleipnir_tx_hier import make_sleipnir_tx_hier

tb = gr.top_block()

# Create PTT and TX blocks
ptt = make_ptt_gpio(gpio_pin=18)
tx = make_sleipnir_tx_hier(callsign="N0CALL")

# Connect audio
tb.connect(audio_source, ptt)
tb.connect(ptt, tx)

# Connect PTT state to TX control
ptt.message_port_register_out("ptt")
tx.message_port_register_hier_in("ptt")
# In GRC: Connect message ports

tb.run()
```

## Serial PTT

PTT control via serial port, suitable for USB serial adapters and serial-controlled radios.

### Features

- USB serial adapter support
- Configurable commands
- Command delay support
- Multiple radio compatibility

### Usage

```python
from python.ptt_serial import make_ptt_serial

ptt = make_ptt_serial(
    serial_port="/dev/ttyUSB0",
    baudrate=9600,
    ptt_command_on=b"PTT ON\r\n",
    ptt_command_off=b"PTT OFF\r\n",
    ptt_delay_ms=50
)
```

### Common Serial PTT Adapters

- **SignaLink USB**: Uses DTR/RTS pins
- **RigBlaster**: Serial commands
- **Custom adapters**: Configurable commands

### Configuration

- **serial_port**: Serial device path (e.g., "/dev/ttyUSB0")
- **baudrate**: Serial baud rate
- **ptt_command_on**: Bytes to send for PTT on
- **ptt_command_off**: Bytes to send for PTT off
- **ptt_delay_ms**: Delay after command (ms)

### Example Commands

```python
# SignaLink USB (DTR/RTS)
ptt = make_ptt_serial(
    serial_port="/dev/ttyUSB0",
    ptt_command_on=b"\x01",  # DTR high
    ptt_command_off=b"\x00"   # DTR low
)

# RigBlaster
ptt = make_ptt_serial(
    serial_port="/dev/ttyUSB0",
    ptt_command_on=b"TX\r\n",
    ptt_command_off=b"RX\r\n"
)
```

## VOX (Voice Operated Exchange)

Automatic PTT activation based on voice detection.

### Features

- Automatic transmission
- Configurable threshold
- Attack/release timing
- Hang time support

### Usage

```python
from python.ptt_vox import make_ptt_vox

ptt = make_ptt_vox(
    threshold_db=-30.0,   # Voice detection threshold
    attack_ms=50,          # PTT on delay
    release_ms=500,        # PTT off delay
    hang_time_ms=200       # Minimum PTT on time
)
```

### Configuration

- **threshold_db**: Voice detection threshold in dB
- **attack_ms**: Delay before PTT activates (ms)
- **release_ms**: Delay before PTT deactivates (ms)
- **hang_time_ms**: Minimum PTT on time (ms)

### Tuning

- **Lower threshold**: More sensitive (activates on quieter sounds)
- **Higher threshold**: Less sensitive (requires louder voice)
- **Longer release**: Prevents cutting off during pauses
- **Shorter attack**: Faster response to voice

### Use Cases

- Hands-free operation
- Repeater operation
- Continuous monitoring
- Automatic response systems

## Network PTT

PTT control via TCP/IP or UDP network.

### Features

- Remote control
- TCP or UDP protocol
- JSON or plain text commands
- Multiple client support (TCP)

### Usage

```python
from python.ptt_network import make_ptt_network

ptt = make_ptt_network(
    listen_address="0.0.0.0",  # Listen on all interfaces
    listen_port=5558,
    protocol="TCP"             # or "UDP"
)
```

### Network Commands

**JSON format**:
```json
{"ptt": true}
{"command": "PTT_ON"}
```

**Plain text format**:
```
PTT ON
TX ON
PTT OFF
TX OFF
```

### Remote Control Client

```python
import socket
import json

# TCP client
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("radio.local", 5558))

# Send PTT on command
command = json.dumps({"ptt": True})
sock.send(command.encode())

# Send PTT off command
command = json.dumps({"ptt": False})
sock.send(command.encode())

sock.close()
```

### Use Cases

- Remote station control
- Web interface integration
- Mobile app control
- Network-based automation

## ZMQ PTT

ZeroMQ message-based control (existing method).

### Usage

```python
from python.zmq_control_helper import SleipnirControlClient

client = SleipnirControlClient("tcp://localhost:5555")
client.send_control(...)  # Includes PTT control
```

See `examples/SLEIPNIR_TX_MODULE.md` for details.

## PTT Integration Helper

Use `ptt_control_integration.py` for easy integration:

```python
from python.ptt_control_integration import create_ptt_handler

# Create PTT block
ptt = create_ptt_handler(
    'gpio',
    gpio_pin=18,
    active_low=True
)

# Or serial
ptt = create_ptt_handler(
    'serial',
    serial_port="/dev/ttyUSB0",
    baudrate=9600
)

# Or VOX
ptt = create_ptt_handler(
    'vox',
    threshold_db=-30.0
)
```

## Comparison

| Method | Latency | Complexity | Use Case |
|--------|---------|------------|----------|
| GPIO | Very Low | Low | Local hardware control |
| Serial | Low | Medium | USB adapters, serial radios |
| VOX | Medium | Low | Hands-free operation |
| Network | Medium | Medium | Remote control |
| ZMQ | Low | Low | Message-based control |

## Choosing a PTT Method

- **GPIO**: Direct hardware control, Raspberry Pi, embedded systems
- **Serial**: USB serial adapters, serial-controlled radios
- **VOX**: Hands-free operation, automatic transmission
- **Network**: Remote control, web interfaces, mobile apps
- **ZMQ**: Message-based systems, existing ZMQ infrastructure

## Troubleshooting

### GPIO PTT Not Working

- Check GPIO pin number (BCM vs physical)
- Verify active_low setting matches hardware
- Check permissions (may need sudo or gpio group)
- Verify GPIO library installed (RPi.GPIO or libgpiod)

### Serial PTT Not Working

- Verify serial port exists: `ls -l /dev/ttyUSB*`
- Check permissions: `sudo usermod -a -G dialout $USER`
- Verify baud rate matches adapter
- Test with serial terminal: `minicom -D /dev/ttyUSB0`

### VOX Too Sensitive/Not Sensitive Enough

- Adjust threshold_db (lower = more sensitive)
- Increase attack_ms to reduce false triggers
- Increase release_ms to prevent cutting off

### Network PTT Connection Fails

- Check firewall settings
- Verify listen_address (0.0.0.0 for all interfaces)
- Test with telnet: `telnet radio.local 5558`
- Check protocol (TCP vs UDP)

## Examples

See `examples/` directory for complete flowgraph examples with each PTT method.

