#!/usr/bin/env python3
"""
Frame-aware LDPC decoder to PDU converter.

Handles variable frame sizes:
- Frame 0 (auth): 64 bytes after decoding
- Frames 1-24 (voice): 48 bytes after decoding

This block buffers decoder output and produces PDUs with correct frame sizes
based on frame position in the superframe.
"""

import numpy as np
from gnuradio import gr
import pmt
from array import array


class frame_aware_ldpc_decoder_to_pdu(gr.sync_block):
    """
    Frame-aware LDPC decoder to PDU converter.
    
    Buffers decoder output and produces PDUs with correct frame sizes:
    - Frame 0: 64 bytes (auth frame)
    - Frames 1-24: 48 bytes (voice frames)
    """
    
    def __init__(self, superframe_size=25):
        gr.sync_block.__init__(
            self,
            name="frame_aware_ldpc_decoder_to_pdu",
            in_sig=[np.uint8],
            out_sig=None
        )
        
        self.superframe_size = superframe_size
        self.frame_counter = 0
        self.buffer = bytearray()
        
        # Message port for PDUs
        self.message_port_register_out(pmt.intern("pdus"))
        
        # Store reference to prevent garbage collection
        if not hasattr(type(self), '_instances'):
            type(self)._instances = []
        type(self)._instances.append(self)
    
    def work(self, input_items, output_items):
        """
        Process decoder output and produce PDUs when frames are complete.
        """
        in0 = input_items[0]
        
        if len(in0) == 0:
            return 0
        
        # Add new data to buffer
        self.buffer.extend(in0.tobytes())
        
        # Process complete frames
        frames_produced = 0
        while True:
            # Determine frame size based on frame counter
            if self.frame_counter == 0:
                # Auth frame: 64 bytes
                frame_size_bytes = 64
            else:
                # Voice frame: 48 bytes
                frame_size_bytes = 48
            
            # Check if we have enough data for a complete frame
            if len(self.buffer) < frame_size_bytes:
                break
            
            # Extract frame
            frame_data = bytes(self.buffer[:frame_size_bytes])
            self.buffer = self.buffer[frame_size_bytes:]
            
            # Create PDU
            frame_pmt = pmt.init_u8vector(len(frame_data), list(frame_data))
            meta = pmt.make_dict()
            meta = pmt.dict_add(meta, pmt.intern("frame_size"), 
                               pmt.from_long(frame_size_bytes))
            meta = pmt.dict_add(meta, pmt.intern("frame_num"), 
                               pmt.from_long(self.frame_counter))
            
            # Output PDU
            self.message_port_pub(pmt.intern("pdus"), pmt.cons(meta, frame_pmt))
            frames_produced += 1
            
            # Update frame counter
            self.frame_counter = (self.frame_counter + 1) % self.superframe_size
        
        # Consume all input
        return len(in0)
    
    def __del__(self):
        """Cleanup method"""
        # Clear buffer to free memory
        try:
            self.buffer = bytearray()
        except:
            pass
        
        if hasattr(type(self), '_instances'):
            try:
                type(self)._instances.remove(self)
            except (ValueError, AttributeError):
                pass


def make_frame_aware_ldpc_decoder_to_pdu(superframe_size=25):
    """Factory function to create frame_aware_ldpc_decoder_to_pdu block"""
    return frame_aware_ldpc_decoder_to_pdu(superframe_size=superframe_size)

