#!/usr/bin/env python3
"""
Superframe Assembler Block

Assembles superframes from Opus-encoded audio frames.
Handles encryption, signing, and metadata insertion.

Input: PDU with Opus frames (list of 40-byte frames)
Output: PDU with superframe payloads (list of frame payloads)
"""

import numpy as np
from gnuradio import gr
import pmt
from typing import List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.crypto_helpers import (
    load_private_key,
    generate_ecdsa_signature,
    compute_chacha20_mac,
    get_callsign_bytes
)
from python.voice_frame_builder import VoiceFrameBuilder


class sleipnir_superframe_assembler(gr.sync_block):
    """
    Assembles superframes from Opus frames.
    
    Input: PDU with list of 24 Opus frames (40 bytes each)
    Output: PDU with list of frame payloads ready for LDPC encoding
    """
    
    def __init__(
        self,
        callsign: str = "N0CALL",
        enable_signing: bool = False,
        enable_encryption: bool = False,
        private_key_path: Optional[str] = None,
        mac_key: Optional[bytes] = None
    ):
        gr.sync_block.__init__(
            self,
            name="sleipnir_superframe_assembler",
            in_sig=None,
            out_sig=None
        )
        
        self.callsign = callsign
        self.enable_signing = enable_signing
        self.enable_encryption = enable_encryption
        
        # Load private key if provided
        self.private_key = None
        if private_key_path:
            self.private_key = load_private_key(private_key_path)
            if self.private_key:
                self.enable_signing = True
        
        self.mac_key = mac_key
        
        # Voice frame builder
        self.frame_builder = VoiceFrameBuilder(
            callsign=callsign,
            mac_key=mac_key,
            enable_mac=(mac_key is not None)
        )
        
        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        
        # Control port for configuration
        self.message_port_register_in(pmt.intern("ctrl"))
        self.set_msg_handler(pmt.intern("ctrl"), self.handle_control)
    
    def handle_control(self, msg):
        """Handle control messages to update configuration."""
        if not pmt.is_dict(msg):
            return
        
        try:
            if pmt.dict_has_key(msg, pmt.intern("enable_signing")):
                self.enable_signing = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("enable_signing"), pmt.PMT_F)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("mac_key")):
                mac_key_pmt = pmt.dict_ref(msg, pmt.intern("mac_key"), pmt.PMT_NIL)
                if pmt.is_blob(mac_key_pmt):
                    self.mac_key = pmt.to_python(mac_key_pmt)
                    self.frame_builder.mac_key = self.mac_key
                    self.frame_builder.enable_mac = True
            
            if pmt.dict_has_key(msg, pmt.intern("callsign")):
                self.callsign = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("callsign"), pmt.PMT_NIL)
                )
                self.frame_builder.callsign = self.callsign
                
        except Exception as e:
            print(f"Error handling control message: {e}")
    
    def handle_msg(self, msg):
        """Handle incoming PDU with Opus frames."""
        if not pmt.is_pair(msg):
            return
        
        meta = pmt.car(msg)
        data = pmt.cdr(msg)
        
        if not pmt.is_blob(data):
            print("Warning: Expected blob data")
            return
        
        # Extract Opus frames from blob
        opus_data = pmt.to_python(data)
        
        # Expect 24 frames of 40 bytes each = 960 bytes
        expected_size = 24 * 40
        if len(opus_data) != expected_size:
            print(f"Warning: Expected {expected_size} bytes, got {len(opus_data)}")
            # Pad or truncate
            if len(opus_data) < expected_size:
                opus_data = opus_data.ljust(expected_size, b'\x00')
            else:
                opus_data = opus_data[:expected_size]
        
        # Split into 24 frames
        opus_frames = [opus_data[i:i+40] for i in range(0, len(opus_data), 40)]
        
        # Assemble superframe
        try:
            frame_payloads = self.assemble_superframe(opus_frames)
            
            # Convert to PMT
            payload_bytes = b''.join(frame_payloads)
            output_pmt = pmt.init_u8vector(len(payload_bytes), list(payload_bytes))
            
            # Output
            self.message_port_pub(pmt.intern("out"), pmt.cons(meta, output_pmt))
            
        except Exception as e:
            print(f"Error assembling superframe: {e}")
    
    def assemble_superframe(self, opus_frames: List[bytes]) -> List[bytes]:
        """
        Assemble superframe from 24 Opus frames.
        
        Returns list of frame payloads:
        - Frame 0 (if signing enabled): 32 bytes auth payload
        - Frames 1-24: 48 bytes voice payloads
        """
        if len(opus_frames) != 24:
            raise ValueError(f"Expected 24 Opus frames, got {len(opus_frames)}")
        
        frames = []
        
        # Build superframe data for signing
        superframe_data = b''.join(opus_frames)
        
        # Frame 0: Authentication frame (if signing enabled)
        if self.enable_signing and self.private_key:
            auth_payload = self.build_auth_frame(superframe_data)
            frames.append(auth_payload)
        
        # Frames 1-24: Voice frames
        for i, opus_frame in enumerate(opus_frames, start=1):
            voice_payload = self.build_voice_frame(opus_frame, i)
            frames.append(voice_payload)
        
        return frames
    
    def build_auth_frame(self, superframe_data: bytes) -> bytes:
        """Build authentication frame payload (32 bytes)."""
        try:
            signature = generate_ecdsa_signature(superframe_data, self.private_key)
            # Pad/truncate to 32 bytes
            if len(signature) > 32:
                signature = signature[:32]
            elif len(signature) < 32:
                signature = signature.ljust(32, b'\x00')
            return signature
        except Exception as e:
            print(f"Error building auth frame: {e}")
            return b'\x00' * 32
    
    def build_voice_frame(self, opus_data: bytes, frame_num: int) -> bytes:
        """Build voice frame payload (48 bytes)."""
        return self.frame_builder.build_frame(opus_data, frame_num)


def make_sleipnir_superframe_assembler(
    callsign: str = "N0CALL",
    enable_signing: bool = False,
    enable_encryption: bool = False,
    private_key_path: Optional[str] = None,
    mac_key: Optional[bytes] = None
):
    """Factory function for GRC."""
    return sleipnir_superframe_assembler(
        callsign=callsign,
        enable_signing=enable_signing,
        enable_encryption=enable_encryption,
        private_key_path=private_key_path,
        mac_key=mac_key
    )

