# Superframe LDPC Matrix Specifications

This document describes the custom LDPC matrices used in the gr-sleipnir superframe structure.

## Superframe Structure

- **Superframe**: 25 frames (1 second total)
- **Frame 0**: Authentication frame (with signature)
- **Frames 1-24**: Voice frames

## Code 1: Authentication Frame - LDPC (768, 256) Rate 1/3

### Purpose
Protect BrainpoolP256r1 signature in frame 0. The signature MUST be received correctly - a single bit error results in an invalid signature.

### Specifications
- **File**: `ldpc_auth_768_256.alist`
- **Block length**: 768 bits
- **Information bits**: 256 bits
- **Parity bits**: 512 bits
- **Code rate**: 1/3 (256/768)
- **Column weights**: 3-6 (variable, irregular)
- **Row weights**: ~10-13 (variable, irregular)

### Frame 0 Payload Structure
```
Uncoded payload:           256 bits
- Signature:               512 bits (actually 256 bits + padding/encoding)
LDPC encoding:             768 bits coded (rate 1/3)
Total:                     768 bits
```

### Performance Expectations
- Can correct ~30% bit errors
- BER 10^-5 at SNR ~2 dB
- Ensures signature integrity

## Code 2: Voice Frame - LDPC (576, 384) Rate 2/3

### Purpose
Protect voice data + ChaCha20-Poly1305 MAC + metadata in frames 1-24.

### Specifications
- **File**: `ldpc_voice_576_384.alist`
- **Block length**: 576 bits
- **Information bits**: 384 bits
- **Parity bits**: 192 bits
- **Code rate**: 2/3 (384/576)
- **Column weights**: 2-4 (variable, irregular)
- **Row weights**: ~5-7 (variable, irregular)

### Voice Frame Payload Structure
```
Uncoded payload:           384 bits
- Opus voice:              320 bits
- ChaCha20 MAC:            128 bits
- Callsign:                 40 bits
- Frame counter:             8 bits
- Reserved:                 24 bits
LDPC encoding:             576 bits coded (rate 2/3)
Total:                     576 bits per frame
```

### Performance Expectations
- Can correct ~10-15% bit errors
- BER 10^-5 at SNR ~5-6 dB
- Good for VHF/UHF multipath conditions

## Matrix Generation

The matrices are generated using `create_custom_ldpc.py`:

```bash
cd ldpc_matrices
python3 create_custom_ldpc.py
```

This creates:
- `ldpc_auth_768_256.alist` - Authentication frame matrix
- `ldpc_voice_576_384.alist` - Voice frame matrix

## GNU Radio Usage

### Authentication Frame Encoder/Decoder

```python
from gnuradio import fec

# Encoder
auth_enc = fec.ldpc_encoder_make(
    'ldpc_matrices/ldpc_auth_768_256.alist',
    'encode'  # syndrome encoding
)

# Decoder
auth_dec = fec.ldpc_decoder.make(
    'ldpc_matrices/ldpc_auth_768_256.alist',
    0.5,  # noise sigma estimate
    20    # max iterations
)
```

### Voice Frame Encoder/Decoder

```python
# Encoder
voice_enc = fec.ldpc_encoder_make(
    'ldpc_matrices/ldpc_voice_576_384.alist',
    'encode'
)

# Decoder
voice_dec = fec.ldpc_decoder.make(
    'ldpc_matrices/ldpc_voice_576_384.alist',
    0.5,  # noise sigma estimate
    20    # max iterations
)
```

## Integration into Flowgraphs

To use these matrices in GRC flowgraphs:

1. Update the `ldpc_matrix_file` variable to point to the appropriate matrix:
   - Frame 0: `"../ldpc_matrices/ldpc_auth_768_256.alist"`
   - Frames 1-24: `"../ldpc_matrices/ldpc_voice_576_384.alist"`

2. Update the LDPC encoder/decoder block definitions:
   - For rate 1/3: `dim1: '1', dim2: '3'`
   - For rate 2/3: `dim1: '2', dim2: '3'`

3. Ensure frame synchronization to distinguish frame 0 from voice frames

## Optimization Notes

These are initial matrices optimized for:
- VHF/UHF multipath (delay spread ~1-5 µs)
- Burst errors from fading
- Balance between protection and capacity

For production use:
1. Test with `ldpc_test` tools in GNU Radio
2. Optimize degree distributions using density evolution
3. Consider channel-specific optimizations
4. Validate performance under expected SNR conditions

## File Format

The matrices are stored in AList format, compatible with GNU Radio's LDPC implementation:

```
Line 1: nrows ncols
Line 2: max_col_degree max_row_degree
Line 3: column degrees (space-separated)
Line 4: row degrees (space-separated)
Lines 5 to 5+n-1: column connections (1-indexed)
Lines 5+n to end: row connections (1-indexed)
```

## References

- GNU Radio LDPC documentation
- LDPC code design principles
- Density evolution for LDPC optimization

