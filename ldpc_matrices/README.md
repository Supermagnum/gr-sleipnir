# LDPC Parity Check Matrices

This directory contains LDPC parity check matrix files (alist format) for the gr-sleipnir system.

## Required Matrices

### 4FSK Mode - Rate 3/4 LDPC
- **File**: `ldpc_rate34.alist`
- **Code Rate**: 3/4 (6,000 bps raw -> 8,000 bps coded)
- **Usage**: 4FSK mode forward error correction

### 8FSK Mode - Rate 2/3 LDPC
- **File**: `ldpc_rate23.alist`
- **Code Rate**: 2/3 (8,000 bps raw -> 12,000 bps coded)
- **Usage**: 8FSK mode forward error correction

## Matrix Generation

LDPC matrices can be generated using tools such as:
- `make-ldpc` from the GNU Radio LDPC tools
- Online LDPC matrix generators
- Custom scripts using libraries like `pyldpc`

## Alist File Format

The alist format is a text-based format for representing sparse parity check matrices:

```
nrows ncols
max_degree_row max_degree_col
row_degree_list
col_degree_list
non-zero positions (row-major)
non-zero positions (col-major)
```

## Notes

- Matrices should be optimized for the specific code rates and frame sizes
- Frame sizes should match the Opus frame structure (typically 20ms frames)
- Matrices need to be compatible with GNU Radio's LDPC decoder implementation

