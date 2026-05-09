#!/usr/bin/env python3
"""
Parallel Bit Interleaver Block for Multi-Carrier QPSK

Interleaves bits across multiple carriers and outputs parallel streams.
For 8 carriers: distributes bits round-robin, outputs 8 parallel streams.

Input: uint8 bytes
Output: 8 parallel streams of bits (vector output)
"""

import numpy as np
from gnuradio import gr
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class bit_interleaver_parallel(gr.sync_block):
    """
    Interleave bits across multiple carriers, outputting parallel streams.
    
    Input: uint8 bytes
    Output: Vector of uint8 (num_carriers elements) - one stream per carrier
    
    Distributes bits round-robin: bit 0→carrier 0, bit 1→carrier 1, etc.
    """
    
    def __init__(self, num_carriers=8):
        """
        Initialize parallel bit interleaver.
        
        Args:
            num_carriers: Number of carriers to interleave across
        """
        gr.sync_block.__init__(
            self,
            name="bit_interleaver_parallel",
            in_sig=[np.uint8],  # Input bytes
            out_sig=[(np.uint8, num_carriers)]  # Vector output: one stream per carrier
        )
        
        self.num_carriers = num_carriers
        self.bit_position = 0  # Current bit position (for round-robin)
        
    def work(self, input_items, output_items):
        """
        Interleave bits across carriers, outputting parallel streams.
        
        Takes input bytes, unpacks to bits, distributes round-robin,
        outputs as vectors with one element per carrier.
        """
        if len(input_items) == 0 or len(input_items[0]) == 0:
            return 0
        
        if len(output_items) == 0 or len(output_items[0]) == 0:
            return 0
        
        input_bytes = input_items[0]
        output_vec = output_items[0]
        
        ninput = len(input_bytes)
        noutput = len(output_vec)
        
        # Each output vector contains bits for all carriers at one time step
        # We need num_carriers bits to fill one output vector
        
        # Unpack bytes to bits first
        all_bits = []
        for byte_val in input_bytes:
            # Unpack 8 bits (MSB first)
            for bit_pos in range(8):
                bit = (byte_val >> (7 - bit_pos)) & 1
                all_bits.append(bit)
        
        # Distribute bits round-robin across carriers
        # Output vectors: each vector has num_carriers elements (one per carrier)
        n_vectors = min(noutput, len(all_bits) // self.num_carriers)
        
        for vec_idx in range(n_vectors):
            for carrier_idx in range(self.num_carriers):
                bit_idx = vec_idx * self.num_carriers + carrier_idx
                if bit_idx < len(all_bits):
                    output_vec[vec_idx][carrier_idx] = all_bits[bit_idx]
                else:
                    output_vec[vec_idx][carrier_idx] = 0
        
        return n_vectors


def make_bit_interleaver_parallel(num_carriers=8):
    """Factory function to create parallel bit interleaver"""
    return bit_interleaver_parallel(num_carriers)

