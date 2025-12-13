#!/usr/bin/env python3
"""
LDPC utility functions for encoding and decoding.

Provides functions to load LDPC parity check matrices from alist files
and perform encoding/decoding operations.
"""

import numpy as np
from typing import Tuple, Optional


def load_alist_matrix(filename: str) -> Tuple[np.ndarray, int, int]:
    """
    Load LDPC parity check matrix from alist format file.
    
    Args:
        filename: Path to alist file
        
    Returns:
        Tuple of (parity_check_matrix, n, k) where:
        - parity_check_matrix: Binary matrix H (m x n)
        - n: Codeword length
        - k: Information length (n - m)
    """
    with open(filename, 'r') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    
    # Line 1: n m (codeword length, number of parity checks)
    n, m = map(int, lines[0].split())
    k = n - m
    
    # Line 2: max_col_degree max_row_degree (not needed for matrix construction)
    # Line 3: column degrees
    # Line 4: row degrees
    # Lines 5 to 5+n: column connections (1-indexed)
    # Lines 5+n to end: row connections (1-indexed)
    
    # Build column connections
    col_connections = []
    for i in range(n):
        if 4 + i < len(lines):
            conns = [int(x) - 1 for x in lines[4 + i].split() if x]  # Convert to 0-indexed
            col_connections.append(conns)
        else:
            col_connections.append([])
    
    # Build row connections
    row_connections = []
    for i in range(m):
        if 4 + n + i < len(lines):
            conns = [int(x) - 1 for x in lines[4 + n + i].split() if x]  # Convert to 0-indexed
            row_connections.append(conns)
        else:
            row_connections.append([])
    
    # Build parity check matrix H (m x n)
    H = np.zeros((m, n), dtype=np.uint8)
    for col in range(n):
        for row in col_connections[col]:
            if 0 <= row < m:
                H[row, col] = 1
    
    # Verify row connections match
    for row in range(m):
        for col in row_connections[row]:
            if 0 <= col < n:
                H[row, col] = 1
    
    return H, n, k


def compute_generator_matrix(H: np.ndarray) -> np.ndarray:
    """
    Compute generator matrix G from parity check matrix H.
    
    For systematic encoding, we want G = [I | P] where:
    - I is k x k identity matrix
    - P is k x m parity matrix
    
    We have H = [P^T | I] for systematic form, so we need to rearrange.
    
    Args:
        H: Parity check matrix (m x n)
        
    Returns:
        Generator matrix G (k x n) for systematic encoding
    """
    m, n = H.shape
    k = n - m
    
    # Try to find systematic form: H = [A | I] where A is m x k
    # If not in systematic form, we need to perform Gaussian elimination
    
    # Check if last m columns form identity (systematic form)
    H_last_m = H[:, -m:]
    if np.array_equal(H_last_m, np.eye(m)):
        # Already in systematic form: H = [P^T | I]
        P_T = H[:, :k]  # m x k
        P = P_T.T  # k x m (parity part)
        # Generator: G = [I | P]
        I_k = np.eye(k, dtype=np.uint8)
        G = np.hstack([I_k, P]) % 2
        return G
    
    # Not in systematic form - need Gaussian elimination
    # Convert to systematic form: H = [P^T | I]
    H_sys = H.copy().astype(np.float64)
    
    # Perform Gaussian elimination to get systematic form
    # We want the last m columns to be identity
    for i in range(m):
        # Find pivot in column n-m+i (last m columns)
        pivot_row = None
        for j in range(i, m):
            if H_sys[j, n - m + i] == 1:
                pivot_row = j
                break
        
        if pivot_row is None:
            # Can't find pivot - matrix may not be full rank
            # Try to find any non-zero in this column
            for j in range(m):
                if H_sys[j, n - m + i] == 1:
                    pivot_row = j
                    break
        
        if pivot_row is not None and pivot_row != i:
            # Swap rows
            H_sys[[i, pivot_row]] = H_sys[[pivot_row, i]]
        
        # Eliminate other rows
        if H_sys[i, n - m + i] == 1:
            for j in range(m):
                if j != i and H_sys[j, n - m + i] == 1:
                    H_sys[j] = (H_sys[j] + H_sys[i]) % 2
    
    # Extract P^T and compute G
    P_T = H_sys[:, :k].astype(np.uint8)
    P = P_T.T  # k x m
    I_k = np.eye(k, dtype=np.uint8)
    G = np.hstack([I_k, P]) % 2
    
    return G.astype(np.uint8)


def ldpc_encode(info_bits: np.ndarray, G: np.ndarray) -> np.ndarray:
    """
    Encode information bits using generator matrix.
    
    Args:
        info_bits: Information bits (k bits)
        G: Generator matrix (k x n)
        
    Returns:
        Codeword (n bits)
    """
    if len(info_bits) != G.shape[0]:
        raise ValueError(f"Info bits length {len(info_bits)} doesn't match generator matrix k={G.shape[0]}")
    
    # Systematic encoding: c = u * G
    codeword = (info_bits @ G) % 2
    return codeword.astype(np.uint8)


def ldpc_decode_soft(soft_bits: np.ndarray, H: np.ndarray, max_iter: int = 50) -> np.ndarray:
    """
    Decode soft bits using belief propagation (sum-product algorithm).
    
    Args:
        soft_bits: Soft decisions (LLRs) as float32 array (n bits)
        H: Parity check matrix (m x n)
        max_iter: Maximum iterations
        
    Returns:
        Decoded hard bits (k information bits)
    """
    m, n = H.shape
    k = n - m
    
    # Handle case where we don't have enough soft bits
    if len(soft_bits) < n:
        # Pad with zeros (low confidence)
        soft_bits_padded = np.zeros(n, dtype=np.float32)
        soft_bits_padded[:len(soft_bits)] = soft_bits
        soft_bits = soft_bits_padded
    elif len(soft_bits) > n:
        # Truncate to n bits
        soft_bits = soft_bits[:n]
    
    # Initialize variable node messages (from variable nodes to check nodes)
    # VN[i][j] = message from variable node i to check node j
    VN = {}
    for i in range(n):
        VN[i] = {}
        for j in range(m):
            if H[j, i] == 1:
                # Initialize with channel LLR
                VN[i][j] = float(soft_bits[i])
    
    # Initialize check node messages (from check nodes to variable nodes)
    CN = {}
    for j in range(m):
        CN[j] = {}
        for i in range(n):
            if H[j, i] == 1:
                CN[j][i] = 0.0
    
    # Belief propagation iterations
    for iteration in range(max_iter):
        # Update check node messages
        for j in range(m):
            neighbors = [i for i in range(n) if H[j, i] == 1]
            if len(neighbors) == 0:
                continue
            for i in neighbors:
                # Compute product of tanh of all other messages
                product = 1.0
                for i2 in neighbors:
                    if i2 != i:
                        msg = VN[i2].get(j, 0.0)
                        tanh_val = np.tanh(msg / 2.0)
                        # Clamp to avoid numerical issues
                        tanh_val = np.clip(tanh_val, -0.999999, 0.999999)
                        product *= tanh_val
                
                # Check node message: 2 * atanh(product)
                if abs(product) >= 0.999999:
                    CN[j][i] = 0.0
                else:
                    try:
                        CN[j][i] = 2.0 * np.arctanh(product)
                    except (OverflowError, ValueError):
                        CN[j][i] = 0.0
        
        # Update variable node messages
        for i in range(n):
            neighbors = [j for j in range(m) if H[j, i] == 1]
            for j in neighbors:
                # Sum of channel LLR and all other check node messages
                msg_sum = float(soft_bits[i])
                for j2 in neighbors:
                    if j2 != j:
                        msg_sum += CN[j2].get(i, 0.0)
                VN[i][j] = msg_sum
        
        # Compute posterior LLRs for early stopping
        posterior = np.zeros(n, dtype=np.float32)
        for i in range(n):
            neighbors = [j for j in range(m) if H[j, i] == 1]
            posterior[i] = float(soft_bits[i])
            for j in neighbors:
                posterior[i] += CN[j].get(i, 0.0)
        
        # Hard decision
        hard_bits = (posterior < 0).astype(np.uint8)
        
        # Check if valid codeword (all parity checks satisfied)
        syndrome = (H @ hard_bits) % 2
        if np.sum(syndrome) == 0:
            # Valid codeword found
            break
    
    # Extract information bits (first k bits for systematic code)
    # If code is not systematic, we return all decoded bits
    info_bits = hard_bits[:k] if k > 0 else hard_bits
    return info_bits

