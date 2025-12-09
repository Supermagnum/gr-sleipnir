#!/usr/bin/env python3
"""
Frame Splitter and Router for gr-sleipnir.

Splits concatenated superframe into individual frames and routes them
to appropriate FEC encoders/decoders based on frame position:
- Frame 0: 32 bytes -> auth FEC encoder
- Frames 1-24: 48 bytes -> voice FEC encoder

This block works with PDUs and emits separate PDUs for each frame type.
"""

import numpy as np
from gnuradio import gr
import pmt


class frame_splitter_router(gr.sync_block):
    """
    Splits superframe into individual frames and routes to appropriate paths.
    
    Input: PDU with concatenated frame payloads
    Output: Two message ports:
    - "auth_out": PDUs for auth frames (32 bytes)
    - "voice_out": PDUs for voice frames (48 bytes)
    """
    
    def __init__(self, enable_signing=True):
        gr.sync_block.__init__(
            self,
            name="frame_splitter_router",
            in_sig=None,
            out_sig=None
        )
        
        self.enable_signing = enable_signing
        self.frame_counter = 0
        
        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        self.message_port_register_out(pmt.intern("auth_out"))
        self.message_port_register_out(pmt.intern("voice_out"))
        
    def handle_msg(self, msg):
        """Handle incoming PDU with concatenated frame payloads."""
        if not pmt.is_pair(msg):
            return
        
        meta = pmt.car(msg)
        data = pmt.cdr(msg)
        
        if not pmt.is_blob(data):
            print("Warning: Expected blob data")
            return
        
        # Extract frame data
        frame_data = pmt.to_python(data)
        
        # Split into individual frames
        offset = 0
        frame_num = 0
        
        # Frame 0: Auth frame (32 bytes) if signing enabled
        if self.enable_signing and offset + 32 <= len(frame_data):
            auth_frame = frame_data[offset:offset+32]
            offset += 32
            
            # Emit auth frame PDU
            auth_pmt = pmt.init_u8vector(len(auth_frame), list(auth_frame))
            auth_meta = pmt.make_dict()
            if pmt.is_dict(meta):
                keys = pmt.dict_keys(meta)
                for i in range(pmt.length(keys)):
                    key = pmt.nth(i, keys)
                    value = pmt.dict_ref(meta, key, pmt.PMT_NIL)
                    auth_meta = pmt.dict_add(auth_meta, key, value)
            auth_meta = pmt.dict_add(auth_meta, pmt.intern("frame_type"), pmt.intern("auth"))
            auth_meta = pmt.dict_add(auth_meta, pmt.intern("frame_num"), pmt.from_long(0))
            
            self.message_port_pub(pmt.intern("auth_out"), pmt.cons(auth_meta, auth_pmt))
            frame_num += 1
        
        # Frames 1-24: Voice frames (48 bytes each)
        while offset + 48 <= len(frame_data):
            voice_frame = frame_data[offset:offset+48]
            offset += 48
            
            # Emit voice frame PDU
            voice_pmt = pmt.init_u8vector(len(voice_frame), list(voice_frame))
            voice_meta = pmt.make_dict()
            if pmt.is_dict(meta):
                keys = pmt.dict_keys(meta)
                for i in range(pmt.length(keys)):
                    key = pmt.nth(i, keys)
                    value = pmt.dict_ref(meta, key, pmt.PMT_NIL)
                    voice_meta = pmt.dict_add(voice_meta, key, value)
            voice_meta = pmt.dict_add(voice_meta, pmt.intern("frame_type"), pmt.intern("voice"))
            voice_meta = pmt.dict_add(voice_meta, pmt.intern("frame_num"), pmt.from_long(frame_num))
            
            self.message_port_pub(pmt.intern("voice_out"), pmt.cons(voice_meta, voice_pmt))
            frame_num += 1


def make_frame_splitter_router(enable_signing=True):
    """Factory function for GRC."""
    return frame_splitter_router(enable_signing=enable_signing)

