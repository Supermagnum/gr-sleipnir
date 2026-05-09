#!/usr/bin/env python3
"""
QPSK Symbol to LLR Converter Block

Converts QPSK complex symbol values to bit-level Log-Likelihood Ratios (LLRs) for soft-decision LDPC decoding.

QPSK constellation:
- 00 → (1+1j)/√2 ≈ 0.707+0.707j (or 1+1j normalized)
- 01 → (-1+1j)/√2 ≈ -0.707+0.707j (or -1+1j normalized)
- 10 → (1-1j)/√2 ≈ 0.707-0.707j (or 1-1j normalized)
- 11 → (-1-1j)/√2 ≈ -0.707-0.707j (or -1-1j normalized)

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


class qpsk_symbol_to_llr(gr.interp_block):
    """
    Convert QPSK complex symbols to bit-level LLRs.
    
    Input: complex64 symbol values (from symbol sync)
    Output: float32 LLRs (2 bits per symbol)
    
    Uses interp_block to produce 2 LLRs per input symbol.
    """
    
    def __init__(self, scale_factor=2.0):
        """
        Initialize QPSK symbol to LLR converter.
        
        Args:
            scale_factor: Scaling factor for LLR magnitude (higher = more confidence)
        """
        # QPSK has 2 bits per symbol
        interp = 2
        
        gr.interp_block.__init__(
            self,
            name="qpsk_symbol_to_llr",
            in_sig=[np.complex64],
            out_sig=[np.float32],
            interp=interp
        )
        
        # CRITICAL: Set output multiple to ensure scheduler requests aligned output sizes
        # This helps with scheduling when connected to downstream blocks like decoder_router
        # Request output in multiples of interp (2 LLRs per symbol) for better alignment
        try:
            # Request output in multiples of 2 (minimum for interp=2) to allow small initial batches
            # Smaller multiple allows scheduler to call work() with less input data
            # This helps when upstream blocks produce data slowly or in small chunks
            self.set_output_multiple(interp)  # Minimum: 2 LLRs (1 symbol * 2 LLRs/symbol)
            print(f"QPSK-to-LLR: Set output_multiple={interp} (minimum for {interp} LLRs/symbol)")
        except Exception as e:
            print(f"QPSK-to-LLR: Could not set output_multiple: {e}")
        
        self.scale_factor = scale_factor
        self.bits_per_symbol = interp
    
    def work(self, input_items, output_items):
        """
        Convert QPSK complex symbols to bit-level LLRs.
        
        For QPSK:
        - Bit 0 (LSB): I component (real part > 0 → bit 0 = 0, real < 0 → bit 0 = 1)
        - Bit 1 (MSB): Q component (imag part > 0 → bit 1 = 0, imag < 0 → bit 1 = 1)
        """
        # Debug: Track if work() is being called
        if not hasattr(self, '_work_call_count'):
            self._work_call_count = 0
            self._total_input_symbols = 0
            self._total_output_llrs = 0
            self._last_log_time = None
            import time
            self._start_time = time.time()
            print(f"QPSK symbol-to-LLR: First work() call - block is being scheduled!")
            import sys
            sys.stderr.write("QPSK symbol-to-LLR: First work() call\n")
            sys.stderr.flush()
        self._work_call_count += 1
        
        if len(input_items) == 0 or len(input_items[0]) == 0:
            if self._work_call_count <= 5:
                print(f"QPSK symbol-to-LLR: Call #{self._work_call_count}, no input items")
            return 0
        
        if len(output_items) == 0 or len(output_items[0]) == 0:
            if self._work_call_count <= 5:
                print(f"QPSK symbol-to-LLR: Call #{self._work_call_count}, no output items")
            return 0
        
        input_symbols = input_items[0]
        llrs = output_items[0]
        ninput = len(input_symbols)
        noutput = len(llrs)
        
        # Process each input symbol and produce 2 LLRs
        # Calculate how many symbols we can process based on available input and output space
        nprocess = min(ninput, noutput // self.bits_per_symbol)
        
        # Track totals for rate analysis
        self._total_input_symbols += nprocess
        self._total_output_llrs += (nprocess * self.bits_per_symbol)
        
        # Log first few calls and periodically
        import time
        current_time = time.time()
        elapsed = current_time - self._start_time if hasattr(self, '_start_time') else 1.0
        
        should_log = (self._work_call_count <= 20 or 
                     self._work_call_count % 1000 == 0 or
                     (elapsed > 0 and self._work_call_count % 100 == 0))
        
        if should_log:
            mean_mag = float(np.mean(np.abs(input_symbols[:nprocess]))) if nprocess > 0 else 0.0
            input_rate = self._total_input_symbols / elapsed if elapsed > 0 else 0
            output_rate = self._total_output_llrs / elapsed if elapsed > 0 else 0
            print(f"QPSK symbol-to-LLR: Call #{self._work_call_count}, input={ninput}, process={nprocess}, output_space={noutput}, mean_mag={mean_mag:.6f}, total_in={self._total_input_symbols}, total_out={self._total_output_llrs}, input_rate={input_rate:.1f} sym/s, output_rate={output_rate:.1f} LLR/s")
        
        for i in range(nprocess):
            sym = input_symbols[i]
            output_idx = i * self.bits_per_symbol
            
            if output_idx + self.bits_per_symbol > noutput:
                break
            
            # Extract real and imaginary parts
            real_part = sym.real
            imag_part = sym.imag
            
            # Bit 0 (LSB) LLR: based on real (I) component
            # Real > 0 → bit 0 = 0 → positive LLR
            # Real < 0 → bit 0 = 1 → negative LLR
            # LLR magnitude proportional to |real| (distance from 0)
            bit0_llr = real_part * self.scale_factor
            llrs[output_idx] = bit0_llr
            
            # Bit 1 (MSB) LLR: based on imaginary (Q) component
            # Imag > 0 → bit 1 = 0 → positive LLR
            # Imag < 0 → bit 1 = 1 → negative LLR
            # LLR magnitude proportional to |imag| (distance from 0)
            bit1_llr = imag_part * self.scale_factor
            llrs[output_idx + 1] = bit1_llr
        
        return nprocess
    
    # NOTE: Removed custom forecast() - let GNU Radio handle it automatically
    # For interp_block, GNU Radio automatically calculates forecast based on interp ratio
    # Custom forecast might be causing issues with scheduling


def make_qpsk_symbol_to_llr(scale_factor=2.0):
    """Factory function to create qpsk_symbol_to_llr block"""
    return qpsk_symbol_to_llr(scale_factor)

