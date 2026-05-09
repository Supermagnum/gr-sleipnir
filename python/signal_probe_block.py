#!/usr/bin/env python3
"""
Signal Probe Block for Debugging

Probes signal at various stages to check signal levels, DC offset, and data flow.
"""

import numpy as np
from gnuradio import gr
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class signal_probe_cc(gr.sync_block):
    """
    Probe complex signal to check signal levels and statistics.
    
    Input: complex64 signal
    Output: Same signal (pass-through)
    Logs: Signal statistics (power, DC offset, etc.)
    """
    
    def __init__(self, name="signal_probe", log_interval=1000):
        """
        Initialize signal probe block.
        
        Args:
            name: Name for logging
            log_interval: Log every N calls (0 = only first few calls)
        """
        gr.sync_block.__init__(
            self,
            name=f"signal_probe_{name}",
            in_sig=[np.complex64],
            out_sig=[np.complex64]
        )
        
        self.name = name
        self.log_interval = log_interval
        self.call_count = 0
        self.total_samples = 0
        self.total_power = 0.0
        
        print(f"Signal probe '{name}': Initialized")
    
    def work(self, input_items, output_items):
        """Pass through signal and log statistics."""
        in0 = input_items[0]
        out0 = output_items[0]
        
        n = min(len(in0), len(out0))
        if n == 0:
            return 0
        
        # Pass through data
        out0[:n] = in0[:n]
        
        # Calculate statistics
        power = np.mean(np.abs(in0)**2)
        dc_offset_real = np.mean(in0.real)
        dc_offset_imag = np.mean(in0.imag)
        magnitude_mean = np.mean(np.abs(in0))
        magnitude_max = np.max(np.abs(in0))
        
        self.call_count += 1
        self.total_samples += n
        self.total_power += power * n
        
        # Log first 5 calls, then periodically
        should_log = (self.call_count <= 5) or (self.log_interval > 0 and self.call_count % self.log_interval == 0)
        
        if should_log:
            avg_power = self.total_power / self.total_samples if self.total_samples > 0 else 0.0
            msg = (f"Probe '{self.name}': Call #{self.call_count}, samples={n}, "
                   f"power={power:.6f}, avg_power={avg_power:.6f}, "
                   f"DC_offset=({dc_offset_real:.6f}+{dc_offset_imag:.6f}j), "
                   f"mag_mean={magnitude_mean:.6f}, mag_max={magnitude_max:.6f}")
            print(msg)
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        
        return n


class signal_probe_ff(gr.sync_block):
    """
    Probe float signal to check signal levels and statistics.
    
    Input: float32 signal (LLRs)
    Output: Same signal (pass-through)
    Logs: Signal statistics (mean, std, range, etc.)
    """
    
    def __init__(self, name="signal_probe", log_interval=1000):
        """
        Initialize signal probe block.
        
        Args:
            name: Name for logging
            log_interval: Log every N calls (0 = only first few calls)
        """
        gr.sync_block.__init__(
            self,
            name=f"signal_probe_{name}",
            in_sig=[np.float32],
            out_sig=[np.float32]
        )
        
        self.name = name
        self.log_interval = log_interval
        self.call_count = 0
        self.total_samples = 0
        self.total_mean = 0.0
        
        print(f"Signal probe '{name}': Initialized (float32)")
    
    def work(self, input_items, output_items):
        """Pass through signal and log statistics."""
        in0 = input_items[0]
        out0 = output_items[0]
        
        n = min(len(in0), len(out0))
        if n == 0:
            return 0
        
        # Pass through data
        out0[:n] = in0[:n]
        
        # Calculate statistics
        mean_val = np.mean(in0)
        std_val = np.std(in0)
        min_val = np.min(in0)
        max_val = np.max(in0)
        non_zero_count = np.count_nonzero(in0)
        
        self.call_count += 1
        self.total_samples += n
        self.total_mean += mean_val * n
        
        # Log first 5 calls, then periodically
        should_log = (self.call_count <= 5) or (self.log_interval > 0 and self.call_count % self.log_interval == 0)
        
        if should_log:
            avg_mean = self.total_mean / self.total_samples if self.total_samples > 0 else 0.0
            msg = (f"Probe '{self.name}': Call #{self.call_count}, samples={n}, "
                   f"mean={mean_val:.6f}, std={std_val:.6f}, "
                   f"range=[{min_val:.6f}, {max_val:.6f}], "
                   f"non_zero={non_zero_count}/{n}, avg_mean={avg_mean:.6f}")
            print(msg)
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        
        return n


def make_signal_probe_cc(name="signal_probe", log_interval=1000):
    """Factory function to create complex signal probe block"""
    return signal_probe_cc(name=name, log_interval=log_interval)


def make_signal_probe_ff(name="signal_probe", log_interval=1000):
    """Factory function to create float signal probe block"""
    return signal_probe_ff(name=name, log_interval=log_interval)

