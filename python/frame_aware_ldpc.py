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

        # Initialize encoders (lazy initialization to avoid memory issues)
        # Store file paths and create encoders on first use
        self.auth_encoder = None
        self.voice_encoder = None
        self._auth_encoder_created = False
        self._voice_encoder_created = False
        
        if FEC_AVAILABLE:
            self.auth_matrix_file = auth_matrix_file
            self.voice_matrix_file = voice_matrix_file
        else:
            self.auth_matrix_file = None
            self.voice_matrix_file = None

        # Frame buffer
        self.frame_buffer = bytearray()
        self.frame_counter = 0

    def _ensure_auth_encoder(self):
        """Lazy initialization of auth encoder to avoid memory issues."""
        if not self._auth_encoder_created and FEC_AVAILABLE and self.auth_matrix_file:
            try:
                if os.path.exists(self.auth_matrix_file):
                    self.auth_encoder = fec.ldpc_encoder_make(self.auth_matrix_file)
                    self._auth_encoder_created = True
                else:
                    print(f"Warning: Auth matrix file not found: {self.auth_matrix_file}")
            except Exception as e:
                print(f"Error initializing auth LDPC encoder: {e}")
    
    def _ensure_voice_encoder(self):
        """Lazy initialization of voice encoder to avoid memory issues."""
        if not self._voice_encoder_created and FEC_AVAILABLE and self.voice_matrix_file:
            try:
                if os.path.exists(self.voice_matrix_file):
                    self.voice_encoder = fec.ldpc_encoder_make(self.voice_matrix_file)
                    self._voice_encoder_created = True
                else:
                    print(f"Warning: Voice matrix file not found: {self.voice_matrix_file}")
            except Exception as e:
                print(f"Error initializing voice LDPC encoder: {e}")

    def work(self, input_items, output_items):
        """
        Process input and encode with appropriate LDPC matrix
        """
        # Ensure encoders are initialized before use
        if not self._auth_encoder_created:
            self._ensure_auth_encoder()
        if not self._voice_encoder_created:
            self._ensure_voice_encoder()
            
        in0 = input_items[0]
        out = output_items[0]

        # Add input to buffer
        if len(in0) > 0:
            self.frame_buffer.extend(in0.tobytes())

        output_idx = 0
        input_consumed = 0

        # Determine frame type and encode
        # Frame 0: 256 bits (32 bytes) -> 768 bits (96 bytes) with rate 1/3
        # Frames 1-24: 384 bits (48 bytes) -> 576 bits (72 bytes) with rate 2/3
        # For sync_block, we need 1:1 input/output ratio
        # So we'll process only what we can output

        while output_idx < noutput and len(self.frame_buffer) > 0:
            if self.frame_counter == 0:
                # Authentication frame
                if len(self.frame_buffer) < 32:  # Need 256 bits = 32 bytes
                    break
                
                # Ensure encoder is created
                self._ensure_auth_encoder()

                frame_data = bytes(self.frame_buffer[:32])
                self.frame_buffer = self.frame_buffer[32:]

                # FEC encoder is a GNU Radio block, not a callable
                # For now, pass through without encoding (will be fixed in architecture)
                # TODO: Integrate FEC blocks properly in hierarchical flowgraph
                if output_idx + len(frame_data) <= len(out):
                    # Pass through (no encoding for now)
                    out[output_idx:output_idx + len(frame_data)] = np.frombuffer(frame_data, dtype=np.uint8)
                    output_idx += len(frame_data)
                else:
                    # Not enough space, put back
                    self.frame_buffer = bytearray(frame_data) + self.frame_buffer
                    break

                self.frame_counter = (self.frame_counter + 1) % self.superframe_size

            else:
                # Voice frame
                if len(self.frame_buffer) < 48:  # Need 384 bits = 48 bytes
                    break
                
                # Ensure encoder is created
                self._ensure_voice_encoder()

                frame_data = bytes(self.frame_buffer[:48])
                self.frame_buffer = self.frame_buffer[48:]
                input_consumed += 48

                # FEC encoder is a GNU Radio block, not a callable
                # For now, pass through without encoding (will be fixed in architecture)
                # TODO: Integrate FEC blocks properly in hierarchical flowgraph
                if output_idx + len(frame_data) <= len(out):
                    # Pass through (no encoding for now)
                    out[output_idx:output_idx + len(frame_data)] = np.frombuffer(frame_data, dtype=np.uint8)
                    output_idx += len(frame_data)
                else:
                    # Not enough space, put back
                    self.frame_buffer = bytearray(frame_data) + self.frame_buffer
                    break

                self.frame_counter = (self.frame_counter + 1) % self.superframe_size

        # For sync_block, return number of output items produced
        # Since sync_block requires 1:1 ratio, we return min of what we produced and input length
        # This ensures we don't get stuck
        return min(output_idx, ninput) if output_idx > 0 else min(1, ninput)
    

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

        # Initialize decoders (lazy initialization to avoid memory issues)
        # Store file paths and create decoders on first use
        self.auth_decoder = None
        self.voice_decoder = None
        self._auth_decoder_created = False
        self._voice_decoder_created = False
        
        if FEC_AVAILABLE:
            self.auth_matrix_file = auth_matrix_file
            self.voice_matrix_file = voice_matrix_file
            self.max_iter = max_iter
        else:
            self.auth_matrix_file = None
            self.voice_matrix_file = None
            self.max_iter = max_iter

        # Frame buffer
        self.frame_buffer = []
        self.frame_counter = 0

    def _ensure_auth_decoder(self):
        """Lazy initialization of auth decoder to avoid memory issues."""
        if not self._auth_decoder_created and FEC_AVAILABLE and self.auth_matrix_file:
            try:
                if os.path.exists(self.auth_matrix_file):
                    self.auth_decoder = fec.ldpc_decoder_make(self.auth_matrix_file, self.max_iter)
                    self._auth_decoder_created = True
                else:
                    print(f"Warning: Auth matrix file not found: {self.auth_matrix_file}")
            except Exception as e:
                print(f"Error initializing auth LDPC decoder: {e}")
    
    def _ensure_voice_decoder(self):
        """Lazy initialization of voice decoder to avoid memory issues."""
        if not self._voice_decoder_created and FEC_AVAILABLE and self.voice_matrix_file:
            try:
                if os.path.exists(self.voice_matrix_file):
                    self.voice_decoder = fec.ldpc_decoder_make(self.voice_matrix_file, self.max_iter)
                    self._voice_decoder_created = True
                else:
                    print(f"Warning: Voice matrix file not found: {self.voice_matrix_file}")
            except Exception as e:
                print(f"Error initializing voice LDPC decoder: {e}")

    def work(self, input_items, output_items):
        """
        Process input and decode with appropriate LDPC matrix
        """
        # Ensure decoders are initialized before use
        if not self._auth_decoder_created:
            self._ensure_auth_decoder()
        if not self._voice_decoder_created:
            self._ensure_voice_decoder()
            
        in0 = input_items[0]
        out = output_items[0]

        # Add input to buffer (soft decisions)
        if len(in0) > 0:
            self.frame_buffer.extend(in0.tolist())

        output_idx = 0

        # Determine frame type and decode
        # Frame 0: 768 bits (96 bytes) -> 256 bits (32 bytes) with rate 1/3
        # Frames 1-24: 576 bits (72 bytes) -> 384 bits (48 bytes) with rate 2/3

        while output_idx < noutput and len(self.frame_buffer) > 0:
            if self.frame_counter == 0:
                # Authentication frame - need 768 soft bits
                if len(self.frame_buffer) < 768:
                    break
                
                # Ensure decoder is created
                self._ensure_auth_decoder()

                soft_bits = np.array(self.frame_buffer[:768], dtype=np.float32)
                self.frame_buffer = self.frame_buffer[768:]

                # FEC decoder is a GNU Radio block, not a callable
                # For now, use hard decision (will be fixed in architecture)
                # TODO: Integrate FEC blocks properly in hierarchical flowgraph
                hard_bits = (soft_bits > 0).astype(np.uint8)
                decoded = hard_bits[:32].tobytes()
                if output_idx + len(decoded) <= len(out):
                    out[output_idx:output_idx + len(decoded)] = np.frombuffer(decoded, dtype=np.uint8)
                    output_idx += len(decoded)
                else:
                    # Not enough space, put back
                    self.frame_buffer = soft_bits.tolist() + self.frame_buffer
                    break

                self.frame_counter = (self.frame_counter + 1) % self.superframe_size

            else:
                # Voice frame - need 576 soft bits
                if len(self.frame_buffer) < 576:
                    break
                
                # Ensure decoder is created
                self._ensure_voice_decoder()

                soft_bits = np.array(self.frame_buffer[:576], dtype=np.float32)
                self.frame_buffer = self.frame_buffer[576:]

                # FEC decoder is a GNU Radio block, not a callable
                # For now, use hard decision (will be fixed in architecture)
                # TODO: Integrate FEC blocks properly in hierarchical flowgraph
                hard_bits = (soft_bits > 0).astype(np.uint8)
                decoded = hard_bits[:48].tobytes()
                if output_idx + len(decoded) <= len(out):
                    out[output_idx:output_idx + len(decoded)] = np.frombuffer(decoded, dtype=np.uint8)
                    output_idx += len(decoded)
                else:
                    # Not enough space, put back
                    self.frame_buffer = soft_bits.tolist() + self.frame_buffer
                    break

                self.frame_counter = (self.frame_counter + 1) % self.superframe_size

        # For sync_block, return number of output items produced
        # Since sync_block requires 1:1 ratio, we return min of what we produced and input length
        # This ensures we don't get stuck
        return min(output_idx, ninput) if output_idx > 0 else min(1, ninput)
    


def make_frame_aware_ldpc_encoder(auth_matrix_file, voice_matrix_file, superframe_size=25):
    """Factory function for GRC."""
    return frame_aware_ldpc_encoder(auth_matrix_file, voice_matrix_file, superframe_size)


def make_frame_aware_ldpc_decoder(auth_matrix_file, voice_matrix_file, superframe_size=25, max_iter=20):
    """Factory function for GRC."""
    return frame_aware_ldpc_decoder(auth_matrix_file, voice_matrix_file, superframe_size, max_iter)

