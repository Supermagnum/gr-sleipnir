#!/usr/bin/env python3
"""
FSK Symbol to LLR Converter Block

Converts FSK symbol values to bit-level Log-Likelihood Ratios (LLRs) for soft-decision LDPC decoding.

For 4FSK: symbols are -3, -1, 1, 3 (mapped to 00, 01, 11, 10 in Gray code)
For 8FSK: symbols are -7, -5, -3, -1, 1, 3, 5, 7 (mapped to 000, 001, 011, 010, 110, 111, 101, 100 in Gray code)

LLR = log(P(bit=0) / P(bit=1))
- Positive LLR = bit likely 0
- Negative LLR = bit likely 1
- Magnitude = confidence
"""

import numpy as np
from gnuradio import gr
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class fsk_symbol_to_llr(gr.interp_block):
    """
    Convert FSK symbol values to bit-level LLRs.
    
    Input: float32 symbol values (from symbol sync)
    Output: float32 LLRs (one per bit, expanded from symbols)
    
    Uses buffering to handle variable input/output ratio.
    """
    
    def __init__(self, fsk_levels=4, scale_factor=2.0):
        """
        Initialize FSK symbol to LLR converter.
        
        Args:
            fsk_levels: Number of FSK levels (4 or 8)
            scale_factor: Scaling factor for LLR magnitude (higher = more confidence)
        """
        if fsk_levels == 4:
            interp = 2  # 2 bits per symbol for 4FSK
        elif fsk_levels == 8:
            interp = 3  # 3 bits per symbol for 8FSK
        else:
            raise ValueError(f"Unsupported FSK levels: {fsk_levels}")
        
        gr.interp_block.__init__(
            self,
            name="fsk_symbol_to_llr",
            in_sig=[np.float32],
            out_sig=[np.float32],
            interp=interp
        )
        
        # CRITICAL: Request larger output buffers to feed decoder router faster
        # This helps accumulate soft bits more quickly in the decoder router
        try:
            # Request output in multiples of 256 symbols (produces 512 LLRs for 4FSK)
            # This allows downstream blocks to receive larger chunks
            self.set_output_multiple(256 * interp)  # 256 symbols * interp = LLRs
            print(f"FSK-to-LLR: Set output_multiple={256 * interp} (256 symbols * {interp} bits/symbol)")
        except Exception as e:
            print(f"FSK-to-LLR: Could not set output_multiple: {e}")
        
        self.fsk_levels = fsk_levels
        self.scale_factor = scale_factor
        self.bits_per_symbol = interp
        
        # Symbol tables for reference
        if fsk_levels == 4:
            # 4FSK symbol mapping (Gray code):
            # -3 -> 00
            # -1 -> 01
            #  1 -> 11
            #  3 -> 10
            self.symbol_table = [-3, -1, 1, 3]
        elif fsk_levels == 8:
            self.bits_per_symbol = 3
            # 8FSK symbol mapping (Gray code):
            # -7 -> 000, -5 -> 001, -3 -> 011, -1 -> 010
            #  1 -> 110,  3 -> 111,  5 -> 101,  7 -> 100
            self.symbol_table = [-7, -5, -3, -1, 1, 3, 5, 7]
        else:
            raise ValueError(f"Unsupported FSK levels: {fsk_levels}")
    
    def work(self, input_items, output_items):
        """
        Convert symbol values to bit-level LLRs.
        
        For interp_block, this is called with ninput input items and
        ninput * interp output items. We process each input symbol and
        produce interp LLRs for it.
        """
        if len(input_items) == 0 or len(input_items[0]) == 0:
            return 0
        
        if len(output_items) == 0 or len(output_items[0]) == 0:
            return 0
        
        input_symbols = input_items[0]
        llrs = output_items[0]
        ninput = len(input_symbols)
        noutput = len(llrs)
        
        # Debug: Log first few calls
        if not hasattr(self, '_llr_call_count'):
            self._llr_call_count = 0
            print(f"FSK-to-LLR: Block initialized, first work() call")
        self._llr_call_count += 1
        
        if self._llr_call_count <= 10:
            print(f"FSK-to-LLR: Call #{self._llr_call_count}, received {ninput} symbols, output space: {noutput} LLRs (need {ninput * self.bits_per_symbol})")
        
        # For interp_block, GNU Radio guarantees noutput >= ninput * interp
        # Process all input items and produce interp LLRs for each
        # But ensure we don't exceed output buffer
        max_output_items = noutput // self.bits_per_symbol
        nprocess = min(ninput, max_output_items)
        
        # Process each input symbol and produce interp LLRs
        for i in range(nprocess):
            sym = input_symbols[i]
            output_idx = i * self.bits_per_symbol
            
            # Ensure we don't write beyond output buffer
            if output_idx + self.bits_per_symbol > noutput:
                break
            
            if self.fsk_levels == 4:
                # 4FSK: 2 bits per symbol
                # Gray code mapping: -3->00, -1->01, 1->11, 3->10
                # Bit 0 (LSB): 0 for -3 and 3, 1 for -1 and 1
                #   Decision boundary: bit0 = 1 if |sym| is close to 1, bit0 = 0 if |sym| is close to 3
                # Bit 1 (MSB): 0 for -3 and -1, 1 for 1 and 3
                #   Decision boundary at 0: bit1 = 1 if sym > 0, bit1 = 0 if sym < 0
                
                # Bit 0 LLR: based on distance from ±1 vs ±3
                # Symbols -1, 1: |sym| = 1 -> bit 0 = 1 -> negative LLR
                # Symbols -3, 3: |sym| = 3 -> bit 0 = 0 -> positive LLR
                # Decision boundary at |sym| = 2
                if abs(sym) < 2:
                    # Bit 0 = 1 -> negative LLR, magnitude based on distance from 2
                    llrs[output_idx] = -(2 - abs(sym)) * self.scale_factor
                else:
                    # Bit 0 = 0 -> positive LLR, magnitude based on distance from 2
                    llrs[output_idx] = (abs(sym) - 2) * self.scale_factor
                
                # Bit 1 LLR: based on sign of symbol
                # Positive symbol (1, 3) -> bit 1 = 1 -> negative LLR
                # Negative symbol (-3, -1) -> bit 1 = 0 -> positive LLR
                # LLR magnitude proportional to distance from 0
                # Calculate and assign directly - ensure negative values are preserved
                bit1_llr = -sym * self.scale_factor
                llrs[output_idx + 1] = bit1_llr
        
            elif self.fsk_levels == 8:
                # 8FSK: 3 bits per symbol
                # More complex mapping with Gray code
                # Bit 0 (LSB): decision boundary at 0
                # Bit 1: decision boundaries at -4 and +4
                # Bit 2 (MSB): decision boundaries at -2, +2, -6, +6
                
                # Bit 0 LLR: based on sign
                llrs[output_idx] = -sym * self.scale_factor
                
                # Bit 1 LLR: based on distance from ±4
                # Decision boundary at -4 and +4
                if abs(sym) < 4:
                    llrs[output_idx + 1] = (abs(sym) - 4) * self.scale_factor
                else:
                    llrs[output_idx + 1] = (abs(sym) - 4) * self.scale_factor
                
                # Bit 2 LLR: based on distance from ±2 and ±6
                # Decision boundaries at -6, -2, +2, +6
                if abs(sym) <= 2:
                    # Close to center, uncertain
                    llrs[output_idx + 2] = (abs(sym) - 2) * self.scale_factor
                elif abs(sym) <= 6:
                    # Middle range
                    llrs[output_idx + 2] = (4 - abs(sym)) * self.scale_factor
                else:
                    # Far from center, certain
                    llrs[output_idx + 2] = (abs(sym) - 6) * self.scale_factor
                
                # Advance output index for next symbol
                output_idx += self.bits_per_symbol
        
        # For sync_block, we need to return the number of input items consumed
        # But we also need to ensure we're producing output at 2x the input rate
        # If we produced output, consume proportional input
        # If we didn't produce output but have buffered symbols, we still need to consume some input
        
        # For interp_block, return number of input items consumed
        # We process nprocess items and produce nprocess * interp output items
        return nprocess


def make_fsk_symbol_to_llr(fsk_levels=4, scale_factor=2.0):
    """Factory function to create fsk_symbol_to_llr block"""
    return fsk_symbol_to_llr(fsk_levels, scale_factor)

