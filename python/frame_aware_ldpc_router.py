#!/usr/bin/env python3
"""
Frame-aware LDPC router for gr-sleipnir.

Routes frames to appropriate FEC encoder/decoder based on frame number:
- Frame 0: Authentication frame -> auth FEC block
- Frames 1-24: Voice frames -> voice FEC block

This block acts as a router/mux that switches between two FEC paths.
"""

import numpy as np
from gnuradio import gr
import pmt

try:
    from gnuradio import fec
    FEC_AVAILABLE = True
except ImportError:
    FEC_AVAILABLE = False
    print("Warning: GNU Radio FEC module not available")


class frame_aware_ldpc_router(gr.sync_block):
    """
    Routes frames to appropriate FEC encoder/decoder based on frame number.
    
    This is a helper block that tracks frame numbers and emits tags
    to control routing in the hierarchical blocks.
    """
    
    def __init__(self, superframe_size=25):
        gr.sync_block.__init__(
            self,
            name="frame_aware_ldpc_router",
            in_sig=[np.uint8],
            out_sig=[np.uint8]
        )
        
        self.superframe_size = superframe_size
        self.frame_counter = 0
        self.sample_counter = 0
        
    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        
        n_items = min(len(in0), len(out))
        
        # Copy input to output (pass-through for now)
        # The actual routing will be done in the hierarchical block
        out[:n_items] = in0[:n_items]
        
        # Emit frame type tags
        # Frame 0 = auth, others = voice
        if self.sample_counter == 0:
            frame_type = "auth" if self.frame_counter == 0 else "voice"
            tag_key = pmt.intern("frame_type")
            tag_value = pmt.intern(frame_type)
            self.add_item_tag(0, self.nitems_written(0), tag_key, tag_value)
        
        self.sample_counter += n_items
        # Update frame counter based on expected frame sizes
        # This is approximate - actual frame detection happens in superframe parser
        self.frame_counter = (self.frame_counter + 1) % self.superframe_size
        
        return n_items

