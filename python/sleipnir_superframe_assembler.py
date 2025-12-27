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
    encrypt_chacha20_poly1305,
    get_callsign_bytes
)
from python.voice_frame_builder import VoiceFrameBuilder


class sleipnir_superframe_assembler(gr.basic_block):
    """
    Assembles superframes from Opus frames.

    Input: PDU with list of 24 Opus frames (40 bytes each)
    Output: PDU with list of frame payloads ready for LDPC encoding
    
    This is a message-only block (no stream ports), so we use basic_block instead of sync_block.
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
        gr.basic_block.__init__(
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
        
        # Store reference to self to prevent garbage collection issues
        # This helps prevent segfaults when GNU Radio gateway accesses the block
        self._self_ref = self
        
        # Store instance in class-level list to prevent garbage collection
        # This ensures the Python object stays alive even if local references are cleared
        if not hasattr(type(self), '_instances'):
            type(self)._instances = []
        type(self)._instances.append(self)

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
            print("Superframe assembler: Received non-pair message")
            return

        meta = pmt.car(msg)
        data = pmt.cdr(msg)

        # Extract Opus frames from PDU
        # Handle different PMT types that tagged_stream_to_pdu might produce
        opus_data = None
        try:
            if pmt.is_u8vector(data):
                opus_data = bytes(pmt.u8vector_elements(data))
            elif pmt.is_blob(data):
                opus_data = pmt.to_python(data)
            elif pmt.is_uniform_vector(data):
                # Handle uniform vectors (might be short vector from char_to_short conversion)
                # Convert to Python first, then handle numpy arrays
                python_data = pmt.to_python(data)
                if isinstance(python_data, np.ndarray):
                    # Handle numpy arrays (from uniform vector conversion)
                    # If it's int16 (itemsize 2), convert to uint8
                    if python_data.dtype in [np.int16, np.int32]:
                        opus_data = python_data.astype(np.uint8).tobytes()
                    else:
                        opus_data = python_data.astype(np.uint8).tobytes()
                elif isinstance(python_data, list):
                    # Convert list to bytes (handle both int and bytes)
                    opus_data = bytes([b & 0xFF if isinstance(b, int) else b for b in python_data])
                else:
                    print(f"Superframe assembler: Unsupported uniform vector type: {type(python_data)}")
                    return
            else:
                # Try generic conversion for other PMT types
                try:
                    python_data = pmt.to_python(data)
                    if isinstance(python_data, bytes):
                        opus_data = python_data
                    elif isinstance(python_data, np.ndarray):
                        # Handle numpy arrays (from uniform vector conversion)
                        opus_data = python_data.astype(np.uint8).tobytes()
                    elif isinstance(python_data, list):
                        # Convert list to bytes (handle both int and bytes)
                        opus_data = bytes([b & 0xFF if isinstance(b, int) else b for b in python_data])
                    elif isinstance(python_data, (int, float)):
                        # Single value - shouldn't happen but handle gracefully
                        print(f"Superframe assembler: Received single value instead of data: {python_data}")
                        return
                    else:
                        print(f"Superframe assembler: Unexpected data type after conversion: {type(python_data)}")
                        return
                except Exception as e:
                    print(f"Superframe assembler: Error converting data: {e}, type: {type(data)}")
                    return
            
            if opus_data is None:
                print(f"Superframe assembler: Could not extract data from PDU, type: {type(data)}")
                return
        except Exception as e:
            print(f"Superframe assembler: Error processing PDU: {e}, type: {type(data)}")
            import traceback
            traceback.print_exc()
            return

        print(f"Superframe assembler: Received {len(opus_data)} bytes of Opus data")

        # Expect 24 frames of 40 bytes each = 960 bytes
        expected_size = 24 * 40
        
        # Accumulate frames until we have enough for a superframe
        if not hasattr(self, '_opus_frame_buffer'):
            self._opus_frame_buffer = bytearray()
        
        self._opus_frame_buffer.extend(opus_data)
        
        # Check if we have enough for a superframe
        if len(self._opus_frame_buffer) < expected_size:
            print(f"Superframe assembler: Accumulating frames ({len(self._opus_frame_buffer)}/{expected_size} bytes)")
            return  # Wait for more data
        
        # Extract exactly one superframe worth of data
        superframe_data = bytes(self._opus_frame_buffer[:expected_size])
        self._opus_frame_buffer = self._opus_frame_buffer[expected_size:]
        
        print(f"Superframe assembler: Processing superframe with {len(superframe_data)} bytes")

        # Split into 24 frames
        opus_frames = [superframe_data[i:i+40] for i in range(0, len(superframe_data), 40)]
        print(f"Superframe assembler: Split into {len(opus_frames)} frames")

        # Assemble superframe
        try:
            frame_payloads = self.assemble_superframe(opus_frames)

            # Convert to PMT
            payload_bytes = b''.join(frame_payloads)
            # Use array.array for more efficient conversion (avoids creating large list)
            import array
            payload_array = array.array('B', payload_bytes)
            output_pmt = pmt.init_u8vector(len(payload_bytes), payload_array)

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
        - Bytes 0-7:   Sync pattern (64 bits, fixed value, unencrypted)
        - Bytes 8-40:  Payload (33 bytes): superframe counter + frame counter + padding
                       (encrypted if encryption enabled, plaintext otherwise)
        - Bytes 41-48: MAC (8 bytes, truncated from 16-byte Poly1305 tag)

        The sync pattern remains unencrypted to allow receiver detection.
        The payload (counters) is encrypted if encryption is enabled.
        MAC provides integrity verification for the payload.
        """
        sync_frame = bytearray(self.SYNC_FRAME_BYTES)

        # Sync pattern (64 bits = 8 bytes) - always unencrypted for detection
        struct.pack_into('>Q', sync_frame, 0, self.SYNC_PATTERN)

        # Build payload: superframe counter + frame counter + padding
        payload = bytearray(33)  # 33 bytes for payload
        struct.pack_into('>I', payload, 0, self.superframe_counter)  # 4 bytes
        struct.pack_into('>I', payload, 4, 0)  # Frame counter (always 0 for sync frame, 4 bytes)
        # Bytes 8-32: Padding (25 bytes, already zeros)

        # Encrypt payload if encryption is enabled
        if self.enable_encryption and self.mac_key and len(self.mac_key) == 32:
            try:
                # Encrypt payload using ChaCha20-Poly1305
                # Use fixed nonce (all zeros) for sync frames since we can't use counter
                # (counter is inside encrypted payload, creating chicken-and-egg problem)
                nonce = b'\x00' * 12  # Fixed 12-byte nonce for sync frames
                ciphertext, mac_full = encrypt_chacha20_poly1305(bytes(payload), self.mac_key, nonce)
                
                # Store encrypted payload (33 bytes)
                if len(ciphertext) > 33:
                    ciphertext = ciphertext[:33]
                elif len(ciphertext) < 33:
                    ciphertext = ciphertext.ljust(33, b'\x00')
                sync_frame[8:41] = ciphertext
                
                # Store MAC (8 bytes, truncated from 16)
                sync_frame[41:49] = mac_full[:8]
            except Exception as e:
                print(f"Warning: Error encrypting sync frame: {e}, using plaintext")
                # Fall back to plaintext with MAC
                sync_frame[8:41] = payload
                if self.mac_key and len(self.mac_key) == 32:
                    # Compute MAC for plaintext payload
                    mac_data = bytes(payload)
                    mac_full = compute_chacha20_mac(mac_data, self.mac_key)
                    sync_frame[41:49] = mac_full[:8]
                else:
                    sync_frame[41:49] = b'\x00' * 8
        elif self.mac_key and len(self.mac_key) == 32:
            # MAC only (no encryption)
            sync_frame[8:41] = payload
            # Compute MAC for plaintext payload
            mac_data = bytes(payload)
            mac_full = compute_chacha20_mac(mac_data, self.mac_key)
            sync_frame[41:49] = mac_full[:8]
        else:
            # No encryption, no MAC - use original structure for backward compatibility
            sync_frame[8:41] = payload
            sync_frame[41:49] = b'\x00' * 8

        return bytes(sync_frame)
    
    def __del__(self):
        """Cleanup method to release resources"""
        # Remove from class instances list
        if hasattr(type(self), '_instances'):
            try:
                type(self)._instances.remove(self)
            except (ValueError, AttributeError):
                pass

    def build_auth_frame(self, superframe_data: bytes) -> bytes:
        """
        Build authentication frame payload.
        
        The full ECDSA signature is 64 bytes (r + s, each 32 bytes).
        Auth frame after LDPC decoding is 64 bytes (512 bits) using ldpc_auth_1536_512.alist.
        We store the full 64-byte signature for proper cryptographic verification.
        """
        try:
            signature = generate_ecdsa_signature(superframe_data, self.private_key)
            # Ensure signature is exactly 64 bytes (r + s concatenated)
            if len(signature) > 64:
                signature = signature[:64]  # Truncate if somehow longer
            elif len(signature) < 64:
                signature = signature.ljust(64, b'\x00')  # Pad if shorter
            
            # Store full 64-byte signature (r + s)
            return signature
        except Exception as e:
            print(f"Error building auth frame: {e}")
            return b'\x00' * 64

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

