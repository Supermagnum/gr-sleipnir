#!/usr/bin/env python3
"""
LDPC Decoder to PDU Block

Converts LDPC decoder output stream to PDUs without requiring tags.
Buffers decoder output and produces PDUs when enough data is accumulated.
"""

import numpy as np
from gnuradio import gr
import pmt
import array


class ldpc_decoder_to_pdu(gr.sync_block):
    """
    Convert LDPC decoder output stream to PDUs.
    
    Buffers decoder output and produces PDUs when enough data is accumulated.
    This avoids the "Missing length tag" error that occurs when stream_to_tagged_stream
    doesn't receive enough data to form packets.
    
    Input: uint8 stream from LDPC decoder
    Output: PDU messages with decoded frames
    """
    
    def __init__(self, frame_size_bytes=48):
        """
        Initialize LDPC decoder to PDU block.
        
        Args:
            frame_size_bytes: Size of each frame in bytes (default: 48 for voice frames)
        """
        gr.sync_block.__init__(
            self,
            name="ldpc_decoder_to_pdu",
            in_sig=[np.uint8],
            out_sig=None  # Message-only block
        )
        
        self.frame_size_bytes = frame_size_bytes
        self.buffer = bytearray()
        
        # Register message output port
        self.message_port_register_out(pmt.intern("pdus"))
        
        # Store reference to self to prevent garbage collection
        self._self_ref = self
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
        while len(self.buffer) >= self.frame_size_bytes:
            # Extract frame
            frame_data = bytes(self.buffer[:self.frame_size_bytes])
            self.buffer = self.buffer[self.frame_size_bytes:]
            
            # Create PDU
            frame_pmt = pmt.init_u8vector(len(frame_data), array.array('B', frame_data))
            meta = pmt.make_dict()
            meta = pmt.dict_add(meta, pmt.intern("frame_size"), 
                               pmt.from_long(self.frame_size_bytes))
            
            # Output PDU
            self.message_port_pub(pmt.intern("pdus"), pmt.cons(meta, frame_pmt))
            frames_produced += 1
        
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


def make_ldpc_decoder_to_pdu(frame_size_bytes=48):
    """Factory function to create ldpc_decoder_to_pdu block"""
    return ldpc_decoder_to_pdu(frame_size_bytes=frame_size_bytes)

