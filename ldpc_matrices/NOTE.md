# LDPC Matrix Generation Note

## Required Matrices

The flowgraph requires LDPC parity check matrices in alist format:

### Rate 3/4 Matrix (for 4FSK mode)
- **File**: `ldpc_rate34.alist`
- **Code Rate**: 3/4 (k/n = 3/4)
- **Example dimensions**: n=1200, k=900 or n=800, k=600
- **Usage**: Encodes 6,000 bps raw data to 8,000 bps coded data

### Rate 2/3 Matrix (for 8FSK mode - future)
- **File**: `ldpc_rate23.alist`
- **Code Rate**: 2/3 (k/n = 2/3)
- **Example dimensions**: n=1200, k=800 or n=900, k=600
- **Usage**: Encodes 8,000 bps raw data to 12,000 bps coded data

## Generating LDPC Matrices

### Option 1: Use GNU Radio Tools
GNU Radio includes Python tools for generating LDPC matrices:
```bash
python3 /usr/lib/python3/dist-packages/gnuradio/fec/LDPC/Generate_LDPC_matrix.py
```

### Option 2: Use Online Generators
Search for "LDPC matrix generator" or "alist format LDPC" online tools.

### Option 3: Use pyldpc Library
```python
import pyldpc
# Generate rate 3/4 matrix
H, G = pyldpc.make_ldpc(n=1200, d_v=3, d_c=6, systematic=True, sparse=True)
# Convert to alist format and save
```

## Alist File Format

The alist format is a text-based sparse matrix representation:
- Line 1: nrows ncols
- Line 2: max_degree_row max_degree_col
- Line 3: row_degree_list (space-separated)
- Line 4: col_degree_list (space-separated)
- Remaining lines: non-zero positions

## Temporary Solution

Until proper matrices are generated, you can temporarily use an existing GNU Radio matrix:
```bash
cp /usr/share/gnuradio/fec/ldpc/n_1800_k_0902_gap_28.alist ldpc_matrices/ldpc_rate34.alist
```
Note: This is rate 1/2, not 3/4, so it will not work correctly. It's only for testing the flowgraph structure.

## Frame Size Considerations

The LDPC frame size should be compatible with:
- Opus frame structure (typically 20ms frames)
- 4FSK symbol mapping (2 bits per symbol)
- Overall system latency requirements

For 8 kHz audio at 20ms frames:
- Raw audio: 160 samples = 160 bytes (mono, 8-bit) or 320 bytes (mono, 16-bit)
- After G.711 encoding: 160 bytes
- After LDPC encoding (rate 3/4): ~213 bytes
- After 4FSK mapping: ~427 symbols

Choose matrix dimensions that accommodate these frame sizes efficiently.

