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
import struct
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

    # Sync frame constants
    SYNC_PATTERN = 0xDEADBEEFCAFEBABE  # 64-bit sync pattern
    SYNC_FRAME_INTERVAL = 5  # Insert sync frame every N superframes (default: 5)
    SYNC_FRAME_BYTES = 49  # Same size as voice frame (386 bits for LDPC)

    def __init__(
        self,
        callsign: str = "N0CALL",
        enable_signing: bool = False,
        enable_encryption: bool = False,
        private_key_path: Optional[str] = None,
        mac_key: Optional[bytes] = None,
        enable_sync_frames: bool = True,
        sync_frame_interval: int = 5
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
        self.enable_sync_frames = enable_sync_frames
        self.sync_frame_interval = sync_frame_interval

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

        # Superframe counter for sync frames
        self.superframe_counter = 0
        
        # Queues for APRS and text messages
        self.aprs_queue = []
        self.text_queue = []

        # Message ports
        self.message_port_register_in(pmt.intern("in"))  # Opus frames input
        self.message_port_register_out(pmt.intern("out"))  # Frame payloads output
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

        # Control port for configuration
        self.message_port_register_in(pmt.intern("ctrl"))
        self.set_msg_handler(pmt.intern("ctrl"), self.handle_control)
        
        # APRS input port
        self.message_port_register_in(pmt.intern("aprs_in"))
        self.set_msg_handler(pmt.intern("aprs_in"), self.handle_aprs_msg)
        
        # Text input port
        self.message_port_register_in(pmt.intern("text_in"))
        self.set_msg_handler(pmt.intern("text_in"), self.handle_text_msg)

    def handle_control(self, msg):
        """Handle control messages to update configuration."""
        if not pmt.is_dict(msg):
            return

        try:
            if pmt.dict_has_key(msg, pmt.intern("enable_signing")):
                self.enable_signing = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("enable_signing"), pmt.PMT_F)
                )

            # Handle private key from key_source (gr-linux-crypto blocks)
            if pmt.dict_has_key(msg, pmt.intern("private_key")):
                key_pmt = pmt.dict_ref(msg, pmt.intern("private_key"), pmt.PMT_NIL)
                if pmt.is_u8vector(key_pmt):
                    key_bytes = bytes(pmt.u8vector_elements(key_pmt))
                    try:
                        from cryptography.hazmat.primitives import serialization
                        from cryptography.hazmat.backends import default_backend
                        try:
                            self.private_key = serialization.load_pem_private_key(
                                key_bytes, password=None, backend=default_backend()
                            )
                            self.enable_signing = True
                        except:
                            self.private_key = serialization.load_der_private_key(
                                key_bytes, password=None, backend=default_backend()
                            )
                            self.enable_signing = True
                    except Exception as e:
                        print(f"Warning: Could not load private key from control message: {e}")

            if pmt.dict_has_key(msg, pmt.intern("mac_key")):
                mac_key_pmt = pmt.dict_ref(msg, pmt.intern("mac_key"), pmt.PMT_NIL)
                if pmt.is_u8vector(mac_key_pmt):
                    mac_key_bytes = bytes(pmt.u8vector_elements(mac_key_pmt))
                    if len(mac_key_bytes) == 32:
                        self.mac_key = mac_key_bytes
                        self.frame_builder.mac_key = self.mac_key
                        self.frame_builder.enable_mac = True
                elif pmt.is_blob(mac_key_pmt):
                    self.mac_key = pmt.to_python(mac_key_pmt)
                    if len(self.mac_key) == 32:
                        self.frame_builder.mac_key = self.mac_key
                        self.frame_builder.enable_mac = True

            if pmt.dict_has_key(msg, pmt.intern("callsign")):
                self.callsign = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("callsign"), pmt.PMT_NIL)
                )
                self.frame_builder.callsign = self.callsign

        except Exception as e:
            print(f"Error handling control message: {e}")
    
    def handle_aprs_msg(self, msg):
        """Handle incoming APRS message."""
        if not pmt.is_pair(msg):
            return
        
        meta = pmt.car(msg)
        data = pmt.cdr(msg)
        
        # Extract APRS data
        if pmt.is_blob(data):
            aprs_data = pmt.to_python(data)
        elif pmt.is_u8vector(data):
            aprs_data = bytes(pmt.u8vector_elements(data))
        else:
            print("Warning: APRS message must be blob or u8vector")
            return
        
        # Queue APRS data (max 40 bytes per frame, but we use 39 for data + 1 for type)
        # APRS packets can be longer, so we may need to split them
        max_aprs_per_frame = 39
        for i in range(0, len(aprs_data), max_aprs_per_frame):
            chunk = aprs_data[i:i+max_aprs_per_frame]
            self.aprs_queue.append(chunk)
    
    def handle_text_msg(self, msg):
        """Handle incoming text message."""
        if not pmt.is_pair(msg):
            return
        
        meta = pmt.car(msg)
        data = pmt.cdr(msg)
        
        # Extract text data
        if pmt.is_symbol(data):
            text_data = pmt.symbol_to_string(data).encode('utf-8')
        elif pmt.is_blob(data):
            text_data = pmt.to_python(data)
        elif pmt.is_u8vector(data):
            text_data = bytes(pmt.u8vector_elements(data))
        else:
            print("Warning: Text message must be symbol, blob, or u8vector")
            return
        
        # Queue text data (max 39 bytes per frame)
        max_text_per_frame = 39
        for i in range(0, len(text_data), max_text_per_frame):
            chunk = text_data[i:i+max_text_per_frame]
            self.text_queue.append(chunk)

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

            # Update metadata with superframe counter
            output_meta = pmt.make_dict()
            if pmt.is_dict(meta):
                keys = pmt.dict_keys(meta)
                for i in range(pmt.length(keys)):
                    key = pmt.nth(i, keys)
                    value = pmt.dict_ref(meta, key, pmt.PMT_NIL)
                    output_meta = pmt.dict_add(output_meta, key, value)
            output_meta = pmt.dict_add(output_meta, pmt.intern("superframe_counter"),
                                      pmt.from_long(self.superframe_counter))

            # Output
            self.message_port_pub(pmt.intern("out"), pmt.cons(output_meta, output_pmt))

            # Increment superframe counter
            self.superframe_counter += 1

        except Exception as e:
            print(f"Error assembling superframe: {e}")

    def assemble_superframe(self, opus_frames: list[bytes]) -> list[bytes]:
        """
        Assemble superframe from 24 Opus frames.

        Returns list of frame payloads:
        - Frame 0 (if signing enabled): 32 bytes auth payload (will be padded to match matrix)
        - Frames 1-24: 49 bytes voice payloads (386 bits for LDPC) (or sync frame if enabled)
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

        # Check if we should insert sync frame
        insert_sync_frame = (
            self.enable_sync_frames and
            not self.enable_signing and  # Only when signing disabled
            self.superframe_counter > 0 and
            (self.superframe_counter % self.sync_frame_interval == 0)
        )

        # Frames 1-24: Voice/APRS/Text frames (or sync frame)
        sync_frame_inserted = False
        for i, opus_frame in enumerate(opus_frames, start=1):
            # Insert sync frame at position 1 (first voice frame position)
            if insert_sync_frame and i == 1 and not sync_frame_inserted:
                sync_payload = self.build_sync_frame()
                frames.append(sync_payload)
                sync_frame_inserted = True
                # Skip one voice frame (replaced by sync frame)
                continue

            # Check for APRS or text messages to insert
            frame_data = opus_frame
            frame_type = self.frame_builder.FRAME_TYPE_VOICE
            
            # Priority: APRS > Text > Voice
            if self.aprs_queue:
                aprs_data = self.aprs_queue.pop(0)
                # Ensure bytes and pad to 39 bytes
                if isinstance(aprs_data, np.ndarray):
                    aprs_data = bytes(aprs_data)
                frame_data = (aprs_data[:39] if len(aprs_data) >= 39 else aprs_data + b'\x00' * (39 - len(aprs_data)))
                frame_type = self.frame_builder.FRAME_TYPE_APRS
            elif self.text_queue:
                text_data = self.text_queue.pop(0)
                # Ensure bytes and pad to 39 bytes
                if isinstance(text_data, np.ndarray):
                    text_data = bytes(text_data)
                frame_data = (text_data[:39] if len(text_data) >= 39 else text_data + b'\x00' * (39 - len(text_data)))
                frame_type = self.frame_builder.FRAME_TYPE_TEXT
            
            # Build frame with appropriate type
            if frame_type == self.frame_builder.FRAME_TYPE_VOICE:
                voice_payload = self.build_voice_frame(frame_data, i)
            elif frame_type == self.frame_builder.FRAME_TYPE_APRS:
                voice_payload = self.frame_builder.build_aprs_frame(frame_data, i)
            else:  # TEXT
                voice_payload = self.frame_builder.build_text_frame(frame_data, i)
            
            frames.append(voice_payload)

        return frames

    def build_sync_frame(self) -> bytes:
        """
        Build sync frame payload (49 bytes, 386 bits for LDPC).

        Structure:
        - Bytes 0-7:   Sync pattern (64 bits, fixed value)
        - Bytes 8-11:  Superframe counter (32 bits)
        - Bytes 12-15: Frame counter (32 bits, always 0 for sync frame)
        - Bytes 16-47: Reserved/padding
        """
        sync_frame = bytearray(self.SYNC_FRAME_BYTES)

        # Sync pattern (64 bits = 8 bytes)
        struct.pack_into('>Q', sync_frame, 0, self.SYNC_PATTERN)

        # Superframe counter (32 bits = 4 bytes)
        struct.pack_into('>I', sync_frame, 8, self.superframe_counter)

        # Frame counter (32 bits = 4 bytes, always 0 for sync frame)
        struct.pack_into('>I', sync_frame, 12, 0)

        # Bytes 16-47: Reserved/padding (already zeros)

        return bytes(sync_frame)

    def build_auth_frame(self, superframe_data: bytes) -> bytes:
        """
        Build authentication frame payload.
        
        Note: For now, we pad to 49 bytes (386 bits) to match voice matrix.
        TODO: Generate proper auth matrix (256 bits -> 768 bits) and use 32 bytes.
        """
        try:
            signature = generate_ecdsa_signature(superframe_data, self.private_key)
            # Pad/truncate to 49 bytes to match voice matrix (temporary workaround)
            # TODO: Use proper auth matrix (32 bytes -> 96 bytes)
            if len(signature) > 49:
                signature = signature[:49]
            elif len(signature) < 49:
                signature = signature.ljust(49, b'\x00')
            return signature
        except Exception as e:
            print(f"Error building auth frame: {e}")
            return b'\x00' * 49

    def build_voice_frame(self, opus_data: bytes, frame_num: int) -> bytes:
        """Build voice frame payload (49 bytes, 386 bits for LDPC)."""
        return self.frame_builder.build_frame(opus_data, frame_num)


def make_sleipnir_superframe_assembler(
    callsign: str = "N0CALL",
    enable_signing: bool = False,
    enable_encryption: bool = False,
    private_key_path: Optional[str] = None,
    mac_key: Optional[bytes] = None,
    enable_sync_frames: bool = True,
    sync_frame_interval: int = 5
):
    """Factory function for GRC."""
    return sleipnir_superframe_assembler(
        callsign=callsign,
        enable_signing=enable_signing,
        enable_encryption=enable_encryption,
        private_key_path=private_key_path,
        mac_key=mac_key,
        enable_sync_frames=enable_sync_frames,
        sync_frame_interval=sync_frame_interval
    )

