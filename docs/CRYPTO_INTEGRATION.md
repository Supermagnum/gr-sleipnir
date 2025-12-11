# Crypto Integration Guide

This document describes how gr-linux-crypto and gr-nacl blocks are integrated into the gr-sleipnir TX/RX signal flow.

## Overview

gr-sleipnir uses cryptographic blocks from:
- **gr-linux-crypto**: ECDSA signing and verification (BrainpoolP256r1)
- **gr-nacl**: ChaCha20-Poly1305 encryption and MAC

These blocks are integrated into the PDU-based signal flow using wrapper blocks that provide a consistent interface.

## Architecture

### TX Signal Flow (with Crypto)

```
Audio Input (float32)
    ↓
Opus Encoder (gr-opus)
    ↓
[PDU: Opus frames]
    ↓
Superframe Assembler
    ├─ Frame 0: ECDSA Sign Block (gr-linux-crypto) ──┐
    └─ Frames 1-24: ChaCha20-Poly1305 Encrypt Block ─┤
        (gr-nacl)                                     │
    ↓                                                  │
[PDU: Encrypted/Signed frames]                        │
    ↓                                                  │
LDPC Encoder                                          │
    ├─ Frame 0: Auth matrix (rate 1/3)                │
    └─ Frames 1-24: Voice matrix (rate 2/3)          │
    ↓                                                  │
4FSK/8FSK Modulator                                   │
    ↓                                                  │
RF Output (complex64)                                 │
                                                       │
Superframe Data ──────────────────────────────────────┘
(used for Frame 0 signature)
```

### RX Signal Flow (with Crypto)

```
RF Input (complex64)
    ↓
4FSK/8FSK Demodulator
    ↓
LDPC Decoder
    ├─ Frame 0: Auth matrix (rate 1/3)
    └─ Frames 1-24: Voice matrix (rate 2/3)
    ↓
[PDU: Decoded frames]
    ↓
Superframe Parser
    ├─ Frame 0: ECDSA Verify Block (gr-linux-crypto)
    └─ Frames 1-24: ChaCha20-Poly1305 Decrypt Block (gr-nacl)
    ↓
[PDU: Decrypted/Verified frames]
    ↓
Opus Decoder (gr-opus)
    ↓
Audio Output (float32)
```

## Integration Blocks

### ECDSA Sign Block (`ecdsa_sign_block`)

**Location**: `python/crypto_integration.py`

**Purpose**: Sign superframe data using ECDSA (BrainpoolP256r1)

**Input**: PDU with data to sign (blob)
**Output**: PDU with signature (blob, 32 bytes)

**Parameters**:
- `private_key_path`: Path to private key file
- `curve_name`: ECC curve name (default: "brainpoolP256r1")

**Usage in TX**:
```python
from python.crypto_integration import make_ecdsa_sign_block

# Create sign block
sign_block = make_ecdsa_sign_block(
    private_key_path="/path/to/private_key.pem",
    curve_name="brainpoolP256r1"
)

# Connect: superframe_data → sign_block → frame_0_payload
```

### ECDSA Verify Block (`ecdsa_verify_block`)

**Purpose**: Verify ECDSA signature

**Input**: PDU with (data, signature) pair
**Output**: PDU with verification result in metadata

**Parameters**:
- `public_key_store_path`: Path to directory containing public keys

**Usage in RX**:
```python
from python.crypto_integration import make_ecdsa_verify_block

# Create verify block
verify_block = make_ecdsa_verify_block(
    public_key_store_path="/path/to/public_keys/"
)

# Connect: frame_0_payload → verify_block → verified_data
```

### ChaCha20-Poly1305 Encrypt Block (`chacha20poly1305_encrypt_block`)

**Purpose**: Encrypt and compute MAC for voice frames

**Input**: PDU with plaintext data (blob)
**Output**: PDU with (ciphertext, mac) pair

**Parameters**:
- `key`: 32-byte encryption key
- `nonce`: 12-byte nonce (optional, defaults to zeros)

**Usage in TX**:
```python
from python.crypto_integration import make_chacha20poly1305_encrypt_block

# Create encrypt block
encrypt_block = make_chacha20poly1305_encrypt_block(
    key=mac_key,  # 32 bytes
    nonce=None  # Use default zeros
)

# Connect: opus_frame → encrypt_block → encrypted_frame_with_mac
```

### ChaCha20-Poly1305 Decrypt Block (`chacha20poly1305_decrypt_block`)

**Purpose**: Decrypt and verify MAC for voice frames

**Input**: PDU with (ciphertext, mac) pair
**Output**: PDU with plaintext data (if MAC valid)

**Parameters**:
- `key`: 32-byte decryption key
- `nonce`: 12-byte nonce (optional, defaults to zeros)

**Usage in RX**:
```python
from python.crypto_integration import make_chacha20poly1305_decrypt_block

# Create decrypt block
decrypt_block = make_chacha20poly1305_decrypt_block(
    key=mac_key,  # 32 bytes
    nonce=None  # Use default zeros
)

# Connect: encrypted_frame_with_mac → decrypt_block → opus_frame
```

## Integration into Hierarchical Blocks

### TX Hierarchical Block

The `sleipnir_tx_hier` block integrates crypto blocks as follows:

1. **Superframe Assembler** receives Opus frames
2. **ECDSA Sign Block** signs superframe data (if signing enabled)
3. **ChaCha20-Poly1305 Encrypt Block** encrypts voice frames (if encryption enabled)
4. **LDPC Encoder** encodes frames
5. **Modulator** modulates to RF

**Message Ports**:
- `audio_in`: Audio input (stream)
- `ctrl`: Control messages (PMT dict) - for configuration updates
- `key_source`: Key source messages (PMT dict) - receives keys from `gr-linux-crypto` blocks
- `rf_out`: RF output (stream)

**Key Loading Flow**:
1. `kernel_keyring_source` or `nitrokey_interface` block outputs keys via message port
2. Keys received on `key_source` message port
3. Keys forwarded to internal blocks via `ctrl` message port
4. Internal blocks (superframe_assembler) apply keys

### RX Hierarchical Block

The `sleipnir_rx_hier` block integrates crypto blocks as follows:

1. **Demodulator** receives RF input
2. **LDPC Decoder** decodes frames
3. **Superframe Parser** extracts frames
4. **ECDSA Verify Block** verifies signature (if present)
5. **ChaCha20-Poly1305 Decrypt Block** decrypts voice frames (if encrypted)
6. **Opus Decoder** decodes audio

**Message Ports**:
- `rf_in`: RF input (stream)
- `ctrl`: Control messages (PMT dict) - for configuration updates
- `key_source`: Key source messages (PMT dict) - receives keys from `gr-linux-crypto` blocks
- `audio_out`: Audio output (stream)
- `status`: Status messages (PMT dict) - signature/decryption status
- `audio_pdu`: Audio PDUs (PMT blob) - decoded audio frames

**Key Loading Flow**:
1. `kernel_keyring_source` or `nitrokey_interface` block outputs keys via message port
2. Keys received on `key_source` message port
3. Keys forwarded to internal blocks via `ctrl` message port
4. Internal blocks (superframe_parser) apply keys for verification/decryption

## Fallback Behavior

If gr-linux-crypto or gr-nacl blocks are not available, the integration blocks fall back to Python implementations using the `cryptography` library:

- **ECDSA**: Uses `cryptography.hazmat.primitives.asymmetric.ec`
- **ChaCha20-Poly1305**: Uses `cryptography.hazmat.primitives.ciphers.aead.ChaCha20Poly1305`

This ensures the system continues to function even without the GNU Radio crypto modules, though performance may be reduced.

## Key Management

### Key Sources

Keys can be loaded from multiple sources:

1. **File-based keys** (traditional):
   - Private keys: PEM/DER files specified via `private_key_path` parameter
   - Public keys: Directory structure with `{callsign}.pem` files

2. **Dynamic key loading via message ports** (recommended):
   - `key_source` message port: Receives keys from `gr-linux-crypto` blocks
   - Keys are forwarded to internal blocks via `ctrl` message port
   - Supports `kernel_keyring_source` and `nitrokey_interface` blocks

### Private Keys

**File-based**:
```
/path/to/private_key.pem
```
Format: ECDSA private key, BrainpoolP256r1 curve

**Dynamic loading**:
- Connect `kernel_keyring_source.message_out` → `sleipnir_tx_hier.key_source`
- Or connect `nitrokey_interface.message_out` → `sleipnir_tx_hier.key_source`
- Keys are provided as PMT dict with `private_key` field (u8vector of PEM/DER bytes)

### Public Keys

**File-based**:
```
/public_key_store/
    ├── CALL1.pem
    ├── CALL2.pem
    └── CALL3.pem
```
Each file contains the public key for the corresponding callsign.

**Dynamic loading**:
- Connect `kernel_keyring_source.message_out` → `sleipnir_rx_hier.key_source`
- Keys are provided as PMT dict with `public_key` field (u8vector of PEM/DER bytes)
- Optional `key_id` field for key identification

### MAC Keys (Symmetric Encryption)

**Pre-shared keys**:
- Can be passed as `mac_key` parameter (32 bytes)
- Or sent via `key_source` message port as PMT dict with `mac_key` field (u8vector, 32 bytes)
- Keys are forwarded to internal blocks via `ctrl` message port
- Supports key rotation mid-transmission

**Message Format**:
```python
{
    "mac_key": <u8vector of 32 bytes>,
    "private_key": <u8vector of PEM/DER bytes>,  # Optional
    "public_key": <u8vector of PEM/DER bytes>,   # Optional (RX only)
    "key_id": <symbol string>                     # Optional identifier
}
```

## Performance Considerations

### Hardware Acceleration

- **gr-linux-crypto**: Uses Linux kernel crypto API, may benefit from hardware acceleration
- **gr-nacl**: Pure software implementation, optimized for ARM processors

### Latency

- **ECDSA Signing**: ~5-10ms (software), ~1-2ms (hardware accelerated)
- **ECDSA Verification**: ~5-10ms (software), ~1-2ms (hardware accelerated)
- **ChaCha20-Poly1305**: ~0.1-0.5ms per frame (software)

### Throughput

- **ECDSA**: Limited by key operations (~100-200 ops/sec)
- **ChaCha20-Poly1305**: High throughput (~100+ MB/s on modern CPUs)

## Testing

To test crypto integration:

1. Generate test keys:
```bash
openssl ecparam -genkey -name brainpoolP256r1 -out private_key.pem
openssl ec -in private_key.pem -pubout -out public_key.pem
```

2. Run TX with signing enabled:
```python
tx_block = make_sleipnir_tx_hier(
    callsign="TEST",
    enable_signing=True,
    private_key_path="private_key.pem"
)
```

3. Run RX with verification enabled:
```python
rx_block = make_sleipnir_rx_hier(
    local_callsign="TEST",
    require_signatures=True,
    public_key_store_path="./public_keys/"
)
```

## Troubleshooting

### "gr-linux-crypto not available"

Install gr-linux-crypto:
```bash
git clone https://github.com/Supermagnum/gr-linux-crypto.git
cd gr-linux-crypto
mkdir build && cd build
cmake ..
make
sudo make install
sudo ldconfig
```

### "gr-nacl not available"

Install gr-nacl:
```bash
git clone https://github.com/Supermagnum/gr-nacl.git
cd gr-nacl
mkdir build && cd build
cmake ..
make
sudo make install
sudo ldconfig
```

### "Could not load private key"

Ensure:
- Key file exists and is readable
- Key is in PEM or DER format
- Key uses BrainpoolP256r1 curve

### "No public key found for CALLSIGN"

Ensure:
- Public key file exists: `{public_key_store_path}/{CALLSIGN}.pem`
- File is readable
- Key is in PEM or DER format

