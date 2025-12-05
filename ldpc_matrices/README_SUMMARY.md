# LDPC Matrices Summary

## Available Matrices

### Superframe Structure Matrices (New)

1. **ldpc_auth_768_256.alist** - Rate 1/3
   - Authentication frame (Frame 0)
   - 768 bits coded, 256 bits information
   - Strong protection for signature

2. **ldpc_voice_576_384.alist** - Rate 2/3
   - Voice frames (Frames 1-24)
   - 576 bits coded, 384 bits information
   - Optimized for voice + MAC protection

### Legacy Matrices (For Testing)

3. **ldpc_rate34.alist** - Rate 3/4
   - Simplified matrix for 4FSK mode testing
   - 800 bits coded, 600 bits information

4. **ldpc_rate23.alist** - Rate 2/3
   - Simplified matrix for 8FSK mode testing
   - 900 bits coded, 600 bits information

## Usage

### In GRC Flowgraphs

Update the `ldpc_matrix_file` variable to point to the desired matrix:

```yaml
- name: ldpc_matrix_file
  id: variable
  parameters:
    value: '"../ldpc_matrices/ldpc_auth_768_256.alist"'
```

### For Superframe Implementation

- **Frame 0**: Use `ldpc_auth_768_256.alist` (rate 1/3)
- **Frames 1-24**: Use `ldpc_voice_576_384.alist` (rate 2/3)

See `SUPERFRAME_LDPC.md` for detailed specifications.

## Generation

To regenerate matrices:

```bash
cd ldpc_matrices
python3 create_custom_ldpc.py
```

## File Format

All matrices are in AList format, compatible with GNU Radio's LDPC encoder/decoder blocks.
