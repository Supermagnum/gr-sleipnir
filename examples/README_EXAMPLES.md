# gr-sleipnir Example Flowgraphs

This directory contains example GNU Radio Companion (GRC) flowgraphs demonstrating various usage scenarios for gr-sleipnir.

## Basic Examples

### sleipnir_tx_basic.grc
Basic transmitter example with audio file input.

**Features:**
- Audio file input (WAV format)
- Basic TX chain using `sleipnir_tx_hier`
- IQ file output
- No encryption or signing

**Usage:**
1. Place a WAV file named `input.wav` in the examples directory
2. Open `sleipnir_tx_basic.grc` in GNU Radio Companion
3. Run the flowgraph
4. Output will be saved to `tx_output.iq`

### sleipnir_rx_basic.grc
Basic receiver example with IQ file input.

**Features:**
- IQ file input
- Basic RX chain using `sleipnir_rx_hier`
- Audio file output (WAV format)
- No signature verification

**Usage:**
1. Generate an IQ file using `sleipnir_tx_basic.grc`
2. Rename it to `rx_input.iq`
3. Open `sleipnir_rx_basic.grc` in GNU Radio Companion
4. Run the flowgraph
5. Decoded audio will be saved to `output.wav`

## Cryptographic Examples

### sleipnir_tx_encrypted.grc
Transmitter with encryption and signing enabled.

**Features:**
- ECDSA signing (BrainpoolP256r1)
- ChaCha20-Poly1305 encryption
- Private key file support
- Recipient addressing

**Requirements:**
- Private key file at `keys/private.pem`
- gr-linux-crypto module installed (for ECDSA)
- gr-nacl module installed (for ChaCha20-Poly1305)

**Usage:**
1. Generate a private key:
   ```bash
   openssl ecparam -genkey -name brainpoolP256r1 -out keys/private.pem
   ```
2. Set recipient callsign in the `recipient` variable
3. Run the flowgraph

### sleipnir_rx_verified.grc
Receiver with signature verification and decryption.

**Features:**
- ECDSA signature verification
- Message decryption
- Public key store support
- Status reporting

**Requirements:**
- Private key file at `keys/private.pem` (for decryption)
- Public key store directory at `keys/public_keys/`
- Public keys named as `{callsign}.pem` (e.g., `N0CALL.pem`)

**Usage:**
1. Extract public key from sender's private key:
   ```bash
   openssl ec -in keys/private.pem -pubout -out keys/public_keys/N0CALL.pem
   ```
2. Set `local_callsign` to match your station
3. Set `require_signatures` to `True` to reject unsigned messages
4. Run the flowgraph

## PTT Control Examples

### sleipnir_tx_ptt.grc
Transmitter with GPIO PTT control.

**Features:**
- GPIO pin control for PTT
- Hardware PTT integration
- Suitable for Raspberry Pi and similar devices

**Requirements:**
- GPIO access (RPi.GPIO or libgpiod)
- Hardware connected to specified GPIO pin

**Usage:**
1. Set `gpio_pin` variable to your PTT GPIO pin number
2. Set `active_high` based on your hardware (True for active high, False for active low)
3. Connect PTT hardware to the specified GPIO pin
4. Run the flowgraph

**Note:** For other PTT methods (Serial, VOX, Network), see the PTT_METHODS.md documentation.

## ZMQ Integration Examples

### sleipnir_rx_zmq.grc
Receiver with ZMQ status and audio output.

**Features:**
- ZMQ PUB socket for status messages (JSON format)
- ZMQ PUB socket for audio PDUs
- Remote monitoring and audio streaming
- Separate addresses for status and audio

**Usage:**
1. Set `status_address` (default: `tcp://*:5556`)
2. Set `audio_address` (default: `tcp://*:5557`)
3. Run the flowgraph
4. Connect ZMQ subscribers to receive status and audio

**ZMQ Subscriber Example:**
```python
import zmq
import json

# Status subscriber
context = zmq.Context()
status_socket = context.socket(zmq.SUB)
status_socket.connect("tcp://localhost:5556")
status_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# Audio subscriber
audio_socket = context.socket(zmq.SUB)
audio_socket.connect("tcp://localhost:5557")
audio_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# Receive status
status_json = status_socket.recv_string()
status = json.loads(status_json)
print(f"Sender: {status.get('sender')}")
print(f"Signature valid: {status.get('signature_valid')}")

# Receive audio
metadata_json = audio_socket.recv_string()
audio_data = audio_socket.recv()
```

## Legacy Examples

The following examples are legacy flowgraphs that demonstrate the underlying components:

- `tx_4fsk_opus.grc` - 4FSK transmitter with Opus and LDPC (legacy)
- `rx_4fsk_opus.grc` - 4FSK receiver with Opus and LDPC (legacy)
- `tx_8fsk_opus.grc` - 8FSK transmitter (legacy)
- `rx_8fsk_opus.grc` - 8FSK receiver (legacy)

These use the basic GNU Radio blocks directly and do not use the sleipnir hierarchical blocks.

## Configuration

All examples use variables that can be adjusted:

- `audio_samp_rate`: Audio sample rate (default: 8000 Hz)
- `rf_samp_rate`: RF sample rate (default: 48000 Hz)
- `callsign`: Source callsign
- `local_callsign`: Local station callsign (RX only)
- `input_file`: Input file path
- `output_file`: Output file path

## Troubleshooting

**Issue: Module not found**
- Ensure gr-sleipnir is installed: `sudo make -C build install`
- Check Python path includes gr-sleipnir modules

**Issue: Key file not found**
- Verify key file paths are correct
- Check file permissions

**Issue: ZMQ connection refused**
- Verify ZMQ addresses are correct
- Check firewall settings
- Ensure ZMQ subscribers are running

**Issue: GPIO access denied**
- Add user to `gpio` group: `sudo usermod -a -G gpio $USER`
- Use `sudo` if necessary (not recommended)

For more information, see the main [README.md](../README.md) and module documentation.

