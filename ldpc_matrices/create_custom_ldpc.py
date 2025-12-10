#!/usr/bin/env python3
"""
Create custom LDPC matrices for gr-sleipnir superframe structure.

Code 1: Authentication frame - LDPC (768, 256) Rate 1/3
Code 2: Voice frame - LDPC (576, 384) Rate 2/3
"""

import numpy as np
import os

def create_protograph_ldpc(n, k, column_weights, row_weights, seed=42):
    """
    Create protograph-based LDPC matrix
    
    Parameters:
    -----------
    n : int
        Codeword length
    k : int
        Message length
    column_weights : list
        Possible column weights (variable)
    row_weights : list
        Possible row weights (variable)
    seed : int
        Random seed for reproducibility
    """
    np.random.seed(seed)
    m = n - k  # parity bits
    
    # Initialize parity check matrix
    H = np.zeros((m, n), dtype=int)
    
    # Create systematic structure: [I | P] where I is identity for parity bits
    # This ensures efficient encoding
    
    # Information bits (first k columns) - variable column weight
    for col in range(k):
        weight = np.random.choice(column_weights)
        # Select rows ensuring no cycles of length 4
        attempts = 0
        while attempts < 100:
            rows = np.random.choice(m, min(weight, m), replace=False)
            # Check for 4-cycles (simplified check)
            valid = True
            for r in rows:
                if np.sum(H[r, :col]) > 0:
                    # Potential 4-cycle, try different rows
                    if attempts < 50:
                        valid = False
                        break
            if valid:
                H[rows, col] = 1
                break
            attempts += 1
        if attempts >= 100:
            # Fallback: just assign randomly
            rows = np.random.choice(m, min(weight, m), replace=False)
            H[rows, col] = 1
    
    # Parity bits (last m columns) - dual diagonal structure for encoding
    for i in range(m):
        col = k + i
        H[i, col] = 1  # Main diagonal
        if i > 0:
            H[i-1, col] = 1  # Sub-diagonal
    
    # Balance row weights
    for row in range(m):
        current_weight = np.sum(H[row, :])
        target = np.random.choice(row_weights)
        if current_weight < target:
            # Add connections to information bits
            available = np.where((H[row, :k] == 0))[0]
            if len(available) > 0:
                add = min(target - current_weight, len(available))
                add_cols = np.random.choice(available, add, replace=False)
                H[row, add_cols] = 1
    
    # Ensure no zero-weight rows or columns
    for row in range(m):
        if np.sum(H[row, :]) == 0:
            # Add a random connection
            col = np.random.randint(0, n)
            H[row, col] = 1
    
    for col in range(n):
        if np.sum(H[:, col]) == 0:
            # Add a random connection
            row = np.random.randint(0, m)
            H[row, col] = 1
    
    return H

def save_alist(H, filename):
    """
    Save LDPC matrix in AList format for GNU Radio
    
    AList format:
    Line 1: nrows ncols
    Line 2: max_col_degree max_row_degree
    Line 3: column degrees (space-separated)
    Line 4: row degrees (space-separated)
    Lines 5 to 5+n-1: column connections (1-indexed)
    Lines 5+n to end: row connections (1-indexed)
    """
    m, n = H.shape
    
    # Get column and row degrees
    col_degrees = np.sum(H, axis=0).astype(int)
    row_degrees = np.sum(H, axis=1).astype(int)
    
    max_col_degree = int(np.max(col_degrees))
    max_row_degree = int(np.max(row_degrees))
    
    with open(filename, 'w') as f:
        # Header: n m (codeword length, parity checks)
        # GNU Radio LDPC decoder expects: n (codeword length) m (parity checks)
        f.write(f"{n} {m}\n")
        f.write(f"{max_col_degree} {max_row_degree}\n")
        
        # Column degrees
        f.write(" ".join(map(str, col_degrees)) + "\n")
        
        # Row degrees
        f.write(" ".join(map(str, row_degrees)) + "\n")
        
        # Column connections (for each column, list rows with 1s, 1-indexed)
        for col in range(n):
            rows = np.where(H[:, col] == 1)[0] + 1  # 1-indexed
            if len(rows) > 0:
                f.write(" ".join(map(str, rows)) + "\n")
            else:
                f.write("\n")
        
        # Row connections (for each row, list columns with 1s, 1-indexed)
        for row in range(m):
            cols = np.where(H[row, :] == 1)[0] + 1  # 1-indexed
            if len(cols) > 0:
                f.write(" ".join(map(str, cols)) + "\n")
            else:
                f.write("\n")
    
    print(f"  Saved: {filename}")
    print(f"    Dimensions: {m}x{n} (rate {n-m}/{n} = {(n-m)/n:.3f})")
    print(f"    Column degrees: min={np.min(col_degrees)}, max={np.max(col_degrees)}, avg={np.mean(col_degrees):.2f}")
    print(f"    Row degrees: min={np.min(row_degrees)}, max={np.max(row_degrees)}, avg={np.mean(row_degrees):.2f}")

def main():
    """Generate LDPC matrices for gr-sleipnir"""
    
    # Ensure output directory exists
    os.makedirs(".", exist_ok=True)
    
    print("=" * 60)
    print("Creating Custom LDPC Matrices for gr-sleipnir")
    print("=" * 60)
    print()
    
    # Code 1a: Authentication frame (768, 256) Rate 1/3 (32-byte signature, legacy)
    print("Code 1a: Authentication Frame (Legacy) - LDPC (768, 256) Rate 1/3")
    print("-" * 60)
    print("Purpose: Protect BrainpoolP256r1 signature (32-byte truncated)")
    print("Block length: 768 bits")
    print("Information bits: 256 bits (32 bytes)")
    print("Parity bits: 512 bits")
    print()
    
    H_auth_legacy = create_protograph_ldpc(
        n=768,
        k=256,
        column_weights=[3, 4, 5, 6],
        row_weights=[10, 11, 12, 13],
        seed=42
    )
    
    save_alist(H_auth_legacy, "ldpc_auth_768_256.alist")
    print()
    
    # Code 1b: Authentication frame (1536, 512) Rate 1/3 (64-byte full signature)
    print("Code 1b: Authentication Frame (Full Signature) - LDPC (1536, 512) Rate 1/3")
    print("-" * 60)
    print("Purpose: Protect full ECDSA signature (64 bytes: r + s)")
    print("Block length: 1536 bits")
    print("Information bits: 512 bits (64 bytes)")
    print("Parity bits: 1024 bits")
    print()
    
    H_auth_full = create_protograph_ldpc(
        n=1536,
        k=512,
        column_weights=[3, 4, 5, 6],
        row_weights=[10, 11, 12, 13],
        seed=44  # Different seed for new matrix
    )
    
    save_alist(H_auth_full, "ldpc_auth_1536_512.alist")
    print()
    
    # Code 2: Voice frame (576, 384) Rate 2/3
    print("Code 2: Voice Frame - LDPC (576, 384) Rate 2/3")
    print("-" * 60)
    print("Purpose: Protect voice + MAC")
    print("Block length: 576 bits")
    print("Information bits: 384 bits")
    print("Parity bits: 192 bits")
    print()
    
    H_voice = create_protograph_ldpc(
        n=576,
        k=384,
        column_weights=[2, 3, 4],
        row_weights=[5, 6, 7],
        seed=43
    )
    
    save_alist(H_voice, "ldpc_voice_576_384.alist")
    print()
    
    print("=" * 60)
    print("Matrix Generation Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Test matrices with GNU Radio LDPC tools")
    print("2. Optimize degree distributions using density evolution")
    print("3. Integrate into gr-sleipnir flowgraphs")
    print()
    print("Note: These are initial matrices. For production use,")
    print("      optimize using LDPC design tools for your specific")
    print("      channel conditions and performance requirements.")

if __name__ == "__main__":
    main()

