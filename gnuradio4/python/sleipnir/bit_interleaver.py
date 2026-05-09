#!/usr/bin/env python3
"""
Bit Interleaver Block for Multi-Carrier QPSK

Interleaves bits across multiple carriers for parallel QPSK modulation.
For 8 carriers: distributes bits round-robin (bit 0 → carrier 0, bit 1 → carrier 1, ..., bit 7 → carrier 7, repeat)

Input: uint8 bytes
Output: uint8 stream (bits interleaved, ready for per-carrier processing)
"""

import numpy as np
from gnuradio import gr
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class bit_interleaver(gr.sync_block):
    """
    Interleave bits across multiple carriers using round-robin distribution.
    
    This block distributes input bits round-robin across carriers:
    - Bit 0 → Carrier 0
    - Bit 1 → Carrier 1
    - ...
    - Bit 7 → Carrier 7
    - Bit 8 → Carrier 0 (repeat)
    
    Input: uint8 bytes
    Output: uint8 bits (interleaved, with internal state for carrier assignment)
    
    Note: This is a simplified implementation. For full parallel processing,
    use GNU Radio's stream_to_vector and process each carrier in parallel.
    """
    
    def __init__(self, num_carriers=8):
        """
        Initialize bit interleaver.
        
        Args:
            num_carriers: Number of carriers to interleave across
        """
        gr.sync_block.__init__(
            self,
            name="bit_interleaver",
            in_sig=[np.uint8],  # Input bytes
            out_sig=[np.uint8]  # Output bits (interleaved)
        )
        
        self.num_carriers = num_carriers
        self.bit_position = 0  # Current bit position (for round-robin)
        
        # Buffer for interleaved bits (per carrier)
        self.carrier_buffers = [[] for _ in range(num_carriers)]
        
    def work(self, input_items, output_items):
        """
        Interleave bits across carriers using round-robin.
        
        For simplicity, output bits in interleaved order.
        A full implementation would output parallel streams.
        """
        if len(input_items) == 0 or len(input_items[0]) == 0:
            return 0
        
        if len(output_items) == 0 or len(output_items[0]) == 0:
            return 0
        
        input_bytes = input_items[0]
        output_bits = output_items[0]
        
        ninput = len(input_bytes)
        noutput = len(output_bits)
        
        # Unpack bytes to bits and distribute round-robin
        output_idx = 0
        for byte_val in input_bytes:
            # Unpack 8 bits (MSB first)
            for bit_pos in range(8):
                bit = (byte_val >> (7 - bit_pos)) & 1
                carrier_idx = self.bit_position % self.num_carriers
                
                # Store bit in carrier buffer
                self.carrier_buffers[carrier_idx].append(bit)
                self.bit_position += 1
                
                # Output bit if space available (simplified: output in order)
                if output_idx < noutput:
                    output_bits[output_idx] = bit
                    output_idx += 1
        
        return output_idx


def make_bit_interleaver(num_carriers=8):
    """Factory function to create bit_interleaver block"""
    return bit_interleaver(num_carriers)

