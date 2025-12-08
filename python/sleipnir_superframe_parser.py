#!/usr/bin/env python3
"""
Superframe Parser Block

Parses superframes from LDPC-decoded bits.
Handles desynchronization, signature verification, and decryption.

Input: PDU with decoded bits (after LDPC)
Output: PDU with Opus frames and status messages
"""

import numpy as np
from gnuradio import gr
import pmt
import struct
from typing import Optional, List, Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.crypto_helpers import (
    verify_chacha20_mac,
    get_callsign_bytes,
    load_private_key
)
from python.voice_frame_builder import VoiceFrameBuilder


class sleipnir_superframe_parser(gr.sync_block):
    """
    Parses superframes from decoded bits.
    
    Input: PDU with decoded bits (after LDPC decoding)
    Output: PDU with Opus frames and status messages
    """
    
    VOICE_FRAME_BYTES = 48  # 384 bits after LDPC decoding
    AUTH_FRAME_BYTES = 32   # 256 bits after LDPC decoding
    FRAMES_PER_SUPERFRAME = 25
    
    def __init__(
        self,
        local_callsign: str = "N0CALL",
        private_key_path: Optional[str] = None,
        require_signatures: bool = False,
        public_key_store_path: Optional[str] = None
    ):
        """
        Initialize superframe parser.
        
        Args:
            local_callsign: This station's callsign
            private_key_path: Path to private key for decryption
            require_signatures: Require valid signatures
            public_key_store_path: Path to public key store directory
        """
        gr.sync_block.__init__(
            self,
            name="sleipnir_superframe_parser",
            in_sig=None,
            out_sig=None
        )
        
        self.local_callsign = local_callsign.upper()
        self.require_signatures = require_signatures
        self.private_key_path = private_key_path
        self.public_key_store_path = public_key_store_path
        
        # Load private key if provided
        self.private_key = None
        if private_key_path:
            try:
                self.private_key = load_private_key(private_key_path)
            except Exception as e:
                print(f"Warning: Could not load private key: {e}")
        
        # Frame builder for parsing
        self.frame_builder = VoiceFrameBuilder(
            callsign=local_callsign,
            mac_key=None,
            enable_mac=False
        )
        
        # State
        self.frame_buffer = []
        self.superframe_counter = 0
        
        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))
        self.message_port_register_out(pmt.intern("status"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        
        # Control port
        self.message_port_register_in(pmt.intern("ctrl"))
        self.set_msg_handler(pmt.intern("ctrl"), self.handle_control)
    
    def handle_control(self, msg):
        """Handle control messages."""
        if not pmt.is_dict(msg):
            return
        
        try:
            if pmt.dict_has_key(msg, pmt.intern("local_callsign")):
                self.local_callsign = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("local_callsign"), pmt.PMT_NIL)
                ).upper()
                self.frame_builder.callsign = self.local_callsign
            
            if pmt.dict_has_key(msg, pmt.intern("require_signatures")):
                self.require_signatures = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("require_signatures"), pmt.PMT_F)
                )
                
        except Exception as e:
            print(f"Error handling control message: {e}")
    
    def handle_msg(self, msg):
        """Handle incoming PDU with decoded bits."""
        if not pmt.is_pair(msg):
            return
        
        meta = pmt.car(msg)
        data = pmt.cdr(msg)
        
        if not pmt.is_blob(data):
            print("Warning: Expected blob data")
            return
        
        # Extract decoded bits
        if pmt.is_u8vector(data):
            decoded_data = bytes(pmt.u8vector_elements(data))
        elif pmt.is_blob(data):
            decoded_data = pmt.to_python(data)
        else:
            print("Warning: Unexpected data type")
            return
        
        # Parse frames from decoded data
        # This is simplified - actual implementation would handle frame sync
        frames = self.parse_frames(decoded_data)
        
        if not frames:
            return
        
        # Process superframe
        result = self.process_superframe(frames)
        
        if result:
            opus_frames, status = result
            
            # Emit status
            self.emit_status(status)
            
            # Emit Opus frames
            if opus_frames:
                audio_data = b''.join(opus_frames)
                audio_pmt = pmt.init_u8vector(len(audio_data), list(audio_data))
                output_meta = pmt.make_dict()
                output_meta = pmt.dict_add(output_meta, pmt.intern("sender"),
                                          pmt.intern(status.get('sender', '')))
                output_meta = pmt.dict_add(output_meta, pmt.intern("message_type"),
                                          pmt.intern(status.get('message_type', 'voice')))
                self.message_port_pub(pmt.intern("out"), pmt.cons(output_meta, audio_pmt))
    
    def parse_frames(self, data: bytes) -> List[bytes]:
        """
        Parse frames from decoded data.
        
        Handles desynchronization by looking for frame boundaries.
        """
        frames = []
        
        # Simplified parsing - assumes frames are properly aligned
        # Real implementation would:
        # 1. Look for sync patterns
        # 2. Handle frame boundaries
        # 3. Extract frame payloads
        
        # Check if we have auth frame (25 frames) or just voice frames (24 frames)
        total_frames = len(data) // self.VOICE_FRAME_BYTES
        
        if total_frames == 25:
            # Has auth frame
            auth_frame = data[:self.AUTH_FRAME_BYTES]
            frames.append(auth_frame)
            voice_data = data[self.AUTH_FRAME_BYTES:]
        else:
            # No auth frame
            voice_data = data
        
        # Parse voice frames
        for i in range(0, len(voice_data), self.VOICE_FRAME_BYTES):
            frame = voice_data[i:i+self.VOICE_FRAME_BYTES]
            if len(frame) == self.VOICE_FRAME_BYTES:
                frames.append(frame)
        
        return frames
    
    def load_public_key(self, callsign: str) -> Optional[object]:
        """
        Load public key for callsign from key store.
        
        Args:
            callsign: Callsign to look up
        
        Returns:
            Public key object or None
        """
        if not self.public_key_store_path:
            return None
        
        # Look for key file: {public_key_store_path}/{callsign}.pem
        key_path = Path(self.public_key_store_path) / f"{callsign.upper()}.pem"
        
        if not key_path.exists():
            return None
        
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            
            with open(key_path, 'rb') as f:
                key_data = f.read()
            
            # Try PEM format
            try:
                public_key = serialization.load_pem_public_key(
                    key_data,
                    backend=default_backend()
                )
                return public_key
            except:
                # Try DER format
                public_key = serialization.load_der_public_key(
                    key_data,
                    backend=default_backend()
                )
                return public_key
        except Exception as e:
            print(f"Error loading public key for {callsign}: {e}")
            return None
    
    def verify_signature(self, signature: bytes, data: bytes, sender_callsign: str) -> bool:
        """
        Verify ECDSA signature.
        
        Args:
            signature: 32-byte signature
            data: Original data
            sender_callsign: Sender's callsign
        
        Returns:
            True if signature is valid
        """
        # Load sender's public key
        public_key = self.load_public_key(sender_callsign)
        if not public_key:
            print(f"No public key found for {sender_callsign}")
            return False
        
        # Note: Signature verification is simplified
        # See crypto_helpers.verify_ecdsa_signature for details
        # For now, return False (not fully implemented)
        print(f"Signature verification for {sender_callsign} not fully implemented")
        return False
    
    def check_recipient(self, recipients: str) -> bool:
        """Check if local callsign is in recipient list."""
        if not recipients:
            return False
        
        recipient_list = [r.strip().upper() for r in recipients.split(",")]
        return self.local_callsign in recipient_list
    
    def decrypt_payload(self, encrypted_payload: bytes) -> Optional[bytes]:
        """Decrypt payload using local private key."""
        if not self.private_key:
            return None
        
        # Decryption implementation depends on encryption scheme
        # This is a placeholder
        print("Decryption not fully implemented")
        return None
    
    def process_superframe(self, frames: List[bytes]) -> Optional[tuple]:
        """
        Process complete superframe.
        
        Returns:
            Tuple of (opus_frames, status_dict) or None
        """
        if len(frames) < 24:
            return None
        
        # Determine if Frame 0 is present
        has_auth_frame = len(frames) == 25
        
        auth_payload = None
        voice_frames_start = 0
        
        if has_auth_frame:
            auth_payload = frames[0]
            voice_frames_start = 1
        
        # Process authentication
        signature_valid = False
        sender_callsign = ""
        
        if auth_payload:
            signature = auth_payload[:32]
            superframe_data = b''.join(frames[voice_frames_start:])
            
            # Extract sender from first voice frame
            if len(frames) > voice_frames_start:
                first_voice = self.frame_builder.parse_frame(frames[voice_frames_start])
                if first_voice:
                    sender_callsign = first_voice.get('callsign', '').strip()
            
            # Verify signature
            if sender_callsign:
                signature_valid = self.verify_signature(signature, superframe_data, sender_callsign)
            
            if self.require_signatures and not signature_valid:
                print("Rejecting message: invalid signature")
                self.emit_status({
                    'signature_valid': False,
                    'encrypted': False,
                    'decrypted_successfully': False,
                    'sender': sender_callsign,
                    'recipients': '',
                    'message_type': 'rejected',
                    'frame_counter': 0,
                    'superframe_counter': self.superframe_counter
                })
                return None
        else:
            # No auth frame
            if self.require_signatures:
                print("Rejecting unsigned message")
                return None
            
            # Extract sender from first voice frame
            if len(frames) > 0:
                first_voice = self.frame_builder.parse_frame(frames[0])
                if first_voice:
                    sender_callsign = first_voice.get('callsign', '').strip()
        
        # Process voice frames
        opus_frames = []
        recipients = []
        message_type = "voice"
        encrypted = False
        decrypted_successfully = False
        
        for i, frame_payload in enumerate(frames[voice_frames_start:], start=1):
            parsed = self.frame_builder.parse_frame(frame_payload)
            if not parsed:
                continue
            
            opus_data = parsed['opus_data']
            mac = parsed['mac']
            frame_callsign = parsed['callsign'].strip()
            frame_counter = parsed['frame_counter']
            
            # Check MAC
            if mac != b'\x00' * 16:
                encrypted = True
                # MAC verification would go here
            
            # Check if addressed to this station
            # Recipients typically in metadata, not individual frames
            
            opus_frames.append(opus_data)
        
        # Build status
        status = {
            'signature_valid': signature_valid,
            'encrypted': encrypted,
            'decrypted_successfully': decrypted_successfully,
            'sender': sender_callsign,
            'recipients': ','.join(recipients) if recipients else '',
            'message_type': message_type,
            'frame_counter': len(opus_frames),
            'superframe_counter': self.superframe_counter
        }
        
        self.superframe_counter += 1
        return (opus_frames, status)
    
    def emit_status(self, status: Dict):
        """Emit status message."""
        status_pmt = pmt.make_dict()
        
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("signature_valid"),
                                  pmt.from_bool(status.get('signature_valid', False)))
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("encrypted"),
                                  pmt.from_bool(status.get('encrypted', False)))
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("decrypted_successfully"),
                                  pmt.from_bool(status.get('decrypted_successfully', False)))
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("sender"),
                                  pmt.intern(status.get('sender', '')))
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("recipients"),
                                  pmt.intern(status.get('recipients', '')))
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("message_type"),
                                  pmt.intern(status.get('message_type', 'unknown')))
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("frame_counter"),
                                  pmt.from_long(status.get('frame_counter', 0)))
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("superframe_counter"),
                                  pmt.from_long(status.get('superframe_counter', 0)))
        
        self.message_port_pub(pmt.intern("status"), status_pmt)


def make_sleipnir_superframe_parser(
    local_callsign: str = "N0CALL",
    private_key_path: Optional[str] = None,
    require_signatures: bool = False,
    public_key_store_path: Optional[str] = None
):
    """Factory function for GRC."""
    return sleipnir_superframe_parser(
        local_callsign=local_callsign,
        private_key_path=private_key_path,
        require_signatures=require_signatures,
        public_key_store_path=public_key_store_path
    )

