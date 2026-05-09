#!/usr/bin/env python3
"""
Simple Debug Probe - Minimal logging to avoid GNU Radio threading issues

Just passes through data and logs basic statistics.
"""

import numpy as np
from gnuradio import gr


class simple_probe_cc(gr.sync_block):
    """Simple complex probe - just logs, no complex operations"""
    
    def __init__(self, name="probe"):
        gr.sync_block.__init__(
            self,
            name=f"simple_probe_cc_{name}",
            in_sig=[np.complex64],
            out_sig=[np.complex64]
        )
        self.name = name
        self.call_count = 0
        
    def work(self, input_items, output_items):
        in0 = input_items[0]
        out0 = output_items[0]
        n = min(len(in0), len(out0))
        
        if n > 0:
            out0[:n] = in0[:n]
            
            self.call_count += 1
            if self.call_count <= 5 or self.call_count % 1000 == 0:
                mag = np.mean(np.abs(in0[:n]))
                print(f"[{self.name}] Call #{self.call_count}: {n} items, mean_mag={mag:.6f}")
        
        return n


class simple_probe_ff(gr.sync_block):
    """Simple float probe - just logs, no complex operations"""
    
    def __init__(self, name="probe"):
        gr.sync_block.__init__(
            self,
            name=f"simple_probe_ff_{name}",
            in_sig=[np.float32],
            out_sig=[np.float32]
        )
        self.name = name
        self.call_count = 0
        
    def work(self, input_items, output_items):
        in0 = input_items[0]
        out0 = output_items[0]
        n = min(len(in0), len(out0))
        
        if n > 0:
            out0[:n] = in0[:n]
            
            self.call_count += 1
            if self.call_count <= 5 or self.call_count % 1000 == 0:
                mean_val = np.mean(in0[:n])
                print(f"[{self.name}] Call #{self.call_count}: {n} items, mean={mean_val:.6f}")
        
        return n


def make_simple_probe_cc(name="probe"):
    return simple_probe_cc(name)


def make_simple_probe_ff(name="probe"):
    return simple_probe_ff(name)

