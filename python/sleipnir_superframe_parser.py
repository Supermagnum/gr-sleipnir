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


class sleipnir_superframe_parser(gr.basic_block):
    """
    Parses superframes from decoded bits.

    Input: PDU with decoded bits (after LDPC decoding)
    Output: PDU with Opus frames and status messages
    
    Error Tracking:
    - Tracks frame_error_count: Cumulative count of frames that failed to decode
    - Tracks total_frames_received: Cumulative count of all frames received
    - FER calculation: frame_error_count / total_frames_received
    - For voice-only tests, only Opus frames are counted as successful
    - Corrupted frames misclassified as APRS/text are counted as errors
    """

    # Frame sizes depend on FEC:
    # - With FEC: LDPC decoder outputs 48 bytes (384 bits) for voice matrix
    # - Without FEC: Superframe assembler outputs 49 bytes
    # We need to handle both cases
    VOICE_FRAME_BYTES_WITH_FEC = 48  # 384 bits output from LDPC decoder
    VOICE_FRAME_BYTES_WITHOUT_FEC = 49  # 49 bytes from superframe assembler
    # Default to 48 bytes (FEC enabled case)
    VOICE_FRAME_BYTES = 48  # Default: assume FEC is enabled
    AUTH_FRAME_BYTES = 64   # 64 bytes after LDPC decoding (512 bits) - stores full ECDSA signature (r + s)
    FRAMES_PER_SUPERFRAME = 25

    # Sync frame constants (must match TX)
    SYNC_PATTERN = 0xDEADBEEFCAFEBABE  # 64-bit sync pattern
    SYNC_FRAME_BYTES = 49  # Same size as voice frame (386 bits)

    def __init__(
        self,
        local_callsign: str = "N0CALL",
        private_key_path: Optional[str] = None,
        require_signatures: bool = False,
        public_key_store_path: Optional[str] = None,
        enable_sync_detection: bool = True,
        mac_key: Optional[bytes] = None
    ):
        """
        Initialize superframe parser.

        Args:
            local_callsign: This station's callsign
            private_key_path: Path to private key for decryption
            require_signatures: Require valid signatures
            public_key_store_path: Path to public key store directory
            enable_sync_detection: Enable sync detection
            mac_key: MAC key for ChaCha20-Poly1305 verification (32 bytes)
        """
        gr.basic_block.__init__(
            self,
            name="sleipnir_superframe_parser",
            in_sig=None,
            out_sig=None
        )

        self.local_callsign = local_callsign.upper()
        self.require_signatures = require_signatures
        self.private_key_path = private_key_path
        self.public_key_store_path = public_key_store_path
        self.enable_sync_detection = enable_sync_detection
        self.mac_key = mac_key

        # Load private key if provided
        self.private_key = None
        if private_key_path:
            try:
                self.private_key = load_private_key(private_key_path)
            except Exception as e:
                print(f"Warning: Could not load private key: {e}")

        # Frame builder for parsing (with MAC key for verification)
        self.frame_builder = VoiceFrameBuilder(
            callsign=local_callsign,
            mac_key=mac_key,
            enable_mac=(mac_key is not None)
        )

        # Store reference to self to prevent garbage collection issues
        # This helps prevent RecursionError when GNU Radio gateway accesses the block
        self._self_ref = self
        if not hasattr(type(self), '_instances'):
            type(self)._instances = []
        type(self)._instances.append(self)
        
        # Store references to critical methods to ensure they're always accessible
        self._handle_msg_ref = self.handle_msg
        self._handle_control_ref = self.handle_control
        
        # Store all critical references in a dict to prevent GC
        self._refs = {
            'self': self,
            'handle_msg': self.handle_msg,
            'handle_control': self.handle_control,
            'gateway': getattr(self, 'gateway', None)
        }
        
        # State
        self.frame_buffer = []
        self.superframe_counter = 0
        self.sync_state = "searching"  # "searching", "synced", "lost"
        self.last_sync_counter = None
        
        # Error tracking
        self.frame_error_count = 0  # Frames that failed to parse or validate
        self.total_frames_received = 0  # Total frames received (for FER calculation)

        # Message ports
        self.message_port_register_in(pmt.intern("in"))
        self.message_port_register_out(pmt.intern("out"))  # Opus frames output
        self.message_port_register_out(pmt.intern("status"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

        # Control port
        self.message_port_register_in(pmt.intern("ctrl"))
        self.set_msg_handler(pmt.intern("ctrl"), self.handle_control)
        
        # APRS output port
        self.message_port_register_out(pmt.intern("aprs_out"))
        
        # Text output port
        self.message_port_register_out(pmt.intern("text_out"))

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
                        except:
                            self.private_key = serialization.load_der_private_key(
                                key_bytes, password=None, backend=default_backend()
                            )
                    except Exception as e:
                        print(f"Warning: Could not load private key from control message: {e}")

            # Handle public key from key_source (gr-linux-crypto blocks)
            if pmt.dict_has_key(msg, pmt.intern("public_key")):
                key_pmt = pmt.dict_ref(msg, pmt.intern("public_key"), pmt.PMT_NIL)
                key_id_pmt = pmt.dict_ref(msg, pmt.intern("key_id"), pmt.PMT_NIL) if pmt.dict_has_key(msg, pmt.intern("key_id")) else pmt.intern("default")
                key_id = pmt.symbol_to_string(key_id_pmt) if pmt.is_symbol(key_id_pmt) else "default"
                
                if pmt.is_u8vector(key_pmt):
                    key_bytes = bytes(pmt.u8vector_elements(key_pmt))
                    try:
                        from cryptography.hazmat.primitives import serialization
                        from cryptography.hazmat.backends import default_backend
                        try:
                            public_key = serialization.load_pem_public_key(
                                key_bytes, backend=default_backend()
                            )
                        except:
                            public_key = serialization.load_der_public_key(
                                key_bytes, backend=default_backend()
                            )
                        # Store public key (could be used for signature verification)
                        # Note: This would need integration with the signature verification logic
                    except Exception as e:
                        print(f"Warning: Could not load public key from control message: {e}")

        except Exception as e:
            print(f"Error handling control message: {e}")

    def handle_msg(self, msg):
        """Handle incoming PDU with decoded bits."""
        if not pmt.is_pair(msg):
            print("Warning: handle_msg received non-pair message")
            return

        meta = pmt.car(msg)
        data = pmt.cdr(msg)

        if not pmt.is_blob(data) and not pmt.is_u8vector(data):
            print(f"Warning: Expected blob/u8vector data, got {type(data)}")
            return

        # Extract decoded bits
        if pmt.is_u8vector(data):
            decoded_data = bytes(pmt.u8vector_elements(data))
        elif pmt.is_blob(data):
            decoded_data = pmt.to_python(data)
        else:
            print("Warning: Unexpected data type")
            return

        print(f"Superframe parser received {len(decoded_data)} bytes")

        # Check if this is a single frame from frame-aware decoder-to-PDU block
        # The frame-aware block sends individual frames with metadata
        frames = []
        if pmt.is_dict(meta):
            frame_num_pmt = pmt.dict_ref(meta, pmt.intern("frame_num"), pmt.PMT_NIL)
            frame_size_pmt = pmt.dict_ref(meta, pmt.intern("frame_size"), pmt.PMT_NIL)
            
            if pmt.is_number(frame_num_pmt) and pmt.is_number(frame_size_pmt):
                # This is a single frame from frame-aware decoder
                frame_num = pmt.to_python(frame_num_pmt)
                frame_size = pmt.to_python(frame_size_pmt)
                
                # Validate frame size matches expected size
                if frame_num == 0:
                    # Auth frame: should be 64 bytes
                    if len(decoded_data) == 64:
                        frames = [decoded_data]
                    else:
                        print(f"Warning: Auth frame size mismatch: expected 64, got {len(decoded_data)}")
                        frames = []
                else:
                    # Voice frame: should be 48 bytes
                    if len(decoded_data) == 48:
                        frames = [decoded_data]
                    else:
                        print(f"Warning: Voice frame size mismatch: expected 48, got {len(decoded_data)}")
                        frames = []
            else:
                # Not from frame-aware decoder, use standard parsing (concatenated frames)
                frames = self.parse_frames(decoded_data)
        else:
            # No metadata, use standard parsing (concatenated frames)
            frames = self.parse_frames(decoded_data)

        print(f"Superframe parser parsed {len(frames)} frames")

        if not frames:
            print("Warning: No frames parsed from data")
            # Count this as an error - data was received but no frames could be parsed
            # This happens when data is corrupted or misaligned
            # Estimate frames based on data length (approximate)
            estimated_frames = max(1, len(decoded_data) // self.VOICE_FRAME_BYTES_WITH_FEC)
            self.total_frames_received += estimated_frames  # We received data (attempted to process)
            self.frame_error_count += estimated_frames  # All estimated frames failed to parse
            return

        # Add frames to buffer
        self.frame_buffer.extend(frames)
        print(f"Frame buffer now has {len(self.frame_buffer)} frames (need 24-25 for superframe)")

        # Process superframe when we have enough frames
        # Logic: Look for complete superframes in the buffer
        # A superframe can be:
        # - 25 frames: 1 auth (64 bytes) + 24 voice (48 bytes each)
        # - 24 frames: 24 voice (48 bytes each, no auth)
        # We need to detect superframe boundaries by looking for auth frames (64 bytes)
        
        processed_any = False
        while len(self.frame_buffer) >= 24:
            # Check if first frame is auth frame (64 bytes)
            if len(self.frame_buffer) > 0 and len(self.frame_buffer[0]) == 64:
                # First frame is auth - need 25 frames total (1 auth + 24 voice)
                if len(self.frame_buffer) >= 25:
                    # We have a complete superframe with auth
                    superframe_frames = self.frame_buffer[:25]
                    self.frame_buffer = self.frame_buffer[25:]
                    print(f"Processing superframe: {len(superframe_frames)} frames (1 auth + 24 voice), first frame size: 64 bytes")
                    result = self.process_superframe(superframe_frames)
                    processed_any = True
                    if result:
                        break  # Process one superframe at a time
                else:
                    # Need more frames (have auth but not all 24 voice frames yet)
                    break
            else:
                # First frame is voice (48 bytes) or buffer is empty
                # Check if we have 24 consecutive voice frames (no auth)
                # But we need to be careful - if we have 24 frames and next would be auth,
                # we should wait. For now, process 24 frames as voice-only superframe
                if len(self.frame_buffer) >= 24:
                    # Check if 25th frame (if exists) is auth - if so, we might be missing first auth
                    # For now, process 24 frames as voice-only
                    superframe_frames = self.frame_buffer[:24]
                    self.frame_buffer = self.frame_buffer[24:]
                    print(f"Processing superframe: {len(superframe_frames)} frames (24 voice, no auth), first frame size: {len(superframe_frames[0]) if superframe_frames else 0} bytes")
                    result = self.process_superframe(superframe_frames)
                    processed_any = True
                    if result:
                        break  # Process one superframe at a time
                else:
                    break
        
        if not processed_any:
            result = None

        if result:
            opus_frames, status = result

            print(f"Superframe processed: {len(opus_frames)} Opus frames, frame_counter={status.get('frame_counter', 0)}, total_frames_received={status.get('total_frames_received', 0)}, frame_errors={status.get('frame_error_count', 0)}")

            # Emit status
            self.emit_status(status)
            print(f"Status emitted: frame_counter={status.get('frame_counter', 0)}, total_frames_received={status.get('total_frames_received', 0)}")

            # Emit Opus frames (only voice, not APRS/text)
            if opus_frames:
                audio_data = b''.join(opus_frames)
                audio_pmt = pmt.init_u8vector(len(audio_data), list(audio_data))
                output_meta = pmt.make_dict()
                output_meta = pmt.dict_add(output_meta, pmt.intern("sender"),
                                          pmt.intern(status.get('sender', '')))
                output_meta = pmt.dict_add(output_meta, pmt.intern("message_type"),
                                          pmt.intern("voice"))
                self.message_port_pub(pmt.intern("out"), pmt.cons(output_meta, audio_pmt))
        else:
            print("Warning: process_superframe returned None")
            
        # APRS and text messages are emitted in process_superframe

    def parse_frames(self, data: bytes) -> list[bytes]:
        """
        Parse frames from decoded data.

        Handles desynchronization by looking for sync patterns and frame boundaries.
        """
        frames = []

        if self.enable_sync_detection:
            # Try to detect sync frame first
            sync_frame_idx = self.detect_sync_frame(data)
            if sync_frame_idx is not None:
                # Found sync frame - use it for synchronization
                self.handle_sync_frame(data[sync_frame_idx:sync_frame_idx+self.SYNC_FRAME_BYTES])
                # Parse frames starting from sync frame position
                return self.parse_frames_with_sync(data, sync_frame_idx)

        # Standard parsing - assumes frames are properly aligned
        # Try both frame sizes (48 bytes with FEC, 49 bytes without FEC)
        # First try 48 bytes (FEC enabled)
        frame_size = self.VOICE_FRAME_BYTES_WITH_FEC
        total_frames = len(data) // frame_size
        
        # If 48-byte frames don't divide evenly, try 49-byte frames
        if len(data) % frame_size != 0:
            frame_size_alt = self.VOICE_FRAME_BYTES_WITHOUT_FEC
            total_frames_alt = len(data) // frame_size_alt
            if len(data) % frame_size_alt == 0:
                frame_size = frame_size_alt
                total_frames = total_frames_alt
                print(f"Using frame size {frame_size} bytes (without FEC)")
            else:
                print(f"Warning: Data length {len(data)} doesn't divide evenly by {frame_size} or {frame_size_alt}")
        else:
            print(f"Using frame size {frame_size} bytes (with FEC)")

        # Check if we have auth frame (25 frames) or just voice frames (24 frames)
        if total_frames == 25:
            # Has auth frame
            auth_frame = data[:self.AUTH_FRAME_BYTES]
            frames.append(auth_frame)
            voice_data = data[self.AUTH_FRAME_BYTES:]
        else:
            # No auth frame
            voice_data = data

        # Parse voice frames
        for i in range(0, len(voice_data), frame_size):
            frame = voice_data[i:i+frame_size]
            if len(frame) == frame_size:
                # Check if this is a sync frame
                if self.is_sync_frame(frame):
                    self.handle_sync_frame(frame)
                    continue  # Skip sync frame in output
                frames.append(frame)

        return frames

    def detect_sync_frame(self, data: bytes) -> Optional[int]:
        """
        Detect sync frame in data by looking for sync pattern.

        Returns:
            Index of sync frame start, or None if not found
        """
        sync_pattern_bytes = struct.pack('>Q', self.SYNC_PATTERN)

        # Search for sync pattern
        for i in range(len(data) - self.SYNC_FRAME_BYTES + 1):
            if data[i:i+8] == sync_pattern_bytes:
                # Found sync pattern - verify it's a valid sync frame
                if i + self.SYNC_FRAME_BYTES <= len(data):
                    frame = data[i:i+self.SYNC_FRAME_BYTES]
                    if self.validate_sync_frame(frame):
                        return i

        return None

    def is_sync_frame(self, frame: bytes) -> bool:
        """Check if frame is a sync frame."""
        if len(frame) < 8:
            return False

        sync_pattern_bytes = struct.pack('>Q', self.SYNC_PATTERN)
        return frame[:8] == sync_pattern_bytes

    def validate_sync_frame(self, frame: bytes) -> bool:
        """
        Validate sync frame structure.

        Checks:
        - Sync pattern matches
        - Frame counter is 0
        - Superframe counter is reasonable
        """
        if len(frame) < self.SYNC_FRAME_BYTES:
            return False

        # Check sync pattern
        sync_pattern_bytes = struct.pack('>Q', self.SYNC_PATTERN)
        if frame[:8] != sync_pattern_bytes:
            return False

        # Check frame counter (should be 0)
        frame_counter = struct.unpack('>I', frame[12:16])[0]
        if frame_counter != 0:
            return False

        # Superframe counter should be reasonable (0 to 2^32-1)
        superframe_counter = struct.unpack('>I', frame[8:12])[0]
        if superframe_counter > 0xFFFFFFFF:
            return False

        return True

    def handle_sync_frame(self, sync_frame: bytes):
        """
        Handle detected sync frame.

        Updates sync state and frame counter.
        """
        if len(sync_frame) < self.SYNC_FRAME_BYTES:
            return

        superframe_counter = struct.unpack('>I', sync_frame[8:12])[0]

        if self.last_sync_counter is None:
            # First sync frame
            self.sync_state = "synced"
            self.superframe_counter = superframe_counter
            self.last_sync_counter = superframe_counter
            print(f"Sync acquired: superframe_counter={superframe_counter}")
        else:
            # Validate counter increment
            expected_counter = (self.last_sync_counter + 1) % 0x100000000
            if superframe_counter == expected_counter or superframe_counter == self.last_sync_counter:
                # Counter is valid
                self.sync_state = "synced"
                self.superframe_counter = superframe_counter
                self.last_sync_counter = superframe_counter
            else:
                # Counter mismatch - sync may be lost
                print(f"Sync warning: expected counter {expected_counter}, got {superframe_counter}")
                self.sync_state = "lost"
                # Still update counter but mark as lost
                self.superframe_counter = superframe_counter
                self.last_sync_counter = superframe_counter

    def parse_frames_with_sync(self, data: bytes, sync_frame_idx: int) -> list[bytes]:
        """
        Parse frames starting from sync frame position.

        Args:
            data: Decoded data
            sync_frame_idx: Index where sync frame starts

        Returns:
            List of frame payloads
        """
        frames = []

        # Skip sync frame
        data_after_sync = data[sync_frame_idx + self.SYNC_FRAME_BYTES:]

        # Parse remaining frames
        # Try both frame sizes (48 bytes with FEC, 49 bytes without FEC)
        frame_size = self.VOICE_FRAME_BYTES_WITH_FEC
        if len(data_after_sync) % frame_size != 0:
            frame_size_alt = self.VOICE_FRAME_BYTES_WITHOUT_FEC
            if len(data_after_sync) % frame_size_alt == 0:
                frame_size = frame_size_alt
        
        for i in range(0, len(data_after_sync), frame_size):
            frame = data_after_sync[i:i+frame_size]
            if len(frame) == frame_size:
                # Skip additional sync frames
                if not self.is_sync_frame(frame):
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
        Verify ECDSA signature (full 64-byte signature).

        Args:
            signature: Full signature bytes (64 bytes: r + s)
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

        # Import verify function
        from python.crypto_helpers import verify_ecdsa_signature
        
        # Verify signature
        try:
            return verify_ecdsa_signature(data, signature, public_key)
        except Exception as e:
            print(f"Error verifying signature for {sender_callsign}: {e}")
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

    def process_superframe(self, frames: list[bytes]) -> Optional[tuple]:
        """
        Process complete superframe.

        Returns:
            Tuple of (opus_frames, status_dict) or None
        """
        if len(frames) < 24:
            # Not enough frames for a superframe - count as error
            # This means we received some frames but not enough to form a complete superframe
            frames_received = len(frames)
            self.total_frames_received += frames_received
            self.frame_error_count += frames_received  # All frames in incomplete superframe are errors
            return None

        # Determine if Frame 0 is present
        # Check if first frame is 64 bytes (auth frame) or 48 bytes (voice frame)
        has_auth_frame = False
        if len(frames) > 0:
            first_frame_size = len(frames[0])
            if first_frame_size == 64:
                # First frame is 64 bytes = auth frame
                has_auth_frame = True
            elif first_frame_size == 48:
                # First frame is 48 bytes = voice frame (no auth)
                has_auth_frame = False
            else:
                # Unknown frame size - check if we have 25 frames (assume first is auth)
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
            # Extract signature (full 64 bytes: r + s)
            signature = auth_payload[:64]  # Full 64-byte signature
            
            # Extract sender from first voice frame
            sender_callsign = ""
            if len(frames) > voice_frames_start:
                first_voice = self.frame_builder.parse_frame(frames[voice_frames_start])
                if first_voice:
                    sender_callsign = first_voice.get('callsign', '').strip()
            
            # Build superframe data for verification
            # IMPORTANT: The signature is generated over the raw Opus data (960 bytes = 24 * 40),
            # not over the frame payloads. We need to extract Opus data from each frame.
            opus_data_list = []
            for frame_payload in frames[voice_frames_start:]:
                try:
                    parsed = self.frame_builder.parse_frame(frame_payload)
                    if parsed:
                        opus_data = parsed.get('opus_data', b'')
                        if opus_data:
                            # Ensure Opus data is exactly 40 bytes (pad/truncate if needed)
                            if len(opus_data) > 40:
                                opus_data = opus_data[:40]
                            elif len(opus_data) < 40:
                                opus_data = opus_data.ljust(40, b'\x00')
                            opus_data_list.append(opus_data)
                        else:
                            # Frame parsed but no Opus data - add zero padding
                            opus_data_list.append(b'\x00' * 40)
                except Exception as e:
                    # Frame failed to parse - add zero padding to maintain frame count
                    print(f"Warning: Failed to parse frame for signature verification: {e}")
                    opus_data_list.append(b'\x00' * 40)
            
            # Ensure we have exactly 24 Opus frames (pad if needed)
            while len(opus_data_list) < 24:
                opus_data_list.append(b'\x00' * 40)
            
            # Concatenate Opus data (this is what was signed on TX)
            # Should be exactly 960 bytes (24 frames * 40 bytes)
            superframe_data = b''.join(opus_data_list[:24])  # Take first 24 frames

            # Debug: Print signature and data info
            print(f"Signature verification: sender={sender_callsign}, signature_len={len(signature)}, superframe_data_len={len(superframe_data)}, opus_frames={len(opus_data_list)}")
            if len(superframe_data) > 0:
                print(f"First 16 bytes of superframe_data: {superframe_data[:16].hex()}")
                print(f"Last 16 bytes of superframe_data: {superframe_data[-16:].hex()}")

            # Verify signature (full 64-byte signature allows proper cryptographic verification)
            if sender_callsign:
                signature_valid = self.verify_signature(signature, superframe_data, sender_callsign)
                print(f"Signature verification result: {signature_valid}")
                if not signature_valid:
                    print("Warning: Signature verification failed")
                    # Note: This may be due to hard-decision decoding errors corrupting the data
                    # However, we report the actual verification result, not a fake pass
                    # If require_signatures is False, we allow processing to continue for analysis
                    # If require_signatures is True, the frame will be rejected below
            else:
                print("Warning: No sender callsign extracted, cannot verify signature")
                signature_valid = False

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

        # Process frames (voice, APRS, text)
        opus_frames = []
        aprs_packets = []
        text_messages = []
        recipients = []
        message_type = "voice"
        encrypted = False
        decrypted_successfully = False
        frames_with_valid_mac = 0
        frames_with_encryption = 0

        frames_failed_to_parse = 0
        frames_failed_mac = 0
        for i, frame_payload in enumerate(frames[voice_frames_start:], start=1):
            try:
                parsed = self.frame_builder.parse_frame(frame_payload)
            except (ValueError, Exception) as e:
                # Frame failed to parse - count as error
                frames_failed_to_parse += 1
                print(f"Warning: Frame {i} failed to parse: {e}")
                continue

            if not parsed:
                frames_failed_to_parse += 1
                print(f"Warning: Frame {i} returned None from parse_frame")
                continue

            frame_type = parsed.get('frame_type', self.frame_builder.FRAME_TYPE_VOICE)
            mac = parsed.get('mac', b'\x00' * 8)
            frame_callsign = parsed.get('callsign', '').strip()
            # Use frame index as frame_counter (matches TX side frame_num 1-24)
            frame_counter = i
            
            # Extract data based on frame type
            if frame_type == self.frame_builder.FRAME_TYPE_VOICE:
                frame_data = parsed.get('opus_data', b'')
            elif frame_type == self.frame_builder.FRAME_TYPE_APRS:
                frame_data = parsed.get('aprs_data', b'')
            elif frame_type == self.frame_builder.FRAME_TYPE_TEXT:
                frame_data = parsed.get('text_data', b'')
            else:
                frame_data = parsed.get('data', b'')

            # Verify MAC if present and MAC key is available
            mac_valid = True
            frame_encrypted = False
            if mac != b'\x00' * len(mac):
                encrypted = True  # At least one frame has encryption
                frame_encrypted = True
                frames_with_encryption += 1
                # MAC present - verify it using MAC key
                if self.mac_key and len(self.mac_key) == 32:
                    # Recompute MAC using same data as TX side
                    # MAC covers: frame_type + data[:39] + callsign + frame_counter
                    # Ensure frame_data is exactly 39 bytes (pad/truncate if needed)
                    mac_frame_data = frame_data[:39] if len(frame_data) >= 39 else frame_data.ljust(39, b'\x00')
                    mac_data = (
                        bytes([frame_type]) +
                        mac_frame_data +  # First 39 bytes of data (matches TX side)
                        get_callsign_bytes(frame_callsign) +
                        bytes([frame_counter])
                    )
                    # Verify MAC
                    try:
                        mac_valid = verify_chacha20_mac(mac_data, mac, self.mac_key)
                        if mac_valid:
                            frames_with_valid_mac += 1
                        else:
                            frames_failed_mac += 1
                            print(f"Warning: Frame {i} MAC verification failed")
                    except Exception as e:
                        print(f"Warning: Error verifying MAC for frame {i}: {e}")
                        mac_valid = False
                        frames_failed_mac += 1
                else:
                    # MAC present but no key - use heuristic check
                    if mac == b'\x00' * len(mac) or mac == b'\xFF' * len(mac):
                        frames_failed_mac += 1
                        mac_valid = False
                    else:
                        # MAC looks valid but can't verify without key
                        frames_with_valid_mac += 1

            # Skip corrupted frames (failed MAC check)
            if not mac_valid:
                print(f"Warning: Frame {i} failed MAC check, skipping")
                continue
            
            # Route based on frame type
            frame_produced_output = False
            if frame_type == self.frame_builder.FRAME_TYPE_VOICE:
                opus_data = parsed.get('opus_data', b'')
                # Add Opus data if present (even if zero, as silence is valid)
                if opus_data:
                    # Ensure Opus data is exactly 40 bytes (pad/truncate if needed)
                    if len(opus_data) > 40:
                        opus_data = opus_data[:40]
                    elif len(opus_data) < 40:
                        opus_data = opus_data.ljust(40, b'\x00')
                    opus_frames.append(opus_data)
                    frame_produced_output = True
                else:
                    # If parse_frame didn't extract opus_data, add zero padding to maintain frame count
                    print(f"Warning: Frame {i} has no Opus data, adding zero padding")
                    opus_frames.append(b'\x00' * 40)
                    frame_produced_output = True  # Count as output to maintain frame count
            elif frame_type == self.frame_builder.FRAME_TYPE_APRS:
                aprs_data = parsed.get('aprs_data', b'')
                if aprs_data:
                    aprs_packets.append(aprs_data)
                    frame_produced_output = True
            elif frame_type == self.frame_builder.FRAME_TYPE_TEXT:
                text_data = parsed.get('text_data', b'')
                if text_data:
                    text_messages.append(text_data)
                    frame_produced_output = True
            
            # Track frames that parsed but didn't produce output
            if not frame_produced_output:
                # Frame was parsed successfully but didn't produce any output
                # This indicates corruption or invalid data
                frames_failed_to_parse += 1  # Count as parse failure (no valid data extracted)

        # Track frame errors
        # Count frames that failed to parse or failed MAC verification
        frames_in_superframe = len(frames)
        frames_successfully_parsed = len(opus_frames) + len(aprs_packets) + len(text_messages)
        # Count all failures: parse failures + MAC failures + frames with no output
        # frames_with_no_output = frames that were parsed but didn't produce any output
        # This happens when a frame is parsed but opus_data/aprs_data/text_data is empty
        # Note: frames_failed_to_parse now includes frames that parsed but produced no output
        frames_with_no_output = max(0, frames_in_superframe - frames_successfully_parsed - frames_failed_to_parse - frames_failed_mac)
        total_frame_errors = frames_failed_to_parse + frames_failed_mac + frames_with_no_output
        
        # Additional safeguard: If we received frames but got no output at all, count them as errors
        if frames_in_superframe > 0 and frames_successfully_parsed == 0:
            # All frames in this superframe failed to produce any output
            # This should already be captured by frames_failed_to_parse + frames_failed_mac,
            # but if those are 0 (frames parsed but no data extracted), count them as errors
            if total_frame_errors == 0:
                # All frames were received and parsed but none produced output - count all as errors
                total_frame_errors = frames_in_superframe
        
        self.total_frames_received += frames_in_superframe
        self.frame_error_count += total_frame_errors
        
        # CRITICAL FIX: Calculate errors directly from the difference between
        # total_frames_received and successfully decoded frames (Opus frames).
        # This is more accurate than per-superframe error counting because
        # parse_frame always extracts data even from corrupted frames.
        # For voice-only tests: errors = total_frames_received - opus_frames_decoded
        # We need to track cumulative opus_frames_decoded separately
        if not hasattr(self, '_cumulative_opus_frames'):
            self._cumulative_opus_frames = 0
        self._cumulative_opus_frames += len(opus_frames)
        
        # Recalculate frame_error_count based on actual difference
        # This ensures errors = total_frames_received - successfully_decoded_frames
        # Account for APRS/text frames which are valid but not Opus
        if not hasattr(self, '_cumulative_aprs_text'):
            self._cumulative_aprs_text = 0
        self._cumulative_aprs_text += len(aprs_packets) + len(text_messages)
        
        # Errors = total received - successfully decoded Opus frames
        # For voice-only tests, APRS/text frames are likely misclassified corrupted frames
        # So we only count Opus frames as successful, not APRS/text
        # This gives us: errors = total_frames_received - opus_frames_decoded
        calculated_errors = max(0, self.total_frames_received - self._cumulative_opus_frames)
        # Use the larger of the two (per-superframe counting vs direct calculation)
        # This ensures we don't undercount errors
        self.frame_error_count = max(self.frame_error_count, calculated_errors)
        
        # Ensure we have exactly 24 Opus frames (pad if needed)
        # This maintains frame count even if one frame is corrupted
        expected_voice_frames = 24
        while len(opus_frames) < expected_voice_frames:
            print(f"Warning: Only {len(opus_frames)} Opus frames extracted, padding to {expected_voice_frames}")
            opus_frames.append(b'\x00' * 40)
        
        # Build status (AFTER recalculating frame_error_count and padding)
        status = {
            'signature_valid': signature_valid,
            'encrypted': encrypted,
            'decrypted_successfully': decrypted_successfully,
            'sender': sender_callsign,
            'recipients': ','.join(recipients) if recipients else '',
            'message_type': message_type,
            'frame_counter': len(opus_frames),
            'frame_error_count': self.frame_error_count,  # Cumulative errors
            'total_frames_received': self.total_frames_received,  # Cumulative total
            'aprs_count': len(aprs_packets),
            'text_count': len(text_messages),
            'superframe_counter': self.superframe_counter,
            'sync_state': self.sync_state
        }

        self.superframe_counter += 1
        # Emit APRS packets
        if aprs_packets:
            aprs_data = b''.join(aprs_packets)
            aprs_pmt = pmt.init_u8vector(len(aprs_data), list(aprs_data))
            aprs_meta = pmt.make_dict()
            aprs_meta = pmt.dict_add(aprs_meta, pmt.intern("sender"), pmt.intern(sender_callsign))
            aprs_meta = pmt.dict_add(aprs_meta, pmt.intern("message_type"), pmt.intern("aprs"))
            aprs_meta = pmt.dict_add(aprs_meta, pmt.intern("packet_count"), pmt.from_long(len(aprs_packets)))
            self.message_port_pub(pmt.intern("aprs_out"), pmt.cons(aprs_meta, aprs_pmt))
        
        # Emit text messages
        if text_messages:
            text_data = b''.join(text_messages)
            text_pmt = pmt.init_u8vector(len(text_data), list(text_data))
            text_meta = pmt.make_dict()
            text_meta = pmt.dict_add(text_meta, pmt.intern("sender"), pmt.intern(sender_callsign))
            text_meta = pmt.dict_add(text_meta, pmt.intern("message_type"), pmt.intern("text"))
            text_meta = pmt.dict_add(text_meta, pmt.intern("message_count"), pmt.from_long(len(text_messages)))
            self.message_port_pub(pmt.intern("text_out"), pmt.cons(text_meta, text_pmt))

        return (opus_frames, status)

    def __del__(self):
        """Cleanup method to remove instance from class instances list"""
        # Clear buffers to free memory
        try:
            self.frame_buffer = []
            if hasattr(self, 'status_messages'):
                self.status_messages = []
        except:
            pass
        
        if hasattr(type(self), '_instances'):
            try:
                type(self)._instances.remove(self)
            except (ValueError, AttributeError):
                pass
    
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
        status_pmt = pmt.dict_add(status_pmt, pmt.intern("sync_state"),
                                  pmt.intern(status.get('sync_state', 'unknown')))
        
        # Add error tracking
        if 'frame_error_count' in status:
            status_pmt = pmt.dict_add(status_pmt, pmt.intern("frame_error_count"),
                                      pmt.from_long(status.get('frame_error_count', 0)))
        if 'total_frames_received' in status:
            status_pmt = pmt.dict_add(status_pmt, pmt.intern("total_frames_received"),
                                      pmt.from_long(status.get('total_frames_received', 0)))

        self.message_port_pub(pmt.intern("status"), status_pmt)


def make_sleipnir_superframe_parser(
    local_callsign: str = "N0CALL",
    private_key_path: Optional[str] = None,
    require_signatures: bool = False,
    public_key_store_path: Optional[str] = None,
    enable_sync_detection: bool = True,
    mac_key: Optional[bytes] = None
):
    """Factory function for GRC."""
    return sleipnir_superframe_parser(
        local_callsign=local_callsign,
        private_key_path=private_key_path,
        require_signatures=require_signatures,
        public_key_store_path=public_key_store_path,
        enable_sync_detection=enable_sync_detection,
        mac_key=mac_key
    )

