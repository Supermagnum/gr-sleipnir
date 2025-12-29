#!/usr/bin/env python3
"""
Custom Tagged Stream to PDU Converter

Converts a tagged stream (uint8) directly to PDUs, handling packet_len tags correctly.
This bypasses the GNU Radio tagged_stream_to_pdu + char_to_short conversion issues.
"""

import numpy as np
from gnuradio import gr
import pmt


class tagged_stream_to_pdu_custom(gr.sync_block):
    """
    Custom tagged stream to PDU converter.
    
    Input: uint8 tagged stream with "packet_len" tags
    Output: PDUs via message port
    
    Reads packet_len tags and creates PDUs for each tagged packet.
    """
    
    def __init__(self, tag_key="packet_len"):
        gr.sync_block.__init__(
            self,
            name="tagged_stream_to_pdu_custom",
            in_sig=[np.uint8],
            out_sig=[np.uint8]  # Dummy stream output to ensure scheduling
        )
        
        self.tag_key = pmt.intern(tag_key)
        
        # Register message output port
        self.message_port_register_out(pmt.intern("pdus"))
        
        self.pdu_count = 0
        
        print(f"Custom tagged_stream_to_pdu: Initialized, looking for tag '{tag_key}'")
    
    def work(self, input_items, output_items):
        """Process tagged stream and create PDUs."""
        in0 = input_items[0]
        
        if len(in0) == 0:
            return 0
        
        # Initialize buffers
        if not hasattr(self, '_call_count'):
            self._call_count = 0
            self._packet_buffer = bytearray()
            self._buffer_start_offset = None  # Absolute offset where buffer starts
            self._processed_tags = set()  # Track processed tag offsets
            print(f"Custom tagged_stream_to_pdu: work() called for first time, received {len(in0)} items")
        self._call_count += 1
        
        # Get current read offset (absolute position in stream)
        read_offset = self.nitems_read(0)
        
        # Initialize buffer start offset on first call
        if self._buffer_start_offset is None:
            self._buffer_start_offset = read_offset
        
        # Add all input to buffer
        self._packet_buffer.extend(in0.tobytes())
        
        # Get tags in the current input buffer AND all buffered data
        # Tags are attached to absolute stream positions
        # CRITICAL: Check tags from the start of buffered data to well beyond current input
        # This ensures we catch tags that were added at positions we haven't consumed yet
        # Tags propagate through streams, so we need to check a wide range
        tag_check_start = self._buffer_start_offset  # Start of buffered data
        # Check well beyond current input to catch tags added at future positions
        # GNU Radio tags propagate with data, so tags added at offset X will be visible
        # when we check positions >= X
        tag_check_end = read_offset + len(in0) + 1000  # Check well beyond current input
        
        # Get tags in the range covering all buffered data and future positions
        tags = self.get_tags_in_range(0, tag_check_start, tag_check_end)
        
        # Filter to only packet_len tags for processing
        packet_len_tags = [t for t in tags if pmt.eq(t.key, self.tag_key)]
        
        # Debug: Log tags found in current buffer
        if self._call_count <= 30:
            all_tag_offsets = sorted(set([t.offset for t in tags]))
            packet_len_tag_offsets = sorted(set([t.offset for t in packet_len_tags]))
            print(f"Custom tagged_stream_to_pdu: Call #{self._call_count}, read_offset={read_offset}, buffer={len(self._packet_buffer)} bytes, checking tags [{tag_check_start}-{tag_check_end}], found {len(tags)} total tags (offsets: {all_tag_offsets[:10]}), {len(packet_len_tags)} packet_len tags (offsets: {packet_len_tag_offsets[:10]})")
            if packet_len_tags:
                for tag in packet_len_tags[:5]:  # Show first 5 packet_len tags
                    tag_key_str = pmt.symbol_to_string(tag.key) if pmt.is_symbol(tag.key) else str(tag.key)
                    tag_val = pmt.to_long(tag.value) if pmt.is_number(tag.value) else str(tag.value)
                    print(f"Custom tagged_stream_to_pdu: Tag - key: '{tag_key_str}', offset: {tag.offset}, value: {tag_val}")
        
        # Process tags to find packet boundaries
        packets_created = 0
        processed_offsets = []
        
        for tag in packet_len_tags:
            if pmt.eq(tag.key, self.tag_key):
                # Found a packet_len tag
                packet_len = pmt.to_long(tag.value)
                tag_abs_offset = tag.offset
                
                # Skip if we've already processed this tag
                if tag_abs_offset in self._processed_tags:
                    continue
                
                # Calculate buffer position: tag_offset - buffer_start_offset
                buffer_pos = tag_abs_offset - self._buffer_start_offset
                
                # Check if we have enough data in buffer
                if buffer_pos < 0:
                    # Tag is before buffer start - shouldn't happen, but skip
                    continue
                
                if buffer_pos + packet_len <= len(self._packet_buffer):
                    # We have enough data in buffer to extract this packet
                    packet_bytes = bytes(self._packet_buffer[buffer_pos:buffer_pos + packet_len])
                    
                    # Verify packet size
                    if len(packet_bytes) != packet_len:
                        print(f"Custom tagged_stream_to_pdu: ERROR - Packet size mismatch: expected {packet_len}, got {len(packet_bytes)}")
                        continue
                    
                    # Create PDU
                    packet_pmt = pmt.init_u8vector(len(packet_bytes), list(packet_bytes))
                    meta = pmt.make_dict()
                    meta = pmt.dict_add(meta, pmt.intern("packet_len"), pmt.from_long(packet_len))
                    pdu = pmt.cons(meta, packet_pmt)
                    
                    # Publish PDU
                    self.message_port_pub(pmt.intern("pdus"), pdu)
                    
                    self.pdu_count += 1
                    packets_created += 1
                    self._processed_tags.add(tag_abs_offset)
                    processed_offsets.append((buffer_pos, packet_len))
                    
                    if self.pdu_count <= 10:
                        print(f"Custom tagged_stream_to_pdu: Created PDU #{self.pdu_count}, packet_len={packet_len} bytes, tag_offset={tag_abs_offset}, buffer_pos={buffer_pos}, data: {list(packet_bytes[:min(8, len(packet_bytes))])}")
                else:
                    # Not enough data yet - will process on next call
                    if self._call_count <= 10:
                        print(f"Custom tagged_stream_to_pdu: Waiting for more data: need {packet_len} bytes at buffer_pos {buffer_pos}, have {len(self._packet_buffer)} bytes")
        
        # Clean up buffer - remove processed packets
        # Find the end of the last processed packet
        if processed_offsets:
            # Sort by buffer position
            processed_offsets.sort()
            # Find the end of the last packet
            last_packet_end = max(buffer_pos + packet_len for buffer_pos, packet_len in processed_offsets)
            
            # Remove processed data from buffer
            if last_packet_end > 0:
                self._packet_buffer = bytearray(self._packet_buffer[last_packet_end:])
                # Update buffer start offset
                self._buffer_start_offset += last_packet_end
                
                if self._call_count <= 10:
                    print(f"Custom tagged_stream_to_pdu: Cleaned buffer, removed {last_packet_end} bytes, remaining buffer={len(self._packet_buffer)} bytes")
        
        # Pass through data as dummy output (1:1 ratio for sync_block)
        output_items[0][:len(in0)] = in0[:len(in0)]
        
        # Consume all input
        return len(in0)


def make_tagged_stream_to_pdu_custom(tag_key="packet_len"):
    """Factory function"""
    return tagged_stream_to_pdu_custom(tag_key)

