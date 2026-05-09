#!/usr/bin/env python3
"""
Debug block to inspect tagged stream and PDU creation.

This block sits between decoder router and parser to debug
what's happening with the tagged stream and PDUs.
"""

import numpy as np
from gnuradio import gr
import pmt


class tagged_stream_debug(gr.sync_block):
    """
    Debug block to inspect tagged stream.
    
    Input: Tagged stream (uint8 or short)
    Output: Same stream (pass-through)
    Also publishes messages when tags are detected.
    """
    
    def __init__(self, tag_key="packet_len"):
        gr.sync_block.__init__(
            self,
            name="tagged_stream_debug",
            in_sig=[np.int16],  # short (after char_to_short)
            out_sig=[np.int16]  # short (pass through)
        )
        
        self.tag_key = pmt.intern(tag_key)
        self.tag_count = 0
        self.total_items = 0
        
        # Message port for debug output
        self.message_port_register_out(pmt.intern("debug"))
        
        print(f"Tagged stream debug: Initialized, looking for tag '{tag_key}'")
    
    def work(self, input_items, output_items):
        """Pass through data and inspect tags."""
        in0 = input_items[0]
        out0 = output_items[0]
        
        n = min(len(in0), len(out0))
        if n == 0:
            return 0
        
        # Log first few calls to verify block is scheduled
        if not hasattr(self, '_call_count'):
            self._call_count = 0
            print(f"Tagged stream debug: work() called for first time, received {n} items")
        self._call_count += 1
        
        if self._call_count <= 10 or self._call_count % 1000 == 0:
            print(f"Tagged stream debug: work() call #{self._call_count}, received {n} items, read_offset={self.nitems_read(0)}, written_offset={self.nitems_written(0)}")
        
        # Pass through data
        out0[:n] = in0[:n]
        
        # Check for tags
        read_offset = self.nitems_read(0)
        tags = self.get_tags_in_window(0, 0, n)
        
        if tags:
            if self.tag_count == 0:
                print(f"Tagged stream debug: Found {len(tags)} tag(s) in this window (read_offset={read_offset})")
            for tag in tags:
                tag_key_str = pmt.symbol_to_string(tag.key) if pmt.is_symbol(tag.key) else str(tag.key)
                if self.tag_count == 0:
                    print(f"Tagged stream debug: Tag key: '{tag_key_str}', looking for '{pmt.symbol_to_string(self.tag_key)}'")
                
                if pmt.eq(tag.key, self.tag_key):
                    self.tag_count += 1
                    tag_value = pmt.to_long(tag.value)
                    tag_pos = tag.offset - read_offset
                    
                    print(f"Tagged stream debug: Found tag #{self.tag_count} at offset {tag.offset} (read_offset={read_offset}, relative: {tag_pos}), value: {tag_value}")
                    
                    # Create debug message
                    debug_msg = pmt.make_dict()
                    debug_msg = pmt.dict_add(debug_msg, pmt.intern("tag_count"), pmt.from_long(self.tag_count))
                    debug_msg = pmt.dict_add(debug_msg, pmt.intern("tag_value"), pmt.from_long(tag_value))
                    debug_msg = pmt.dict_add(debug_msg, pmt.intern("tag_offset"), pmt.from_long(tag.offset))
                    
                    self.message_port_pub(pmt.intern("debug"), debug_msg)
                elif self.tag_count == 0:
                    print(f"Tagged stream debug: Tag key mismatch: got '{tag_key_str}', expected '{pmt.symbol_to_string(self.tag_key)}'")
        
        self.total_items += n
        
        if self.total_items >= 1000 and self.tag_count == 0:
            print(f"Tagged stream debug: Processed {self.total_items} items, found {self.tag_count} tags (read_offset={read_offset})")
            self.total_items = 0  # Reset counter to avoid spam
        
        return n


def make_tagged_stream_debug(tag_key="packet_len"):
    """Factory function"""
    return tagged_stream_debug(tag_key)

