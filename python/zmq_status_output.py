#!/usr/bin/env python3
"""
ZMQ Status Output Block

Outputs status messages and audio PDUs via ZMQ for remote consumers.
"""

import numpy as np
from gnuradio import gr
import pmt
import json
from typing import Optional


class zmq_status_output(gr.sync_block):
    """
    ZMQ output block for status messages and audio PDUs.
    
    Inputs:
    - Message Port 'status': Status messages (PMT dict)
    - Message Port 'audio': Audio PDUs (PMT blob)
    
    Outputs:
    - ZMQ PUB socket for status messages (JSON)
    - ZMQ PUB socket for audio data (binary)
    """
    
    def __init__(
        self,
        status_address: str = "tcp://*:5556",
        audio_address: str = "tcp://*:5557"
    ):
        """
        Initialize ZMQ status output.
        
        Args:
            status_address: ZMQ address for status messages
            audio_address: ZMQ address for audio data
        """
        gr.sync_block.__init__(
            self,
            name="zmq_status_output",
            in_sig=None,
            out_sig=None
        )
        
        self.status_address = status_address
        self.audio_address = audio_address
        
        # Initialize ZMQ
        try:
            import zmq
            self.context = zmq.Context()
            
            # Status publisher
            self.status_socket = self.context.socket(zmq.PUB)
            self.status_socket.bind(status_address)
            
            # Audio publisher
            self.audio_socket = self.context.socket(zmq.PUB)
            self.audio_socket.bind(audio_address)
            
            self.zmq_available = True
        except ImportError:
            print("Warning: ZMQ not available")
            self.zmq_available = False
            self.status_socket = None
            self.audio_socket = None
        
        # Message ports
        self.message_port_register_in(pmt.intern("status"))
        self.message_port_register_in(pmt.intern("audio"))
        self.set_msg_handler(pmt.intern("status"), self.handle_status)
        self.set_msg_handler(pmt.intern("audio"), self.handle_audio)
    
    def handle_status(self, msg):
        """Handle status message and publish via ZMQ."""
        if not self.zmq_available or not pmt.is_dict(msg):
            return
        
        try:
            # Convert PMT dict to Python dict
            status_dict = {}
            
            if pmt.dict_has_key(msg, pmt.intern("signature_valid")):
                status_dict['signature_valid'] = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("signature_valid"), pmt.PMT_F)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("encrypted")):
                status_dict['encrypted'] = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("encrypted"), pmt.PMT_F)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("decrypted_successfully")):
                status_dict['decrypted_successfully'] = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("decrypted_successfully"), pmt.PMT_F)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("sender")):
                status_dict['sender'] = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("sender"), pmt.PMT_NIL)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("recipients")):
                status_dict['recipients'] = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("recipients"), pmt.PMT_NIL)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("message_type")):
                status_dict['message_type'] = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("message_type"), pmt.PMT_NIL)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("frame_counter")):
                status_dict['frame_counter'] = pmt.to_long(
                    pmt.dict_ref(msg, pmt.intern("frame_counter"), pmt.PMT_NIL)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("superframe_counter")):
                status_dict['superframe_counter'] = pmt.to_long(
                    pmt.dict_ref(msg, pmt.intern("superframe_counter"), pmt.PMT_NIL)
                )
            
            # Publish as JSON
            status_json = json.dumps(status_dict)
            self.status_socket.send_string(status_json)
            
        except Exception as e:
            print(f"Error handling status message: {e}")
    
    def handle_audio(self, msg):
        """Handle audio PDU and publish via ZMQ."""
        if not self.zmq_available or not pmt.is_pair(msg):
            return
        
        try:
            meta = pmt.car(msg)
            data = pmt.cdr(msg)
            
            if not pmt.is_blob(data):
                return
            
            # Extract audio data
            audio_data = pmt.to_python(data)
            
            # Extract metadata
            metadata = {}
            if pmt.is_dict(meta):
                if pmt.dict_has_key(meta, pmt.intern("sender")):
                    metadata['sender'] = pmt.symbol_to_string(
                        pmt.dict_ref(meta, pmt.intern("sender"), pmt.PMT_NIL)
                    )
                if pmt.dict_has_key(meta, pmt.intern("message_type")):
                    metadata['message_type'] = pmt.symbol_to_string(
                        pmt.dict_ref(meta, pmt.intern("message_type"), pmt.PMT_NIL)
                    )
            
            # Send metadata first (as JSON), then audio data
            import zmq
            metadata_json = json.dumps(metadata)
            self.audio_socket.send_string(metadata_json, zmq.SNDMORE)
            self.audio_socket.send(audio_data)
            
        except Exception as e:
            print(f"Error handling audio message: {e}")
    
    def work(self, input_items, output_items):
        """No stream processing - message-based only."""
        return 0


def make_zmq_status_output(
    status_address: str = "tcp://*:5556",
    audio_address: str = "tcp://*:5557"
):
    """Factory function for GRC."""
    return zmq_status_output(
        status_address=status_address,
        audio_address=audio_address
    )

