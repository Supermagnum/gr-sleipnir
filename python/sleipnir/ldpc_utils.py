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


def ldpc_decode_soft(soft_bits: np.ndarray, H: np.ndarray, max_iter: int = 50, 
                     algorithm: str = 'sum_product', min_sum_scale: float = 0.75) -> np.ndarray:
    """
    Decode soft bits using belief propagation (sum-product or min-sum algorithm).
    
    Args:
        soft_bits: Soft decisions (LLRs) as float32 array (n bits)
                  LLR = log(P(bit=0) / P(bit=1))
                  Positive LLR means bit is likely 0, negative means likely 1
        H: Parity check matrix (m x n)
        max_iter: Maximum iterations
        algorithm: 'sum_product' (default) or 'min_sum' (faster, slightly less accurate)
        min_sum_scale: Scaling factor for min-sum algorithm (default: 0.75)
        
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
    
    # Clip LLRs to reasonable range to avoid numerical issues
    # Typical LLR range: -20 to +20 for good channels, -5 to +5 for noisy channels
    soft_bits = np.clip(soft_bits, -50.0, 50.0).astype(np.float32)
    
    # Pre-compute neighbor lists for efficiency
    var_neighbors = [[] for _ in range(n)]  # For each variable node, list of check nodes
    check_neighbors = [[] for _ in range(m)]  # For each check node, list of variable nodes
    
    for j in range(m):
        for i in range(n):
            if H[j, i] == 1:
                var_neighbors[i].append(j)
                check_neighbors[j].append(i)
    
    # Initialize variable node messages (from variable nodes to check nodes)
    # VN[i][j] = message from variable node i to check node j
    VN = np.zeros((n, m), dtype=np.float32)
    for i in range(n):
        for j in var_neighbors[i]:
            # Initialize with channel LLR
            VN[i, j] = float(soft_bits[i])
    
    # Initialize check node messages (from check nodes to variable nodes)
    CN = np.zeros((m, n), dtype=np.float32)
    
    # Belief propagation iterations
    for iteration in range(max_iter):
        # Update check node messages
        if algorithm == 'min_sum':
            # Min-sum algorithm (faster, slightly less accurate)
            for j in range(m):
                neighbors = check_neighbors[j]
                if len(neighbors) == 0:
                    continue
                for i in neighbors:
                    # Min-sum: minimum of absolute values, with sign product
                    min_abs = float('inf')
                    sign_product = 1.0
                    neighbor_count = 0
                    for i2 in neighbors:
                        if i2 != i:
                            msg_abs = abs(VN[i2, j])
                            msg_sign = 1.0 if VN[i2, j] >= 0 else -1.0
                            if msg_abs < min_abs:
                                min_abs = msg_abs
                            sign_product *= msg_sign
                            neighbor_count += 1
                    # Handle edge case: if only one neighbor (shouldn't happen in valid LDPC)
                    if neighbor_count == 0:
                        CN[j, i] = 0.0
                    else:
                        # Apply scaling factor and sign
                        CN[j, i] = min_sum_scale * min_abs * sign_product
        else:
            # Sum-product algorithm (default, more accurate)
            for j in range(m):
                neighbors = check_neighbors[j]
                if len(neighbors) == 0:
                    continue
                for i in neighbors:
                    # Compute product of tanh of all other messages
                    product = 1.0
                    for i2 in neighbors:
                        if i2 != i:
                            msg = VN[i2, j]
                            # More stable tanh computation
                            msg_clipped = np.clip(msg, -20.0, 20.0)
                            tanh_val = np.tanh(msg_clipped / 2.0)
                            # Clamp to avoid numerical issues
                            tanh_val = np.clip(tanh_val, -0.999999, 0.999999)
                            product *= tanh_val
                    
                    # Check node message: 2 * atanh(product)
                    if abs(product) >= 0.999999:
                        CN[j, i] = 0.0
                    else:
                        try:
                            # Clamp product for atanh
                            product_clamped = np.clip(product, -0.999999, 0.999999)
                            CN[j, i] = 2.0 * np.arctanh(product_clamped)
                        except (OverflowError, ValueError):
                            CN[j, i] = 0.0
        
        # Update variable node messages
        for i in range(n):
            neighbors = var_neighbors[i]
            for j in neighbors:
                # Sum of channel LLR and all other check node messages
                msg_sum = float(soft_bits[i])
                for j2 in neighbors:
                    if j2 != j:
                        msg_sum += CN[j2, i]
                VN[i, j] = msg_sum
        
        # Compute posterior LLRs for early stopping
        posterior = np.zeros(n, dtype=np.float32)
        for i in range(n):
            neighbors = var_neighbors[i]
            posterior[i] = float(soft_bits[i])
            for j in neighbors:
                posterior[i] += CN[j, i]
        
        # Hard decision
        hard_bits = (posterior < 0).astype(np.uint8)
        
        # Check if valid codeword (all parity checks satisfied)
        # Use sparse matrix multiplication for efficiency
        syndrome = np.zeros(m, dtype=np.uint8)
        for j in range(m):
            for i in check_neighbors[j]:
                syndrome[j] = (syndrome[j] + hard_bits[i]) % 2
        
        if np.sum(syndrome) == 0:
            # Valid codeword found - early termination
            break
    
    # Extract information bits (first k bits for systematic code)
    # If code is not systematic, we return all decoded bits
    info_bits = hard_bits[:k] if k > 0 else hard_bits
    return info_bits


def convert_hard_to_llr(hard_bits: np.ndarray, confidence: float = 5.0) -> np.ndarray:
    """
    Convert hard bits to LLRs (for testing or when demodulator only outputs hard bits).
    
    Args:
        hard_bits: Hard bits (0 or 1) as uint8 array
        confidence: LLR magnitude for confident bits (default: 5.0)
                   Higher values = more confidence
                   
    Returns:
        LLR array: Positive for bit=0, negative for bit=1
    """
    llrs = np.zeros(len(hard_bits), dtype=np.float32)
    llrs[hard_bits == 0] = confidence
    llrs[hard_bits == 1] = -confidence
    return llrs


def convert_demod_metrics_to_llr(metrics: np.ndarray, modulation: str = '4fsk') -> np.ndarray:
    """
    Convert demodulator metrics to LLRs.
    
    For FSK demodulators, metrics typically represent symbol likelihoods.
    This function converts symbol metrics to bit-level LLRs.
    
    Args:
        metrics: Demodulator output metrics (symbol likelihoods or distances)
        modulation: Modulation type ('4fsk' or '8fsk')
        
    Returns:
        LLR array for bits
    """
    if modulation == '4fsk':
        # 4FSK: 2 bits per symbol
        # Metrics should be 4 values per symbol (likelihoods for each symbol)
        # Convert to bit LLRs
        # This is a simplified conversion - actual implementation depends on demodulator
        bits_per_symbol = 2
    elif modulation == '8fsk':
        # 8FSK: 3 bits per symbol
        bits_per_symbol = 3
    else:
        raise ValueError(f"Unsupported modulation: {modulation}")
    
    # For now, return a simple conversion
    # In practice, this should use the actual demodulator output format
    # Assuming metrics are already in LLR form or can be converted
    if len(metrics.shape) == 1:
        # Flatten metrics and convert
        llrs = metrics.astype(np.float32)
    else:
        # Multi-dimensional metrics - flatten
        llrs = metrics.flatten().astype(np.float32)
    
    return llrs

