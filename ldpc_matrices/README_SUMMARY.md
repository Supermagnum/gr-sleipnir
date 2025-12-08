# LDPC Matrices Summary

Quick reference summary. For detailed documentation, see [ldpc_matrices/README.md](README.md) and [ldpc_matrices/SUPERFRAME_LDPC.md](SUPERFRAME_LDPC.md).

## Available Matrices

| Matrix | Rate | Usage | Coded Bits | Info Bits |
|--------|------|-------|------------|-----------|
| `ldpc_auth_768_256.alist` | 1/3 | Frame 0 (auth) | 768 | 256 |
| `ldpc_voice_576_384.alist` | 2/3 | Frames 1-24 (voice) | 576 | 384 |
| `ldpc_rate34.alist` | 3/4 | 4FSK mode (legacy) | 800 | 600 |
| `ldpc_rate23.alist` | 2/3 | 8FSK mode (legacy) | 900 | 600 |

## Usage

For superframe implementation:
- **Frame 0**: `ldpc_auth_768_256.alist`
- **Frames 1-24**: `ldpc_voice_576_384.alist`

For detailed documentation, see [ldpc_matrices/README.md](README.md) and [ldpc_matrices/SUPERFRAME_LDPC.md](SUPERFRAME_LDPC.md).
