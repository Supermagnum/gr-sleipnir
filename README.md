# gr-sleipnir

A GNU Radio-based digital voice mode designed for amateur radio narrowband FM (NFM) channel spacing, utilizing modern audio codecs for superior voice quality compared to traditional codec2 implementations.

## About the Name

Sleipnir is the eight-legged horse of Odin, the Allfather in Norse mythology. According to the Prose Edda, Sleipnir was the finest of all horses, capable of traveling between the worlds of the gods, giants, and the dead. The name reflects the project's dual nature:

- **Eight legs**: Representing the 8FSK modulation mode (and the 4FSK mode as half the capability)
- **Speed and reliability**: Sleipnir's legendary speed and ability to traverse difficult terrain mirrors the system's goal of providing fast, reliable digital voice communication
- **Connection between worlds**: Just as Sleipnir bridged the realms of Norse cosmology, this system bridges the gap between traditional ham radio and modern digital communication technology

The name embodies the project's ambition to be a superior mode of digital voice communication for amateur radio, carrying messages reliably across the airwaves.

## Overview

gr-sleipnir is an experimental digital voice communication system for ham radio that combines Frequency Shift Keying (4FSK and 8FSK) modulation with modern audio codec technology. The system is designed to fit within standard NFM channel spacing while providing significantly improved audio quality over older codec2-based systems. Two modes are supported: 4FSK for standard operation and 8FSK for enhanced quality.

## Key Features

- **Dual Modulation Modes**: 4FSK (9,600 bps) and 8FSK (14,400 bps) for different quality/performance trade-offs
- **Modern Audio Codec**: Uses Opus codec (via gr-opus module) for superior voice quality
- **Forward Error Correction**: LDPC coding (rate 3/4 for 4FSK, rate 2/3 for 8FSK) for robust communication
- **NFM Channel Spacing**: Designed to operate within standard narrowband FM channel allocations
- **Integrated Services**: Voice, text messaging, callsign metadata, and framing in a single protocol
- **PTT Control**: Push-to-talk control integration for radio operation
- **GNU Radio Integration**: Built on GNU Radio framework for flexibility and extensibility
- **Battery-Friendly Cryptography**: BrainpoolP256r1 + ChaCha20Poly1305 optimized for low-power devices

## Cryptography: BrainpoolP256r1 + ChaCha20Poly1305

The system uses a combination of BrainpoolP256r1 (from [gr-linux-crypto](https://github.com/Supermagnum/gr-linux-crypto)) and ChaCha20Poly1305 (from gr-nacl) for authentication and message integrity. This combination is specifically chosen for its battery-friendly characteristics.

### Why This Combination is Battery-Friendly

#### 1. ChaCha20Poly1305 (from gr-nacl)

- **Software-optimized**: Designed for efficient software implementation without requiring special hardware instructions
- **ARM-friendly**: Provides excellent performance on ARM processors (common in battery-powered devices)
- **No hardware dependency**: Unlike AES, which benefits from AES-NI instructions (Intel/AMD), ChaCha20 works efficiently in pure software
- **Lower power consumption**: Software implementations consume less power than hardware-accelerated instructions that require specialized CPU features
- **High throughput**: Even without hardware acceleration, ChaCha20 achieves high encryption speeds

#### 2. BrainpoolP256r1 (from gr-linux-crypto)

- **Lightweight ECC**: Smaller key sizes compared to RSA (256 bits vs. 2048+ bits for equivalent security)
- **Efficient key exchange**: ECDH operations are computationally efficient
- **Battery-conscious**: Fewer CPU cycles = less power consumption during key exchange operations

## Why Opus Over Codec2?

Codec2 is a low-bitrate speech codec designed in the early 2000s, optimized for very low bandwidth (typically 1200-3200 bps). While effective for its era, codec2 has limitations:

- **Limited Audio Quality**: Designed for intelligibility over quality, resulting in robotic-sounding audio
- **Aging Technology**: Based on older speech coding techniques
- **Fixed Bitrates**: Limited flexibility in bitrate selection
- **Made for HF,not VHF bands**

Opus, developed in the 2010s, represents a significant advancement:

- **Superior Quality**: Modern hybrid codec combining CELP and MDCT techniques
- **Adaptive Bitrate**: Supports bitrates from 6 kbps to 510 kbps with excellent quality at low rates
- **Low Latency**: Configurable frame sizes (2.5ms to 60ms) suitable for real-time communication
- **Robust Error Handling**: Better performance under adverse channel conditions
- **Wide Industry Adoption**: Used in modern VoIP, streaming, and communication systems

At comparable bitrates (e.g., 6-8 kbps), Opus provides noticeably better audio quality than codec2 while maintaining low latency suitable for ham radio applications.

## System Architecture

The system consists of two main components:

### 1. 4FSK NFM Transceiver (`som_4fsk_nfm_ptt.grc`)

The main transceiver flowgraph implementing:
- Audio input/output processing
- G.711 vocoder encoding/decoding (currently)
- 4FSK symbol mapping and modulation
- Frequency modulation for RF transmission
- Quadrature demodulation for reception
- PTT control via ZeroMQ messaging
- Baseband I/Q processing via ZeroMQ

### 2. gr-opus Module

A GNU Radio Out-of-Tree (OOT) module providing:
- Opus audio encoder block
- Opus audio decoder block
- Support for multiple sample rates (8kHz, 12kHz, 16kHz, 24kHz, 48kHz)
- Mono and stereo support
- Configurable bitrate and application profiles

## Technical Specifications

### Modulation Modes

The system supports two modulation modes optimized for different use cases:

#### 4FSK Mode (Standard)

- **Modulation**: 4-level Frequency Shift Keying
- **Symbol Rate**: 4800 symbols/second
- **Gross Capacity**: 9,600 bps
- **FSK Deviation**: 2400 Hz
- **RF Sample Rate**: 500 kHz
- **Audio Sample Rate**: 8 kHz
- **Bandwidth**: ~9-10 kHz
- **SNR Requirement**: Baseline

**Bitrate Budget Breakdown**:
- Opus voice (raw): 6,000 bps
- LDPC rate 3/4 coded: 8,000 bps
- Framing/sync: 800 bps
- Metadata/callsign: 400 bps
- Text messaging: 400 bps (burst mode)
- **Total**: 9,600 bps

**Characteristics**:
- Voice quality: Good (6 kbps Opus)
- FEC strength: Moderate (rate 3/4)
- Suitable for standard NFM channel spacing

#### 8FSK Mode (High Performance)

- **Modulation**: 8-level Frequency Shift Keying
- **Symbol Rate**: 4800 symbols/second
- **Gross Capacity**: 14,400 bps
- **Bandwidth**: ~11-12 kHz
- **SNR Requirement**: +3 dB vs 4FSK

**Bitrate Budget Breakdown**:
- Opus voice (raw): 8,000 bps
- LDPC rate 2/3 coded: 12,000 bps
- Framing/sync: 800 bps
- Callsign/meta: 600 bps
- Text messaging: 600 bps (burst mode)
- CRC/checksum: 200 bps
- Reserved: 200 bps
- **Total**: 14,400 bps

**Characteristics**:
- Voice quality: Excellent (8 kbps Opus)
- FEC strength: Strong (rate 2/3)
- Requires better SNR but provides superior audio quality

### General Specifications

- **Codec**: Opus (via gr-opus module)
- **Channel Spacing**: Compatible with standard NFM spacing (typically 12.5 kHz or 25 kHz)
- **PTT Control**: ZeroMQ message-based

## Requirements

### System Dependencies

- GNU Radio 3.8 or later
- libopus-dev (Opus codec development libraries)
- CMake 3.8 or later
- ZeroMQ libraries

### Python Dependencies

- numpy
- opuslib (Python bindings for Opus)

### Installation

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install gnuradio-dev libopus-dev cmake libzmq3-dev

# Install Python dependencies
pip3 install numpy opuslib --break-system-packages

# Build gr-opus module
cd gr-opus
mkdir build && cd build
cmake ..
make
sudo make install
sudo ldconfig
```

## Usage

### Running the Transceiver

Open the flowgraph in GNU Radio Companion:

```bash
gnuradio-companion som_4fsk_nfm_ptt.grc
```

Or run the generated Python script directly:

```bash
python3 som_4fsk_nfm_ptt.py
```

### Configuration

Key parameters can be adjusted in the flowgraph:
- `audio_samp_rate`: Audio sample rate (default: 8000 Hz)
- `fsk_deviation`: FSK deviation in Hz (default: 2400)
- `rf_samp_rate`: RF sample rate (default: 500 kHz)
- `audio_dev`: Audio device name

### PTT Control

PTT (Push-to-Talk) control is handled via ZeroMQ messages:
- Send "SOT" (Start of Transmission) to enable transmission
- Send "EOT" (End of Transmission) to disable transmission
- Messages are sent to `ipc:///tmp/ptt_msg`

Example PTT control:

```python
import zmq
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.connect("ipc:///tmp/ptt_msg")
socket.send_string("SOT")  # Key PTT
# ... transmit ...
socket.send_string("EOT")  # Release PTT
```

## Project Structure

```
gr-sleipnir/
├── README.md                 # This file
├── CMakeLists.txt           # Root CMake configuration
├── som_4fsk_nfm_ptt.grc     # Main transceiver flowgraph
└── gr-opus/                 # Opus codec GNU Radio module
    ├── python/              # Python blocks
    ├── grc/                 # GRC block definitions
    ├── tests/               # Unit tests
    └── examples/            # Example flowgraphs
```

## Testing

The gr-opus module includes comprehensive tests:

```bash
cd gr-opus
python3 -m unittest discover tests/ -p 'qa_*.py' -v
```

See `gr-opus/test-results.md` for detailed test results.

## Status

This is an experimental project. The system is functional but may require tuning for optimal performance in various operating conditions.

## Future Work

- Integration of Opus codec into the main transceiver flowgraph (replacing G.711)
- Bitrate optimization for NFM channel constraints
- Error correction coding
- Performance testing and optimization
- Documentation and usage examples

## License

GPLv3

## Contributing

Contributions are welcome. Please ensure all code follows the project's coding standards and includes appropriate tests.

## Legal and Appropriate Uses for Amateur Radio

### Digital Signatures (Primary Use Case)

- **Cryptographically sign transmissions** to verify sender identity
- **Prevent callsign spoofing** through cryptographic authentication
- **Replace error-prone DTMF authentication** with secure digital signatures
- **Legal**: Digital signatures do not obscure content and are generally permitted in amateur radio

### Message Integrity

- **Detect transmission errors** through cryptographic integrity checks
- **Verify message authenticity** to ensure messages haven't been tampered with
- **Non-obscuring authentication tags** that verify but don't hide content
- **Legal**: Integrity verification does not hide message content

### Key Management Infrastructure

- **Secure key storage** using Nitrokey hardware security modules and kernel keyring
- **Off-air key exchange** using ECDH (Elliptic Curve Diffie-Hellman)
- **Authentication key distribution** for establishing trust relationships
- **Legal**: Key management does not encrypt on-air content

### Important Note

**Signing and verifying sender identity is NOT encryption**. Digital signatures provide authentication and integrity verification without obscuring the message content, making them appropriate for amateur radio use where encryption is generally prohibited.

### Experimental and Research Uses

For experiments or research on frequencies where encryption is legally permitted:

- Encryption may be used in accordance with local regulations
- Users must verify applicable frequency bands and regulations
- This module provides the technical capability; users are responsible for legal compliance

## References

- [Opus Codec](https://opus-codec.org/)
- [GNU Radio](https://www.gnuradio.org/)
- [Codec2](https://www.rowetel.com/?page_id=452)
- [gr-linux-crypto](https://github.com/Supermagnum/gr-linux-crypto) - BrainpoolP256r1 and Linux crypto integration
