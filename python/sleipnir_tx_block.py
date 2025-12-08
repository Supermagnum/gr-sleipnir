#!/usr/bin/env python3
"""
gr-sleipnir TX Block

GNU Radio block for superframe transmission with encryption and signing.

Inputs:
- Port 0: Audio samples (float) from Opus encoder
- Port 1: Control messages (PMT dict) with configuration

Outputs:
- Port 0: Complex baseband samples to 4FSK/8FSK modulator

Control message format (PMT dict):
{
    'enable_signing': bool,
    'enable_encryption': bool,
    'key_source': str,  # Path to key file or 'keyring'
    'recipient': str,  # Single callsign or comma-separated list
    'message_type': str,  # 'voice', 'text', etc.
    'payload': bytes,  # Optional payload for non-voice messages
    'from_callsign': str,  # Source callsign
    'to_callsign': str,  # Destination callsign(s)
}
"""

import numpy as np
from gnuradio import gr
import pmt
import time
import struct
from typing import Optional, List

# Import our crypto helpers
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


class sleipnir_tx_block(gr.sync_block):
    """
    gr-sleipnir TX block for superframe transmission.
    
    Handles:
    - Superframe assembly (25 frames)
    - Encryption and signing
    - Per-recipient key blocks
    - Metadata insertion
    """
    
    # Superframe parameters
    FRAMES_PER_SUPERFRAME = 25
    FRAME_DURATION_MS = 40
    VOICE_FRAME_BYTES = 48  # 384 bits
    AUTH_FRAME_BYTES = 32   # 256 bits
    
    def __init__(
        self,
        callsign: str = "N0CALL",
        rf_samp_rate: float = 48000.0,
        symbol_rate: float = 4800.0,
        auth_matrix_file: str = "../ldpc_matrices/ldpc_auth_768_256.alist",
        voice_matrix_file: str = "../ldpc_matrices/ldpc_voice_576_384.alist"
    ):
        """
        Initialize sleipnir TX block.
        
        Args:
            callsign: Default source callsign
            rf_samp_rate: RF sample rate (Hz)
            symbol_rate: Symbol rate (symbols/sec)
            auth_matrix_file: Path to auth LDPC matrix
            voice_matrix_file: Path to voice LDPC matrix
        """
        gr.sync_block.__init__(
            self,
            name="sleipnir_tx_block",
            in_sig=[np.float32],  # Audio input
            out_sig=[np.complex64]  # Complex baseband output
        )
        
        self.callsign = callsign
        self.rf_samp_rate = rf_samp_rate
        self.symbol_rate = symbol_rate
        
        # Message port for control
        self.message_port_register_in(pmt.intern("ctrl"))
        self.set_msg_handler(pmt.intern("ctrl"), self.handle_control_msg)
        
        # State
        self.enable_signing = False
        self.enable_encryption = False
        self.private_key = None
        self.mac_key = None
        self.recipients = []
        self.from_callsign = callsign
        self.to_callsigns = []
        self.message_type = "voice"
        
        # Frame buffers
        self.opus_frame_buffer = bytearray()
        self.superframe_buffer = []
        self.frame_counter = 0
        self.superframe_counter = 0
        
        # Voice frame builder
        self.frame_builder = VoiceFrameBuilder(
            callsign=callsign,
            mac_key=None,
            enable_mac=False
        )
        
        # Timing
        self.samples_per_frame = int(rf_samp_rate * self.FRAME_DURATION_MS / 1000.0)
        self.output_buffer = []
        
    def handle_control_msg(self, msg):
        """Handle control message (PMT dict)."""
        if not pmt.is_dict(msg):
            print("Warning: Control message is not a PMT dict")
            return
        
        # Extract fields
        try:
            if pmt.dict_has_key(msg, pmt.intern("enable_signing")):
                self.enable_signing = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("enable_signing"), pmt.PMT_F)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("enable_encryption")):
                self.enable_encryption = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("enable_encryption"), pmt.PMT_F)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("key_source")):
                key_source = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("key_source"), pmt.PMT_NIL)
                )
                if key_source and key_source != "":
                    self.private_key = load_private_key(key_source)
                    if self.private_key:
                        self.enable_signing = True
            
            if pmt.dict_has_key(msg, pmt.intern("recipient")):
                recipient_str = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("recipient"), pmt.PMT_NIL)
                )
                if recipient_str:
                    self.recipients = [r.strip() for r in recipient_str.split(",")]
                    self.to_callsigns = self.recipients
            
            if pmt.dict_has_key(msg, pmt.intern("from_callsign")):
                self.from_callsign = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("from_callsign"), pmt.PMT_NIL)
                )
                self.frame_builder.callsign = self.from_callsign
            
            if pmt.dict_has_key(msg, pmt.intern("to_callsign")):
                to_callsign = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("to_callsign"), pmt.PMT_NIL)
                )
                if to_callsign:
                    self.to_callsigns = [to_callsign]
                    self.recipients = self.to_callsigns
            
            if pmt.dict_has_key(msg, pmt.intern("message_type")):
                self.message_type = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("message_type"), pmt.PMT_NIL)
                )
            
            if pmt.dict_has_key(msg, pmt.intern("mac_key")):
                mac_key_bytes = pmt.to_python(
                    pmt.dict_ref(msg, pmt.intern("mac_key"), pmt.PMT_NIL)
                )
                if isinstance(mac_key_bytes, bytes) and len(mac_key_bytes) == 32:
                    self.mac_key = mac_key_bytes
                    self.frame_builder.mac_key = mac_key_bytes
                    self.frame_builder.enable_mac = True
            
        except Exception as e:
            print(f"Error handling control message: {e}")
    
    def build_auth_frame(self, superframe_data: bytes) -> bytes:
        """Build authentication frame payload (32 bytes)."""
        if not self.enable_signing or not self.private_key:
            return b'\x00' * 32
        
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
        if len(opus_data) != 40:
            # Pad or truncate
            if len(opus_data) < 40:
                opus_data = opus_data.ljust(40, b'\x00')
            else:
                opus_data = opus_data[:40]
        
        return self.frame_builder.build_frame(opus_data, frame_num)
    
    def assemble_superframe(self, opus_frames: List[bytes]) -> List[bytes]:
        """
        Assemble complete superframe (25 frames).
        
        Returns list of frame payloads ready for LDPC encoding.
        """
        if len(opus_frames) != 24:
            raise ValueError(f"Expected 24 Opus frames, got {len(opus_frames)}")
        
        frames = []
        
        # Build superframe data for signing
        superframe_data = b''.join(opus_frames)
        
        # Frame 0: Authentication frame
        if self.enable_signing:
            auth_payload = self.build_auth_frame(superframe_data)
            frames.append(auth_payload)
        else:
            # No auth frame, skip frame 0
            pass
        
        # Frames 1-24: Voice frames
        for i, opus_frame in enumerate(opus_frames, start=1):
            voice_payload = self.build_voice_frame(opus_frame, i)
            frames.append(voice_payload)
        
        return frames
    
    def work(self, input_items, output_items):
        """
        Process audio input and generate superframe output.
        
        This is a simplified version - in practice, you'd need to:
        1. Buffer audio samples
        2. Encode with Opus (or receive from Opus encoder block)
        3. Assemble superframe
        4. Encode with LDPC
        5. Modulate to 4FSK/8FSK
        6. Output complex samples
        """
        # For now, this is a placeholder
        # The actual implementation would integrate with:
        # - Opus encoder block (input)
        # - LDPC encoder blocks
        # - 4FSK/8FSK modulator blocks
        
        # This block is meant to be used in a hierarchical block
        # that combines all the components
        
        noutput_items = len(output_items[0])
        
        # Placeholder: output zeros for now
        # Real implementation would process frames here
        output_items[0][:noutput_items] = 0.0 + 0.0j
        
        return noutput_items


# For use as embedded Python block in GRC
def make_sleipnir_tx_block(
    callsign: str = "N0CALL",
    rf_samp_rate: float = 48000.0,
    symbol_rate: float = 4800.0,
    auth_matrix_file: str = "../ldpc_matrices/ldpc_auth_768_256.alist",
    voice_matrix_file: str = "../ldpc_matrices/ldpc_voice_576_384.alist"
):
    """Factory function for GRC."""
    return sleipnir_tx_block(
        callsign=callsign,
        rf_samp_rate=rf_samp_rate,
        symbol_rate=symbol_rate,
        auth_matrix_file=auth_matrix_file,
        voice_matrix_file=voice_matrix_file
    )

