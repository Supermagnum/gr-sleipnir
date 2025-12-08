#!/usr/bin/env python3
"""
ZMQ Control Helper for gr-sleipnir TX

Provides helper functions for sending control messages via ZMQ.
"""

import zmq
import json
import pmt
from typing import Optional, List, Dict


class SleipnirControlClient:
    """
    Client for sending control messages to sleipnir TX block via ZMQ.
    """
    
    def __init__(self, zmq_address: str = "tcp://localhost:5555"):
        """
        Initialize ZMQ control client.
        
        Args:
            zmq_address: ZMQ address (e.g., "tcp://localhost:5555")
        """
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect(zmq_address)
    
    def send_control(
        self,
        enable_signing: Optional[bool] = None,
        enable_encryption: Optional[bool] = None,
        key_source: Optional[str] = None,
        recipient: Optional[str] = None,
        message_type: Optional[str] = None,
        payload: Optional[bytes] = None,
        from_callsign: Optional[str] = None,
        to_callsign: Optional[str] = None,
        mac_key: Optional[bytes] = None
    ):
        """
        Send control message to TX block.
        
        Args:
            enable_signing: Enable ECDSA signing
            enable_encryption: Enable encryption
            key_source: Path to private key file
            recipient: Recipient callsign(s), comma-separated
            message_type: Message type ('voice', 'text', etc.)
            payload: Optional payload bytes
            from_callsign: Source callsign
            to_callsign: Destination callsign
            mac_key: MAC key (32 bytes)
        """
        msg_dict = {}
        
        if enable_signing is not None:
            msg_dict['enable_signing'] = enable_signing
        if enable_encryption is not None:
            msg_dict['enable_encryption'] = enable_encryption
        if key_source:
            msg_dict['key_source'] = key_source
        if recipient:
            msg_dict['recipient'] = recipient
        if message_type:
            msg_dict['message_type'] = message_type
        if payload:
            msg_dict['payload'] = payload.hex()  # Convert to hex string
        if from_callsign:
            msg_dict['from_callsign'] = from_callsign
        if to_callsign:
            msg_dict['to_callsign'] = to_callsign
        if mac_key:
            msg_dict['mac_key'] = mac_key.hex()
        
        # Send as JSON
        msg_json = json.dumps(msg_dict)
        self.socket.send_string(msg_json)
    
    def close(self):
        """Close ZMQ connection."""
        self.socket.close()
        self.context.term()


def create_control_pmt(
    enable_signing: Optional[bool] = None,
    enable_encryption: Optional[bool] = None,
    key_source: Optional[str] = None,
    recipient: Optional[str] = None,
    message_type: Optional[str] = None,
    payload: Optional[bytes] = None,
    from_callsign: Optional[str] = None,
    to_callsign: Optional[str] = None,
    mac_key: Optional[bytes] = None
):
    """
    Create PMT dict for control message.
    
    Returns PMT dict suitable for message port.
    """
    msg_dict = pmt.make_dict()
    
    if enable_signing is not None:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("enable_signing"), 
                                pmt.from_bool(enable_signing))
    if enable_encryption is not None:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("enable_encryption"),
                                pmt.from_bool(enable_encryption))
    if key_source:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("key_source"),
                                pmt.intern(key_source))
    if recipient:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("recipient"),
                                pmt.intern(recipient))
    if message_type:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("message_type"),
                                pmt.intern(message_type))
    if payload:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("payload"),
                                pmt.to_pmt(payload))
    if from_callsign:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("from_callsign"),
                                pmt.intern(from_callsign))
    if to_callsign:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("to_callsign"),
                                pmt.intern(to_callsign))
    if mac_key:
        msg_dict = pmt.dict_add(msg_dict, pmt.intern("mac_key"),
                                pmt.to_pmt(mac_key))
    
    return msg_dict

