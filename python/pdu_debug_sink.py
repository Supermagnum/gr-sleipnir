#!/usr/bin/env python3
"""
PDU Debug Sink

Receives PDUs and logs them to verify tagged_stream_to_pdu is working.
"""

from gnuradio import gr
import pmt


class pdu_debug_sink(gr.sync_block):
    """
    Debug sink to receive and log PDUs.
    
    This block receives PDUs via message port and logs them
    to verify that tagged_stream_to_pdu is creating PDUs.
    """
    
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="pdu_debug_sink",
            in_sig=[],  # No stream input
            out_sig=[]  # No stream output
        )
        
        # Register input message port
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        
        self.pdu_count = 0
        
        print("PDU debug sink: Initialized")
    
    def work(self, input_items, output_items):
        """Dummy work - this block is message-only"""
        return 0
    
    def handle_msg(self, msg):
        """Handle received PDU"""
        self.pdu_count += 1
        
        debug_name = getattr(self, '_debug_name', 'PDU DEBUG SINK')
        print(f"★★★ {debug_name}: Received PDU #{self.pdu_count} ★★★")
        
        if pmt.is_pair(msg):
            meta = pmt.car(msg)
            data = pmt.cdr(msg)
            
            print(f"PDU debug sink: PDU is a pair (meta + data)")
            
            if pmt.is_dict(meta):
                print(f"PDU debug sink: Metadata is a dict")
                if pmt.dict_has_key(meta, pmt.intern("packet_len")):
                    packet_len = pmt.to_long(pmt.dict_ref(meta, pmt.intern("packet_len"), pmt.PMT_NIL))
                    print(f"PDU debug sink: packet_len: {packet_len}")
            
            if pmt.is_u8vector(data):
                data_bytes = pmt.u8vector_elements(data)
                print(f"PDU debug sink: Data is u8vector with {len(data_bytes)} bytes")
                print(f"PDU debug sink: First 16 bytes: {list(data_bytes[:min(16, len(data_bytes))])}")
        else:
            print(f"PDU debug sink: Message is not a pair: {type(msg)}")


def make_pdu_debug_sink():
    """Factory function"""
    return pdu_debug_sink()

