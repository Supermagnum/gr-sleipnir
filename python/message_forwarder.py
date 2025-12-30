#!/usr/bin/env python3
"""
Message Forwarder Block

Simple intermediate block to forward messages from decoder router to parser.
This helps work around message port delivery issues in hier_block2 contexts.
"""

import numpy as np
from gnuradio import gr
import pmt


class message_forwarder(gr.sync_block):
    """
    Forward messages from input port to output port.
    
    This block acts as an intermediate relay to ensure message delivery
    works correctly in hier_block2 contexts.
    
    Input: Messages via message port "in"
    Output: Messages via message port "out"
    Stream: Dummy I/O to keep block scheduled
    """
    
    def __init__(self):
        # Use sync_block with dummy stream I/O to keep scheduler active
        gr.sync_block.__init__(
            self,
            name="message_forwarder",
            in_sig=[np.byte],  # Dummy input
            out_sig=[np.byte]  # Dummy output
        )
        
        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        
        # Set message handler
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        
        # Debug counter
        self._msg_count = 0
        
        print("Message forwarder: Initialized")
    
    def work(self, input_items, output_items):
        """
        Dummy work function - just pass through to keep scheduler happy.
        """
        # Debug: Log first few calls to verify block is scheduled
        if not hasattr(self, '_work_call_count'):
            self._work_call_count = 0
            print(f"Message forwarder: work() called for first time - block is scheduled!")
        self._work_call_count += 1
        
        if self._work_call_count <= 10 or self._work_call_count % 1000 == 0:
            print(f"Message forwarder: work() call #{self._work_call_count}, input={len(input_items[0])}, output={len(output_items[0])}")
        
        n = min(len(input_items[0]), len(output_items[0]))
        if n > 0:
            output_items[0][:n] = input_items[0][:n]
        return n
    
    def handle_msg(self, msg):
        """Forward incoming message to output port."""
        self._msg_count += 1
        
        # Debug: Log first 50 messages to verify message flow (use stderr for visibility)
        import sys
        if self._msg_count <= 50:
            # Extract PDU info for logging
            try:
                if pmt.is_pair(msg):
                    data = pmt.cdr(msg)
                    if pmt.is_u8vector(data):
                        pdu_size = len(pmt.u8vector_elements(data))
                        msg = f"Message forwarder: Received message #{self._msg_count}, {pdu_size} bytes, forwarding to output"
                        print(msg)
                        sys.stderr.write(msg + "\n")
                        sys.stderr.flush()
                    else:
                        msg = f"Message forwarder: Received message #{self._msg_count}, forwarding to output"
                        print(msg)
                        sys.stderr.write(msg + "\n")
                        sys.stderr.flush()
                else:
                    msg = f"Message forwarder: Received message #{self._msg_count}, forwarding to output"
                    print(msg)
                    sys.stderr.write(msg + "\n")
                    sys.stderr.flush()
            except Exception as e:
                msg = f"Message forwarder: Received message #{self._msg_count}, forwarding to output (error logging: {e})"
                print(msg)
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
        
        # Forward message to output port
        self.message_port_pub(pmt.intern("out"), msg)


def make_message_forwarder():
    """Factory function to create message_forwarder block"""
    return message_forwarder()

