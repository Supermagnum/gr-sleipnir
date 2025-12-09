#!/usr/bin/env python3
"""
Frame-aware LDPC encoder/decoder for gr-sleipnir superframe structure.

Switches between LDPC matrices based on frame number:
- Frame 0: Authentication frame (rate 1/3, 768 bits)
- Frames 1-24: Voice frames (rate 2/3, 576 bits)
"""

import numpy as np
from gnuradio import gr
import os

try:
    from gnuradio import fec
    FEC_AVAILABLE = True
except ImportError:
    FEC_AVAILABLE = False
    print("Warning: GNU Radio FEC module not available")

class frame_aware_ldpc_encoder(gr.sync_block):
    """
    Frame-aware LDPC encoder that switches matrices based on frame number.

    Input: Bytes (frame data) + frame number tag
    Output: Bytes (LDPC encoded)
    """

    def __init__(self, auth_matrix_file, voice_matrix_file, superframe_size=25):
        """
        Initialize frame-aware LDPC encoder

        Args:
            auth_matrix_file: Path to authentication frame LDPC matrix (rate 1/3)
            voice_matrix_file: Path to voice frame LDPC matrix (rate 2/3)
            superframe_size: Number of frames in superframe (default: 25)
        """
        gr.sync_block.__init__(
            self,
            name="frame_aware_ldpc_encoder",
            in_sig=[np.uint8],
            out_sig=[np.uint8]
        )

        self.auth_matrix_file = auth_matrix_file
        self.voice_matrix_file = voice_matrix_file
        self.superframe_size = superframe_size
        self.current_frame = 0

        # Initialize encoders
        if FEC_AVAILABLE:
            try:
                if os.path.exists(auth_matrix_file):
                    self.auth_encoder = fec.ldpc_encoder_make(auth_matrix_file)
                else:
                    print(f"Warning: Auth matrix file not found: {auth_matrix_file}")
                    self.auth_encoder = None

                if os.path.exists(voice_matrix_file):
                    self.voice_encoder = fec.ldpc_encoder_make(voice_matrix_file)
                else:
                    print(f"Warning: Voice matrix file not found: {voice_matrix_file}")
                    self.voice_encoder = None
            except Exception as e:
                print(f"Error initializing LDPC encoders: {e}")
                self.auth_encoder = None
                self.voice_encoder = None
        else:
            self.auth_encoder = None
            self.voice_encoder = None

        # Frame buffer
        self.frame_buffer = bytearray()
        self.frame_counter = 0

    def work(self, input_items, output_items):
        """
        Process input and encode with appropriate LDPC matrix
        """
        in0 = input_items[0]
        out = output_items[0]

        # Add input to buffer
        self.frame_buffer.extend(in0.tobytes())

        output_idx = 0

        # Determine frame type and encode
        # Frame 0: 256 bits (32 bytes) -> 768 bits (96 bytes) with rate 1/3
        # Frames 1-24: 384 bits (48 bytes) -> 576 bits (72 bytes) with rate 2/3

        while output_idx < len(out):
            if self.frame_counter == 0:
                # Authentication frame
                if len(self.frame_buffer) < 32:  # Need 256 bits = 32 bytes
                    break

                frame_data = bytes(self.frame_buffer[:32])
                self.frame_buffer = self.frame_buffer[32:]

                if self.auth_encoder is not None:
                    try:
                        encoded = self.auth_encoder.encode(frame_data)
                        if output_idx + len(encoded) <= len(out):
                            out[output_idx:output_idx + len(encoded)] = np.frombuffer(encoded, dtype=np.uint8)
                            output_idx += len(encoded)
                        else:
                            # Not enough space, put back
                            self.frame_buffer = bytearray(frame_data) + self.frame_buffer
                            break
                    except Exception as e:
                        print(f"LDPC encoding error (auth): {e}")
                        # Pass through without encoding if error
                        if output_idx + len(frame_data) <= len(out):
                            out[output_idx:output_idx + len(frame_data)] = np.frombuffer(frame_data, dtype=np.uint8)
                            output_idx += len(frame_data)
                else:
                    # No encoder, pass through
                    if output_idx + len(frame_data) <= len(out):
                        out[output_idx:output_idx + len(frame_data)] = np.frombuffer(frame_data, dtype=np.uint8)
                        output_idx += len(frame_data)

                self.frame_counter = (self.frame_counter + 1) % self.superframe_size

            else:
                # Voice frame
                if len(self.frame_buffer) < 48:  # Need 384 bits = 48 bytes
                    break

                frame_data = bytes(self.frame_buffer[:48])
                self.frame_buffer = self.frame_buffer[48:]

                if self.voice_encoder is not None:
                    try:
                        encoded = self.voice_encoder.encode(frame_data)
                        if output_idx + len(encoded) <= len(out):
                            out[output_idx:output_idx + len(encoded)] = np.frombuffer(encoded, dtype=np.uint8)
                            output_idx += len(encoded)
                        else:
                            # Not enough space, put back
                            self.frame_buffer = bytearray(frame_data) + self.frame_buffer
                            break
                    except Exception as e:
                        print(f"LDPC encoding error (voice): {e}")
                        # Pass through without encoding if error
                        if output_idx + len(frame_data) <= len(out):
                            out[output_idx:output_idx + len(frame_data)] = np.frombuffer(frame_data, dtype=np.uint8)
                            output_idx += len(frame_data)
                else:
                    # No encoder, pass through
                    if output_idx + len(frame_data) <= len(out):
                        out[output_idx:output_idx + len(frame_data)] = np.frombuffer(frame_data, dtype=np.uint8)
                        output_idx += len(frame_data)

                self.frame_counter = (self.frame_counter + 1) % self.superframe_size

        return output_idx

class frame_aware_ldpc_decoder(gr.sync_block):
    """
    Frame-aware LDPC decoder that switches matrices based on frame number.

    Input: Bytes (LDPC encoded) + frame number detection
    Output: Bytes (decoded frame data)
    """

    def __init__(self, auth_matrix_file, voice_matrix_file, superframe_size=25, max_iter=20):
        """
        Initialize frame-aware LDPC decoder

        Args:
            auth_matrix_file: Path to authentication frame LDPC matrix (rate 1/3)
            voice_matrix_file: Path to voice frame LDPC matrix (rate 2/3)
            superframe_size: Number of frames in superframe (default: 25)
            max_iter: Maximum LDPC decoding iterations
        """
        gr.sync_block.__init__(
            self,
            name="frame_aware_ldpc_decoder",
            in_sig=[np.float32],  # Soft decisions (LLRs)
            out_sig=[np.uint8]
        )

        self.auth_matrix_file = auth_matrix_file
        self.voice_matrix_file = voice_matrix_file
        self.superframe_size = superframe_size
        self.max_iter = max_iter
        self.current_frame = 0

        # Initialize decoders
        if FEC_AVAILABLE:
            try:
                if os.path.exists(auth_matrix_file):
                    self.auth_decoder = fec.ldpc_decoder.make(auth_matrix_file, max_iter)
                else:
                    print(f"Warning: Auth matrix file not found: {auth_matrix_file}")
                    self.auth_decoder = None

                if os.path.exists(voice_matrix_file):
                    self.voice_decoder = fec.ldpc_decoder.make(voice_matrix_file, max_iter)
                else:
                    print(f"Warning: Voice matrix file not found: {voice_matrix_file}")
                    self.voice_decoder = None
            except Exception as e:
                print(f"Error initializing LDPC decoders: {e}")
                self.auth_decoder = None
                self.voice_decoder = None
        else:
            self.auth_decoder = None
            self.voice_decoder = None

        # Frame buffer
        self.frame_buffer = []
        self.frame_counter = 0

    def work(self, input_items, output_items):
        """
        Process input and decode with appropriate LDPC matrix
        """
        in0 = input_items[0]
        out = output_items[0]

        # Add input to buffer (soft decisions)
        self.frame_buffer.extend(in0.tolist())

        output_idx = 0

        # Determine frame type and decode
        # Frame 0: 768 bits (96 bytes) -> 256 bits (32 bytes) with rate 1/3
        # Frames 1-24: 576 bits (72 bytes) -> 384 bits (48 bytes) with rate 2/3

        while output_idx < len(out):
            if self.frame_counter == 0:
                # Authentication frame - need 768 soft bits
                if len(self.frame_buffer) < 768:
                    break

                soft_bits = np.array(self.frame_buffer[:768], dtype=np.float32)
                self.frame_buffer = self.frame_buffer[768:]

                if self.auth_decoder is not None:
                    try:
                        decoded = self.auth_decoder.decode(soft_bits)
                        if output_idx + len(decoded) <= len(out):
                            out[output_idx:output_idx + len(decoded)] = np.frombuffer(decoded, dtype=np.uint8)
                            output_idx += len(decoded)
                        else:
                            # Not enough space, put back
                            self.frame_buffer = soft_bits.tolist() + self.frame_buffer
                            break
                    except Exception as e:
                        print(f"LDPC decoding error (auth): {e}")
                        # Hard decision fallback
                        hard_bits = (soft_bits > 0).astype(np.uint8)
                        decoded = hard_bits[:32].tobytes()
                        if output_idx + len(decoded) <= len(out):
                            out[output_idx:output_idx + len(decoded)] = np.frombuffer(decoded, dtype=np.uint8)
                            output_idx += len(decoded)
                else:
                    # No decoder, hard decision
                    hard_bits = (soft_bits > 0).astype(np.uint8)
                    decoded = hard_bits[:32].tobytes()
                    if output_idx + len(decoded) <= len(out):
                        out[output_idx:output_idx + len(decoded)] = np.frombuffer(decoded, dtype=np.uint8)
                        output_idx += len(decoded)

                self.frame_counter = (self.frame_counter + 1) % self.superframe_size

            else:
                # Voice frame - need 576 soft bits
                if len(self.frame_buffer) < 576:
                    break

                soft_bits = np.array(self.frame_buffer[:576], dtype=np.float32)
                self.frame_buffer = self.frame_buffer[576:]

                if self.voice_decoder is not None:
                    try:
                        decoded = self.voice_decoder.decode(soft_bits)
                        if output_idx + len(decoded) <= len(out):
                            out[output_idx:output_idx + len(decoded)] = np.frombuffer(decoded, dtype=np.uint8)
                            output_idx += len(decoded)
                        else:
                            # Not enough space, put back
                            self.frame_buffer = soft_bits.tolist() + self.frame_buffer
                            break
                    except Exception as e:
                        print(f"LDPC decoding error (voice): {e}")
                        # Hard decision fallback
                        hard_bits = (soft_bits > 0).astype(np.uint8)
                        decoded = hard_bits[:48].tobytes()
                        if output_idx + len(decoded) <= len(out):
                            out[output_idx:output_idx + len(decoded)] = np.frombuffer(decoded, dtype=np.uint8)
                            output_idx += len(decoded)
                else:
                    # No decoder, hard decision
                    hard_bits = (soft_bits > 0).astype(np.uint8)
                    decoded = hard_bits[:48].tobytes()
                    if output_idx + len(decoded) <= len(out):
                        out[output_idx:output_idx + len(decoded)] = np.frombuffer(decoded, dtype=np.uint8)
                        output_idx += len(decoded)

                self.frame_counter = (self.frame_counter + 1) % self.superframe_size

        return output_idx


def make_frame_aware_ldpc_encoder(auth_matrix_file, voice_matrix_file, superframe_size=25):
    """Factory function for GRC."""
    return frame_aware_ldpc_encoder(auth_matrix_file, voice_matrix_file, superframe_size)


def make_frame_aware_ldpc_decoder(auth_matrix_file, voice_matrix_file, superframe_size=25, max_iter=20):
    """Factory function for GRC."""
    return frame_aware_ldpc_decoder(auth_matrix_file, voice_matrix_file, superframe_size, max_iter)

