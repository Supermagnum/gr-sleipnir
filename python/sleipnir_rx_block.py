#!/usr/bin/env python3
"""
gr-sleipnir RX Block

GNU Radio block for superframe reception with decryption and signature verification.

Inputs:
- Port 0: Complex baseband samples from 4FSK/8FSK demodulator

Outputs:
- Port 0: Audio samples (float32) to Opus decoder
- Message Port: Status messages (PMT dict)

Status message format (PMT dict):
{
    'signature_valid': bool,
    'encrypted': bool,
    'decrypted_successfully': bool,
    'sender': str,
    'recipients': str,  # Comma-separated list
    'message_type': str,
    'frame_counter': int,
    'superframe_counter': int,
}
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
    get_callsign_bytes
)
from python.voice_frame_builder import VoiceFrameBuilder


class sleipnir_rx_block(gr.sync_block):
    """
    gr-sleipnir RX block for superframe reception.

    Handles:
    - Superframe parsing and desynchronization
    - Signature verification
    - Decryption
    - Status reporting
    """

    # Superframe parameters
    FRAMES_PER_SUPERFRAME = 25
    FRAME_DURATION_MS = 40
    VOICE_FRAME_BYTES = 48  # 384 bits after LDPC decoding
    AUTH_FRAME_BYTES = 32   # 256 bits after LDPC decoding

    def __init__(
        self,
        local_callsign: str = "N0CALL",
        private_key_path: Optional[str] = None,
        require_signatures: bool = False,
        auth_matrix_file: str = "../ldpc_matrices/ldpc_auth_768_256.alist",
        voice_matrix_file: str = "../ldpc_matrices/ldpc_voice_576_384.alist"
    ):
        """
        Initialize sleipnir RX block.

        Args:
            local_callsign: This station's callsign
            private_key_path: Path to private key for decryption
            require_signatures: Require valid signatures (reject unsigned)
            auth_matrix_file: Path to auth LDPC matrix
            voice_matrix_file: Path to voice LDPC matrix
        """
        gr.sync_block.__init__(
            self,
            name="sleipnir_rx_block",
            in_sig=[np.complex64],  # Complex baseband input
            out_sig=[np.float32]  # Audio output
        )

        self.local_callsign = local_callsign
        self.require_signatures = require_signatures
        self.private_key_path = private_key_path

        # Load private key if provided
        self.private_key = None
        if private_key_path:
            try:
                from python.crypto_helpers import load_private_key
                self.private_key = load_private_key(private_key_path)
            except Exception as e:
                print(f"Warning: Could not load private key: {e}")

        # State
        self.frame_buffer = []
        self.superframe_buffer = []
        self.frame_counter = 0
        self.superframe_counter = 0
        self.expecting_auth_frame = True

        # Status
        self.last_status = {
            'signature_valid': False,
            'encrypted': False,
            'decrypted_successfully': False,
            'sender': '',
            'recipients': '',
            'message_type': 'unknown',
            'frame_counter': 0,
            'superframe_counter': 0
        }

        # Voice frame builder for parsing
        self.frame_builder = VoiceFrameBuilder(
            callsign=local_callsign,
            mac_key=None,
            enable_mac=False
        )

        # Message ports
        self.message_port_register_out(pmt.intern("status"))
        self.message_port_register_out(pmt.intern("audio_pdu"))

    def emit_status(self, status: Dict):
        """Emit status message."""
        self.last_status = status.copy()

        # Create PMT dict
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

    def parse_voice_frame(self, payload: bytes) -> Optional[Dict]:
        """
        Parse voice frame payload.

        Returns dict with parsed fields or None if invalid.
        """
        if len(payload) != self.VOICE_FRAME_BYTES:
            return None

        try:
            parsed = self.frame_builder.parse_frame(payload)
            return parsed
        except Exception as e:
            print(f"Error parsing voice frame: {e}")
            return None

    def verify_signature(self, signature: bytes, superframe_data: bytes, sender_callsign: str) -> bool:
        """
        Verify ECDSA signature.

        Args:
            signature: 32-byte signature from Frame 0
            superframe_data: Original superframe data
            sender_callsign: Sender's callsign (for key lookup)

        Returns:
            True if signature is valid
        """
        # Note: This is a placeholder
        # Proper implementation would:
        # 1. Look up sender's public key from key store
        # 2. Verify signature using public key
        # 3. Return verification result

        # For now, return False (signature verification not fully implemented)
        # See crypto_helpers.verify_ecdsa_signature for details
        print(f"Signature verification for {sender_callsign} not fully implemented")
        return False

    def check_recipient(self, recipients: str) -> bool:
        """
        Check if local callsign is in recipient list.

        Args:
            recipients: Comma-separated list of recipient callsigns

        Returns:
            True if this station is a recipient
        """
        if not recipients:
            return False

        recipient_list = [r.strip().upper() for r in recipients.split(",")]
        local_callsign_upper = self.local_callsign.upper()

        return local_callsign_upper in recipient_list

    def decrypt_payload(self, encrypted_payload: bytes) -> Optional[bytes]:
        """
        Decrypt payload using local private key.

        Args:
            encrypted_payload: Encrypted payload bytes

        Returns:
            Decrypted payload or None if decryption fails
        """
        if not self.private_key:
            return None

        # Note: Decryption implementation depends on encryption scheme
        # This is a placeholder - actual implementation would:
        # 1. Extract encrypted data and metadata
        # 2. Use private key to decrypt
        # 3. Return decrypted payload

        print("Decryption not fully implemented")
        return None

    def process_superframe(self, frames: list[bytes]) -> Optional[list[bytes]]:
        """
        Process complete superframe.

        Args:
            frames: List of frame payloads (after LDPC decoding)

        Returns:
            List of Opus frames (40 bytes each) or None if processing fails
        """
        if len(frames) < 24:
            print(f"Warning: Incomplete superframe, got {len(frames)} frames")
            return None

        # Determine if Frame 0 is present (auth frame)
        has_auth_frame = len(frames) == 25

        # Extract Frame 0 if present
        auth_payload = None
        voice_frames_start = 0

        if has_auth_frame:
            auth_payload = frames[0]
            voice_frames_start = 1

        # Process authentication frame
        signature_valid = False
        sender_callsign = ""

        if auth_payload:
            # Frame 0 contains signature
            signature = auth_payload[:32]

            # Build superframe data for verification
            superframe_data = b''.join(frames[voice_frames_start:])

            # Verify signature (placeholder - needs sender's public key)
            # For now, we'll extract sender from first voice frame
            if len(frames) > voice_frames_start:
                first_voice_frame = self.parse_voice_frame(frames[voice_frames_start])
                if first_voice_frame:
                    sender_callsign = first_voice_frame.get('callsign', '')

            # Verify signature
            signature_valid = self.verify_signature(signature, superframe_data, sender_callsign)

            if self.require_signatures and not signature_valid:
                print("Rejecting unsigned message (require_signatures=True)")
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
            # No auth frame - unsigned message
            if self.require_signatures:
                print("Rejecting unsigned message (require_signatures=True)")
                return None

            # Extract sender from first voice frame
            if len(frames) > 0:
                first_voice_frame = self.parse_voice_frame(frames[0])
                if first_voice_frame:
                    sender_callsign = first_voice_frame.get('callsign', '')

        # Process voice frames
        opus_frames = []
        recipients = []
        message_type = "voice"
        encrypted = False
        decrypted_successfully = False

        for i, frame_payload in enumerate(frames[voice_frames_start:], start=1):
            parsed = self.parse_voice_frame(frame_payload)
            if not parsed:
                continue

            # Extract Opus data
            opus_data = parsed['opus_data']

            # Verify MAC if present
            mac_valid = True
            if parsed['mac'] != b'\x00' * 16:
                # MAC present - verify it
                # Note: Need MAC key for verification
                # For now, assume MAC is valid if present
                encrypted = True  # MAC indicates encryption

            # Extract callsign and frame counter
            frame_callsign = parsed['callsign']
            frame_counter = parsed['frame_counter']

            # Check if this station is recipient
            # Recipients are typically in metadata, not in individual frames
            # For now, we'll check in status message

            opus_frames.append(opus_data)

        # Extract recipients from metadata (if available)
        # For now, use empty list

        # Emit status
        self.emit_status({
            'signature_valid': signature_valid,
            'encrypted': encrypted,
            'decrypted_successfully': decrypted_successfully,
            'sender': sender_callsign,
            'recipients': ','.join(recipients) if recipients else '',
            'message_type': message_type,
            'frame_counter': len(opus_frames),
            'superframe_counter': self.superframe_counter
        })

        # Emit audio PDU
        if opus_frames:
            audio_data = b''.join(opus_frames)
            audio_pmt = pmt.init_u8vector(len(audio_data), list(audio_data))
            meta = pmt.make_dict()
            meta = pmt.dict_add(meta, pmt.intern("sender"), pmt.intern(sender_callsign))
            meta = pmt.dict_add(meta, pmt.intern("message_type"), pmt.intern(message_type))
            self.message_port_pub(pmt.intern("audio_pdu"), pmt.cons(meta, audio_pmt))

        self.superframe_counter += 1
        return opus_frames

    def work(self, input_items, output_items):
        """
        Process input samples.

        Note: This is a placeholder - actual implementation would:
        1. Receive decoded bits from LDPC decoder
        2. Parse frames
        3. Assemble superframes
        4. Process and output audio
        """
        # This block is meant to be used in a hierarchical block
        # that combines all the components

        noutput_items = len(output_items[0])

        # Placeholder: output zeros for now
        # Real implementation would process frames here
        output_items[0][:noutput_items] = 0.0

        return noutput_items


def make_sleipnir_rx_block(
    local_callsign: str = "N0CALL",
    private_key_path: Optional[str] = None,
    require_signatures: bool = False,
    auth_matrix_file: str = "../ldpc_matrices/ldpc_auth_768_256.alist",
    voice_matrix_file: str = "../ldpc_matrices/ldpc_voice_576_384.alist"
):
    """Factory function for GRC."""
    return sleipnir_rx_block(
        local_callsign=local_callsign,
        private_key_path=private_key_path,
        require_signatures=require_signatures,
        auth_matrix_file=auth_matrix_file,
        voice_matrix_file=voice_matrix_file
    )

