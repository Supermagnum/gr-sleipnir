# gr-sleipnir Block Usage Guide

Complete reference for using gr-sleipnir TX and RX hierarchical blocks, including all parameters, inputs, outputs, and cryptographic operations.

## Table of Contents

- [TX Block (`sleipnir_tx_hier`)](#tx-block-sleipnir_tx_hier)
- [RX Block (`sleipnir_rx_hier`)](#rx-block-sleipnir_rx_hier)
- [Cryptographic Operations](#cryptographic-operations)
- [Legal and Regulatory Information](#legal-and-regulatory-information)
- [Message Port Reference](#message-port-reference)
- [Examples](#examples)

---

## TX Block (`sleipnir_tx_hier`)

### Block Overview

The `sleipnir_tx_hier` block provides a complete transmit chain for gr-sleipnir digital voice communication.

**Location**: `python/sleipnir_tx_hier.py`

**Import**:
```python
from python.sleipnir_tx_hier import make_sleipnir_tx_hier
```

### Block Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `callsign` | str | `"N0CALL"` | Source callsign (transmitter identifier) |
| `audio_samp_rate` | float | `8000.0` | Audio sample rate in Hz (must be 8000 for Opus) |
| `rf_samp_rate` | float | `48000.0` | RF sample rate in Hz (typically 48000) |
| `symbol_rate` | float | `4800.0` | Symbol rate in symbols/second |
| `fsk_deviation` | float | `2400.0` | FSK frequency deviation in Hz |
| `fsk_levels` | int | `4` | Number of FSK levels: `4` for 4FSK, `8` for 8FSK |
| `auth_matrix_file` | str | `"../ldpc_matrices/ldpc_auth_1536_512.alist"` | Path to authentication frame LDPC matrix file |
| `voice_matrix_file` | str | `"../ldpc_matrices/ldpc_voice_576_384.alist"` | Path to voice frame LDPC matrix file |
| `enable_signing` | bool | `False` | Enable ECDSA signing (see [Legal Information](#legal-and-regulatory-information)) |
| `enable_encryption` | bool | `False` | Enable encryption (see [Legal Information](#legal-and-regulatory-information)) |
| `private_key_path` | str | `None` | Path to private key file (PEM or DER format, BrainpoolP256r1) |
| `mac_key` | bytes | `None` | MAC key for encryption (32 bytes, optional if using `key_source` message port) |

### Stream Inputs

| Port | Type | Sample Rate | Description |
|------|------|-------------|-------------|
| **Port 0** | `float32` | 8000 Hz | Audio input samples (mono, 8 kHz) |

### Stream Outputs

| Port | Type | Sample Rate | Description |
|------|------|-------------|-------------|
| **Port 0** | `complex64` | RF sample rate (default 48000 Hz) | Complex baseband RF output |

### Message Port Inputs

| Port Name | Type | Description |
|-----------|------|-------------|
| **`ctrl`** | PMT dict | Control messages for configuration updates (see [Message Port Reference](#message-port-reference)) |
| **`key_source`** | PMT dict | Key source messages from `gr-linux-crypto` blocks (see [Key Management](#key-management)) |
| **`aprs_in`** | PMT pair `(meta, data)` | APRS packet input (see [APRS Input](#aprs-input)) |
| **`text_in`** | PMT pair `(meta, data)` | Text message input (see [Text Input](#text-input)) |

### Message Port Outputs

| Port Name | Type | Description |
|-----------|------|-------------|
| None | - | TX block has no message port outputs |

### Usage Example

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
    fsk_levels=4,  # 4FSK mode
    enable_signing=True,  # Enable ECDSA signing
    enable_encryption=False,  # Disable encryption
    private_key_path="/path/to/private_key.pem"
)

# Connect in flowgraph
tb = gr.top_block()
tb.connect(audio_source, tx_block)
tb.connect(tx_block, rf_sink)
tb.run()
```

---

## RX Block (`sleipnir_rx_hier`)

### Block Overview

The `sleipnir_rx_hier` block provides a complete receive chain for gr-sleipnir digital voice communication.

**Location**: `python/sleipnir_rx_hier.py`

**Import**:
```python
from python.sleipnir_rx_hier import make_sleipnir_rx_hier
```

### Block Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `local_callsign` | str | `"N0CALL"` | This station's callsign (for recipient checking) |
| `audio_samp_rate` | float | `8000.0` | Audio sample rate in Hz (must be 8000 for Opus) |
| `rf_samp_rate` | float | `48000.0` | RF sample rate in Hz (typically 48000) |
| `symbol_rate` | float | `4800.0` | Symbol rate in symbols/second |
| `fsk_deviation` | float | `2400.0` | FSK frequency deviation in Hz |
| `fsk_levels` | int | `4` | Number of FSK levels: `4` for 4FSK, `8` for 8FSK |
| `auth_matrix_file` | str | `"../ldpc_matrices/ldpc_auth_1536_512.alist"` | Path to authentication frame LDPC matrix file |
| `voice_matrix_file` | str | `"../ldpc_matrices/ldpc_voice_576_384.alist"` | Path to voice frame LDPC matrix file |
| `private_key_path` | str | `None` | Path to private key file for decryption (PEM or DER format, BrainpoolP256r1) |
| `require_signatures` | bool | `False` | Require valid signatures (reject unsigned messages if True) |
| `public_key_store_path` | str | `None` | Path to directory containing public keys for signature verification (format: `{callsign}.pem`) |

### Stream Inputs

| Port | Type | Sample Rate | Description |
|------|------|-------------|-------------|
| **Port 0** | `complex64` | RF sample rate (default 48000 Hz) | Complex baseband RF input |

### Stream Outputs

| Port | Type | Sample Rate | Description |
|------|------|-------------|-------------|
| **Port 0** | `float32` | 8000 Hz | Audio output samples (mono, 8 kHz) |

### Message Port Inputs

| Port Name | Type | Description |
|-----------|------|-------------|
| **`ctrl`** | PMT dict | Control messages for configuration updates (see [Message Port Reference](#message-port-reference)) |
| **`key_source`** | PMT dict | Key source messages from `gr-linux-crypto` blocks (see [Key Management](#key-management)) |

### Message Port Outputs

| Port Name | Type | Description |
|-----------|------|-------------|
| **`status`** | PMT dict | Status messages with signature/decryption status, frame counts, etc. (see [Status Output](#status-output)) |
| **`audio_pdu`** | PMT blob | Decoded audio frame PDUs (optional, for advanced processing) |
| **`aprs_out`** | PMT pair `(meta, data)` | Decoded APRS packets (see [APRS Output](#aprs-output)) |
| **`text_out`** | PMT pair `(meta, data)` | Decoded text messages (see [Text Output](#text-output)) |

### Usage Example

```python
from gnuradio import gr, blocks
from python.sleipnir_rx_hier import make_sleipnir_rx_hier

# Create RX block
rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    private_key_path="/path/to/private_key.pem",
    require_signatures=True,  # Require valid signatures
    public_key_store_path="/path/to/public_keys"
)

# Connect in flowgraph
tb = gr.top_block()
tb.connect(rf_source, rx_block)
tb.connect(rx_block, audio_sink)

# Handle status messages
def handle_status(msg):
    status_dict = pmt.to_python(msg)
    if status_dict.get('signature_valid'):
        print(f"Valid signature from {status_dict.get('sender')}")

rx_block.set_msg_handler("status", handle_status)

tb.run()
```

---

## Cryptographic Operations

### Overview

gr-sleipnir supports two cryptographic operations:

1. **ECDSA Signing/Verification** (BrainpoolP256r1) - For authentication and message integrity
2. **ChaCha20-Poly1305 Encryption/Decryption** - For message confidentiality

**Important**: See [Legal and Regulatory Information](#legal-and-regulatory-information) for legal requirements.

### ECDSA Signing (TX)

**Purpose**: Cryptographically sign transmissions to verify sender identity and message integrity.

**Legal Status**: **Legal** - Signing does not obscure content and is permitted in amateur radio.

**Requirements**:
- Private key file (BrainpoolP256r1, PEM or DER format)
- `enable_signing=True` in TX block
- `private_key_path` parameter or key via `key_source` message port

**Implementation**: Uses `gr-linux-crypto` ECDSA sign block (BrainpoolP256r1 curve).

**Reference**: See [gr-linux-crypto documentation](https://github.com/Supermagnum/gr-linux-crypto) for detailed ECDSA implementation.

**Usage**:
```python
tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_signing=True,
    private_key_path="/path/to/private_key.pem"
)
```

**Key Generation**:
```bash
# Generate BrainpoolP256r1 private key
openssl ecparam -genkey -name brainpoolP256r1 -out private_key.pem

# Extract public key
openssl ec -in private_key.pem -pubout -out public_key.pem
```

### ECDSA Verification (RX)

**Purpose**: Verify cryptographic signatures to authenticate sender and detect tampering.

**Legal Status**: **Legal** - Verification does not obscure content and is permitted in amateur radio.

**Requirements**:
- Public key store directory containing `{callsign}.pem` files
- `require_signatures=True` (optional, rejects unsigned messages if True)
- `public_key_store_path` parameter

**Implementation**: Uses `gr-linux-crypto` ECDSA verify block (BrainpoolP256r1 curve).

**Reference**: See [gr-linux-crypto documentation](https://github.com/Supermagnum/gr-linux-crypto) for detailed ECDSA implementation.

**Usage**:
```python
rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    require_signatures=True,  # Reject unsigned messages
    public_key_store_path="/path/to/public_keys"  # Directory with CALLSIGN.pem files
)
```

**Public Key Store Structure**:
```
/public_keys/
    ├── N0CALL.pem
    ├── N1ABC.pem
    └── W1XYZ.pem
```

### ChaCha20-Poly1305 Encryption (TX)

**Purpose**: Encrypt voice frames for confidentiality.

**Legal Status**: **Restricted** - Encryption is only legal where permitted by regulations or in permitted situations. **User is 100% responsible for legal compliance.**

**Requirements**:
- MAC key (32 bytes)
- `enable_encryption=True` in TX block
- `mac_key` parameter or key via `key_source` message port
- Recipient list (for multi-recipient encryption)

**Implementation**: Uses `gr-nacl` ChaCha20-Poly1305 encrypt block.

**Reference**: See [gr-nacl documentation](https://github.com/Supermagnum/gr-nacl) for detailed ChaCha20-Poly1305 implementation.

**Usage**:
```python
# Generate 32-byte MAC key
import secrets
mac_key = secrets.token_bytes(32)

tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_encryption=True,
    mac_key=mac_key
)

# Set recipients via ctrl message
import pmt
ctrl_msg = pmt.make_dict()
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("recipients"), pmt.intern("N1ABC,N2DEF"))
tx_block.message_port_pub("ctrl", ctrl_msg)
```

**Multi-Recipient Encryption**:
```python
# Encrypt for multiple recipients
ctrl_msg = pmt.make_dict()
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("recipients"), pmt.intern("N1ABC,N2DEF,N3GHI"))
tx_block.message_port_pub("ctrl", ctrl_msg)
```

### ChaCha20-Poly1305 Decryption (RX)

**Purpose**: Decrypt encrypted voice frames.

**Legal Status**: **Restricted** - Decryption is only legal where encryption is permitted. **User is 100% responsible for legal compliance.**

**Requirements**:
- MAC key (32 bytes, must match TX key)
- Private key for recipient checking (if using multi-recipient encryption)
- Key via `key_source` message port or `private_key_path` parameter

**Implementation**: Uses `gr-nacl` ChaCha20-Poly1305 decrypt block.

**Reference**: See [gr-nacl documentation](https://github.com/Supermagnum/gr-nacl) for detailed ChaCha20-Poly1305 implementation.

**Usage**:
```python
# Same MAC key as TX
mac_key = b"your-32-byte-key-here-123456789012"  # 32 bytes

rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    private_key_path="/path/to/private_key.pem"  # For recipient checking
)

# Send MAC key via ctrl message
import pmt
ctrl_msg = pmt.make_dict()
mac_key_pmt = pmt.init_u8vector(len(mac_key), list(mac_key))
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("mac_key"), mac_key_pmt)
rx_block.message_port_pub("ctrl", ctrl_msg)
```

### Key Management

#### Using gr-linux-crypto Key Sources

**Recommended**: Use `gr-linux-crypto` blocks for secure key management.

**TX Key Source**:
```python
from gnuradio import linux_crypto

# Use kernel keyring
keyring_source = linux_crypto.kernel_keyring_source(
    key_id="sleipnir_tx_key"
)

# Connect to TX block
tb.msg_connect(keyring_source, "message_out", tx_block, "key_source")
```

**RX Key Source**:
```python
from gnuradio import linux_crypto

# Use kernel keyring
keyring_source = linux_crypto.kernel_keyring_source(
    key_id="sleipnir_rx_key"
)

# Connect to RX block
tb.msg_connect(keyring_source, "message_out", rx_block, "key_source")
```

**Reference**: See [gr-linux-crypto documentation](https://github.com/Supermagnum/gr-linux-crypto) for:
- `kernel_keyring_source` block usage
- `nitrokey_interface` block usage
- Key storage and retrieval
- Key rotation procedures

#### File-Based Keys

**Private Keys**:
- Format: PEM or DER
- Curve: BrainpoolP256r1
- Location: Specified via `private_key_path` parameter

**Public Keys**:
- Format: PEM or DER
- Curve: BrainpoolP256r1
- Location: `{public_key_store_path}/{callsign}.pem`

**MAC Keys**:
- Format: 32 bytes (binary)
- Can be passed as `bytes` object or via message port

---

## Legal and Regulatory Information

### **IMPORTANT LEGAL NOTICE**

**User Responsibility**: The user is **100% responsible** for ensuring all cryptographic operations comply with applicable laws and regulations in their jurisdiction.

### ECDSA Signing and Verification

**Status**: **Legal and Permitted**

**Rationale**:
- Digital signatures do **not** obscure message content
- Signatures provide authentication and integrity verification
- Content remains readable by anyone
- Similar to DTMF authentication codes (but cryptographically secure)

**Use Cases**:
- Verify sender identity
- Prevent callsign spoofing
- Detect message tampering
- Replace error-prone DTMF authentication

**Regulatory Compliance**: Generally permitted in amateur radio worldwide.

### Encryption (ChaCha20-Poly1305)

**Status**: **Restricted - Legal Only Where Permitted**

**Rationale**:
- Encryption **does** obscure message content
- Content is not readable without the decryption key
- May be prohibited in amateur radio depending on jurisdiction

**Legal Requirements**:
- **User must verify** applicable regulations in their jurisdiction
- **User must ensure** encryption is permitted on the frequency band being used
- **User is 100% responsible** for legal compliance

**Permitted Situations** (examples, verify with local regulations):
- Experimental/research frequencies where encryption is explicitly permitted
- Private/restricted frequency bands where encryption is allowed
- Emergency communications where encryption is authorized
- Other situations where local regulations explicitly permit encryption

**Prohibited Situations**:
- Amateur radio frequencies where encryption is prohibited
- Public service bands where encryption is not authorized
- Any situation where local regulations prohibit encryption

**Compliance Checklist**:
- [ ] Verified encryption is permitted in your jurisdiction
- [ ] Verified encryption is permitted on the frequency band
- [ ] Verified encryption is permitted for your use case
- [ ] Understood that you are 100% responsible for legal compliance
- [ ] Have appropriate authorization if required

### References

- **gr-linux-crypto**: [Documentation](https://github.com/Supermagnum/gr-linux-crypto)
- **gr-nacl**: [Documentation](https://github.com/Supermagnum/gr-nacl)
- **ITU Radio Regulations**: Check applicable regulations for your jurisdiction
- **Local Amateur Radio Regulations**: Verify with your licensing authority

---

## Message Port Reference

### TX Block Message Ports

#### `ctrl` Message Port (Input)

PMT dictionary with optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `enable_signing` | bool | Enable/disable ECDSA signing |
| `enable_encryption` | bool | Enable/disable encryption |
| `recipients` | string | Comma-separated list of recipient callsigns (e.g., `"N1ABC,N2DEF"`) |
| `callsign` | string | Update source callsign |
| `private_key` | u8vector | Private key (PEM/DER bytes) |
| `mac_key` | u8vector | MAC key (32 bytes) |

**Example**:
```python
import pmt

ctrl_msg = pmt.make_dict()
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("enable_signing"), pmt.from_bool(True))
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("recipients"), pmt.intern("N1ABC,N2DEF"))

tx_block.message_port_pub("ctrl", ctrl_msg)
```

#### `key_source` Message Port (Input)

PMT dictionary with fields:

| Field | Type | Description |
|-------|------|-------------|
| `private_key` | u8vector | Private key (PEM/DER bytes) |
| `mac_key` | u8vector | MAC key (32 bytes) |
| `key_id` | symbol | Optional key identifier |

**Source**: Typically from `gr-linux-crypto` blocks (`kernel_keyring_source`, `nitrokey_interface`).

#### `aprs_in` Message Port (Input)

PMT pair `(meta, data)`:
- `meta`: PMT dictionary (optional metadata)
- `data`: PMT u8vector or blob containing APRS packet data (UTF-8 encoded)

**Example**:
```python
import pmt

aprs_data = b"TEST,59.9139,10.7522,100"  # callsign,lat,lon,alt
aprs_pmt = pmt.init_u8vector(len(aprs_data), list(aprs_data))
meta = pmt.make_dict()
tx_block.message_port_pub("aprs_in", pmt.cons(meta, aprs_pmt))
```

#### `text_in` Message Port (Input)

PMT pair `(meta, data)`:
- `meta`: PMT dictionary (optional metadata)
- `data`: PMT symbol (string), blob, or u8vector containing text message (UTF-8 encoded)

**Example**:
```python
import pmt

text_data = b"Hello from gr-sleipnir!"
text_pmt = pmt.init_u8vector(len(text_data), list(text_data))
meta = pmt.make_dict()
tx_block.message_port_pub("text_in", pmt.cons(meta, text_pmt))
```

### RX Block Message Ports

#### `ctrl` Message Port (Input)

PMT dictionary with optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `local_callsign` | string | Update local callsign |
| `require_signatures` | bool | Require valid signatures |
| `private_key` | u8vector | Private key for decryption (PEM/DER bytes) |
| `public_key` | u8vector | Public key for verification (PEM/DER bytes) |
| `mac_key` | u8vector | MAC key for decryption (32 bytes) |
| `key_id` | symbol | Optional key identifier |

**Example**:
```python
import pmt

ctrl_msg = pmt.make_dict()
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("require_signatures"), pmt.from_bool(True))
mac_key = b"your-32-byte-key-here-123456789012"
mac_key_pmt = pmt.init_u8vector(len(mac_key), list(mac_key))
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("mac_key"), mac_key_pmt)

rx_block.message_port_pub("ctrl", ctrl_msg)
```

#### `key_source` Message Port (Input)

PMT dictionary with fields:

| Field | Type | Description |
|-------|------|-------------|
| `private_key` | u8vector | Private key for decryption (PEM/DER bytes) |
| `public_key` | u8vector | Public key for verification (PEM/DER bytes) |
| `mac_key` | u8vector | MAC key for decryption (32 bytes) |
| `key_id` | symbol | Optional key identifier |

**Source**: Typically from `gr-linux-crypto` blocks (`kernel_keyring_source`, `nitrokey_interface`).

#### `status` Message Port (Output)

PMT dictionary with fields:

| Field | Type | Description |
|-------|------|-------------|
| `signature_valid` | bool | Whether signature is valid |
| `encrypted` | bool | Whether message was encrypted |
| `decrypted_successfully` | bool | Whether decryption succeeded |
| `sender` | string | Sender callsign |
| `recipients` | string | Recipient callsigns (comma-separated) |
| `frame_count` | int | Total frames received |
| `frame_error_count` | int | Number of frame errors |
| `superframe_count` | int | Number of superframes processed |
| `aprs_count` | int | Number of APRS packets received |
| `text_count` | int | Number of text messages received |

**Example Handler**:
```python
def handle_status(msg):
    status_dict = pmt.to_python(msg)
    print(f"Sender: {status_dict.get('sender')}")
    print(f"Signature valid: {status_dict.get('signature_valid')}")
    print(f"Decrypted: {status_dict.get('decrypted_successfully')}")

rx_block.set_msg_handler("status", handle_status)
```

#### `aprs_out` Message Port (Output)

PMT pair `(meta, data)`:
- `meta`: PMT dictionary with `sender`, `message_type` ("aprs"), `packet_count`
- `data`: PMT u8vector containing concatenated APRS packet data

**Example Handler**:
```python
def handle_aprs(msg):
    meta = pmt.car(msg)
    data = pmt.cdr(msg)
    sender = pmt.symbol_to_string(pmt.dict_ref(meta, pmt.intern("sender"), pmt.PMT_NIL))
    aprs_data = bytes(pmt.u8vector_elements(data))
    print(f"APRS from {sender}: {aprs_data.decode('utf-8')}")

rx_block.set_msg_handler("aprs_out", handle_aprs)
```

#### `text_out` Message Port (Output)

PMT pair `(meta, data)`:
- `meta`: PMT dictionary with `sender`, `message_type` ("text"), `message_count`
- `data`: PMT u8vector containing concatenated text message data

**Example Handler**:
```python
def handle_text(msg):
    meta = pmt.car(msg)
    data = pmt.cdr(msg)
    sender = pmt.symbol_to_string(pmt.dict_ref(meta, pmt.intern("sender"), pmt.PMT_NIL))
    text_data = bytes(pmt.u8vector_elements(data))
    print(f"Text from {sender}: {text_data.decode('utf-8')}")

rx_block.set_msg_handler("text_out", handle_text)
```

---

## Examples

### Basic TX (No Crypto)

```python
from gnuradio import gr, blocks
from python.sleipnir_tx_hier import make_sleipnir_tx_hier

tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    fsk_levels=4  # 4FSK mode
)
```

### TX with Signing Only

```python
tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_signing=True,
    private_key_path="/path/to/private_key.pem"
)
```

### TX with Encryption Only

```python
import secrets

mac_key = secrets.token_bytes(32)

tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_encryption=True,
    mac_key=mac_key
)

# Set recipients
import pmt
ctrl_msg = pmt.make_dict()
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("recipients"), pmt.intern("N1ABC"))
tx_block.message_port_pub("ctrl", ctrl_msg)
```

### TX with Both Signing and Encryption

```python
import secrets

mac_key = secrets.token_bytes(32)

tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_signing=True,
    enable_encryption=True,
    private_key_path="/path/to/private_key.pem",
    mac_key=mac_key
)

# Set recipients
import pmt
ctrl_msg = pmt.make_dict()
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("recipients"), pmt.intern("N1ABC,N2DEF"))
tx_block.message_port_pub("ctrl", ctrl_msg)
```

### Basic RX (No Crypto)

```python
from gnuradio import gr, blocks
from python.sleipnir_rx_hier import make_sleipnir_rx_hier

rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    fsk_levels=4  # 4FSK mode
)
```

### RX with Signature Verification

```python
rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    require_signatures=True,  # Reject unsigned messages
    public_key_store_path="/path/to/public_keys"
)

def handle_status(msg):
    status_dict = pmt.to_python(msg)
    if not status_dict.get('signature_valid'):
        print("WARNING: Invalid or missing signature!")

rx_block.set_msg_handler("status", handle_status)
```

### RX with Decryption

```python
mac_key = b"your-32-byte-key-here-123456789012"  # Must match TX key

rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    private_key_path="/path/to/private_key.pem"  # For recipient checking
)

# Send MAC key
import pmt
ctrl_msg = pmt.make_dict()
mac_key_pmt = pmt.init_u8vector(len(mac_key), list(mac_key))
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("mac_key"), mac_key_pmt)
rx_block.message_port_pub("ctrl", ctrl_msg)
```

### RX with Both Verification and Decryption

```python
mac_key = b"your-32-byte-key-here-123456789012"

rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    require_signatures=True,
    public_key_store_path="/path/to/public_keys",
    private_key_path="/path/to/private_key.pem"
)

# Send MAC key
import pmt
ctrl_msg = pmt.make_dict()
mac_key_pmt = pmt.init_u8vector(len(mac_key), list(mac_key))
ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("mac_key"), mac_key_pmt)
rx_block.message_port_pub("ctrl", ctrl_msg)

def handle_status(msg):
    status_dict = pmt.to_python(msg)
    print(f"Signature: {'Valid' if status_dict.get('signature_valid') else 'Invalid'}")
    print(f"Decrypted: {'Yes' if status_dict.get('decrypted_successfully') else 'No'}")

rx_block.set_msg_handler("status", handle_status)
```

### Using gr-linux-crypto Key Sources

```python
from gnuradio import linux_crypto

# TX with kernel keyring
keyring_tx = linux_crypto.kernel_keyring_source(key_id="sleipnir_tx_key")
tx_block = make_sleipnir_tx_hier(
    callsign="N0CALL",
    enable_signing=True,
    enable_encryption=True
)

tb.msg_connect(keyring_tx, "message_out", tx_block, "key_source")

# RX with kernel keyring
keyring_rx = linux_crypto.kernel_keyring_source(key_id="sleipnir_rx_key")
rx_block = make_sleipnir_rx_hier(
    local_callsign="N0CALL",
    require_signatures=True,
    public_key_store_path="/path/to/public_keys"
)

tb.msg_connect(keyring_rx, "message_out", rx_block, "key_source")
```

---

## Additional Resources

- **TX Module Quick Reference**: [python/README_TX_MODULE.md](../python/README_TX_MODULE.md)
- **RX Module Quick Reference**: [python/README_RX_MODULE.md](../python/README_RX_MODULE.md)
- **Crypto Integration Guide**: [docs/CRYPTO_INTEGRATION.md](CRYPTO_INTEGRATION.md)
- **Crypto Wiring Guide**: [docs/CRYPTO_WIRING.md](CRYPTO_WIRING.md)
- **gr-linux-crypto Documentation**: [https://github.com/Supermagnum/gr-linux-crypto](https://github.com/Supermagnum/gr-linux-crypto)
- **gr-nacl Documentation**: [https://github.com/Supermagnum/gr-nacl](https://github.com/Supermagnum/gr-nacl)

