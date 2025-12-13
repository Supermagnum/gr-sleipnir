#!/usr/bin/env python3
"""
Frame-aware LDPC decoder router for gr-sleipnir RX.

Routes soft decisions to appropriate decoders based on frame number:
- Frame 0: 1536 soft bits -> auth decoder -> 64 bytes
- Frames 1-24: 576 soft bits -> voice decoder -> 48 bytes

This block buffers soft decisions and routes them to the correct decoder,
then merges outputs in the correct order.
"""

import numpy as np
from gnuradio import gr
import pmt
from array import array
import os

try:
    from gnuradio import fec
    FEC_AVAILABLE = True
except ImportError:
    FEC_AVAILABLE = False
    print("Warning: GNU Radio FEC module not available")

# Import LDPC utility functions
try:
    from python.ldpc_utils import load_alist_matrix, ldpc_decode_soft
    LDPC_UTILS_AVAILABLE = True
except ImportError:
    LDPC_UTILS_AVAILABLE = False
    print("Warning: LDPC utils not available")


class frame_aware_ldpc_decoder_router(gr.sync_block):
    """
    Frame-aware LDPC decoder router.
    
    Routes soft decisions to auth or voice decoder based on frame number,
    then merges outputs in correct order.
    
    Input: float32 soft decisions (LLRs)
    Output: uint8 decoded bytes
    """
    
    def __init__(self, auth_matrix_file, voice_matrix_file, superframe_size=25, max_iter=50):
        gr.sync_block.__init__(
            self,
            name="frame_aware_ldpc_decoder_router",
            in_sig=[np.float32],  # Soft decisions
            out_sig=[np.uint8]    # Decoded bytes
        )
        
        self.auth_matrix_file = auth_matrix_file
        self.voice_matrix_file = voice_matrix_file
        self.superframe_size = superframe_size
        self.max_iter = max_iter
        self.frame_counter = 0
        
        # Soft decision buffer
        self.soft_buffer = []
        
        # Decoded frame buffer (output queue)
        self.output_buffer = bytearray()
        
        # Initialize decoders
        self.auth_decoder = None
        self.voice_decoder = None
        
        # LDPC parity check matrices for decoding
        self.auth_H = None
        self.voice_H = None
        
        if FEC_AVAILABLE:
            try:
                if auth_matrix_file:
                    decoder_obj_auth = fec.ldpc_decoder_make(auth_matrix_file, max_iter)
                    self.auth_decoder = fec.decoder(decoder_obj_auth, gr.sizeof_float, gr.sizeof_char)
            except Exception as e:
                print(f"Warning: Could not create auth decoder: {e}")
            
            try:
                if voice_matrix_file:
                    decoder_obj_voice = fec.ldpc_decoder_make(voice_matrix_file, max_iter)
                    self.voice_decoder = fec.decoder(decoder_obj_voice, gr.sizeof_float, gr.sizeof_char)
            except Exception as e:
                print(f"Warning: Could not create voice decoder: {e}")
        
        # Load LDPC matrices for direct decoding
        if LDPC_UTILS_AVAILABLE:
            try:
                if auth_matrix_file and os.path.exists(auth_matrix_file):
                    self.auth_H, n, k = load_alist_matrix(auth_matrix_file)
            except Exception as e:
                print(f"Warning: Could not load auth matrix: {e}")
            
            try:
                if voice_matrix_file and os.path.exists(voice_matrix_file):
                    self.voice_H, n, k = load_alist_matrix(voice_matrix_file)
            except Exception as e:
                print(f"Warning: Could not load voice matrix: {e}")
        
        # Store reference to prevent garbage collection
        if not hasattr(type(self), '_instances'):
            type(self)._instances = []
        type(self)._instances.append(self)
    
    def _decode_auth_frame(self, soft_bits):
        """
        Decode auth frame (1536 soft bits -> 64 bytes) using LDPC decoder.
        
        WARNING: This is NOT actual LDPC decoding - only simple thresholding is performed.
        The decoder objects are created but never used because GNU Radio FEC decoders
        are stream-based blocks that must be integrated into the flowgraph, not called directly.
        This performs NO error correction - it just converts soft decisions to hard bits by sign.
        TODO: Integrate FEC decoder blocks properly in hierarchical flowgraph.
        """
        soft_array = np.array(soft_bits, dtype=np.float32)
        
        # Perform actual LDPC soft-decision decoding
        if self.auth_H is not None:
            # Use belief propagation decoding
            info_bits = ldpc_decode_soft(soft_array, self.auth_H, self.max_iter)
            # Convert bits to bytes
            decoded_bytes = np.packbits(info_bits).tobytes()
            # Ensure 64 bytes output
            if len(decoded_bytes) < 64:
                decoded_bytes = decoded_bytes + b'\x00' * (64 - len(decoded_bytes))
            elif len(decoded_bytes) > 64:
                decoded_bytes = decoded_bytes[:64]
        else:
            # Fallback: simple thresholding if decoding not available
            hard_bits = (soft_array > 0).astype(np.uint8)
            decoded_bits = hard_bits[:512]
            decoded_bytes = decoded_bits.tobytes()[:64]
        
        return decoded_bytes
    
    def _decode_voice_frame(self, soft_bits):
        """
        Decode voice frame (576 soft bits -> 48 bytes) using LDPC decoder.
        
        WARNING: This is NOT actual LDPC decoding - only simple thresholding is performed.
        The decoder objects are created but never used because GNU Radio FEC decoders
        are stream-based blocks that must be integrated into the flowgraph, not called directly.
        This performs NO error correction - it just converts soft decisions to hard bits by sign.
        TODO: Integrate FEC decoder blocks properly in hierarchical flowgraph.
        """
        soft_array = np.array(soft_bits, dtype=np.float32)
        
        # Perform actual LDPC soft-decision decoding
        if self.voice_H is not None:
            # Use belief propagation decoding
            info_bits = ldpc_decode_soft(soft_array, self.voice_H, self.max_iter)
            # Convert bits to bytes
            decoded_bytes = np.packbits(info_bits).tobytes()
            # Ensure 48 bytes output
            if len(decoded_bytes) < 48:
                decoded_bytes = decoded_bytes + b'\x00' * (48 - len(decoded_bytes))
            elif len(decoded_bytes) > 48:
                decoded_bytes = decoded_bytes[:48]
        else:
            # Fallback: simple thresholding if decoding not available
            hard_bits = (soft_array > 0).astype(np.uint8)
            decoded_bits = hard_bits[:384]
            decoded_bytes = decoded_bits.tobytes()[:48]
        
        return decoded_bytes
    
    def work(self, input_items, output_items):
        """
        Process soft decisions and route to appropriate decoder.
        """
        in0 = input_items[0]
        out = output_items[0]
        
        if len(in0) == 0:
            return 0
        
        # Add new soft decisions to buffer
        self.soft_buffer.extend(in0.tolist())
        
        output_idx = 0
        
        # Process frames from buffer
        # Note: We process frames and add to output_buffer, then output from buffer
        # This allows us to handle variable output sizes
        while len(self.soft_buffer) > 0:
            if self.frame_counter == 0:
                # Auth frame: need 1536 soft bits
                if len(self.soft_buffer) < 1536:
                    break
                
                # Extract 1536 soft bits
                soft_bits = self.soft_buffer[:1536]
                self.soft_buffer = self.soft_buffer[1536:]
                
                # Decode auth frame (64 bytes)
                decoded = self._decode_auth_frame(soft_bits)
                
                # Add to output buffer
                if len(decoded) == 64:
                    self.output_buffer.extend(decoded)
                else:
                    # Pad or truncate to 64 bytes
                    if len(decoded) < 64:
                        self.output_buffer.extend(decoded + b'\x00' * (64 - len(decoded)))
                    else:
                        self.output_buffer.extend(decoded[:64])
                
                # Update frame counter (wraps at superframe_size)
                self.frame_counter = (self.frame_counter + 1) % self.superframe_size
                
            else:
                # Voice frame: need 576 soft bits
                if len(self.soft_buffer) < 576:
                    break
                
                # Extract 576 soft bits
                soft_bits = self.soft_buffer[:576]
                self.soft_buffer = self.soft_buffer[576:]
                
                # Decode voice frame (48 bytes)
                decoded = self._decode_voice_frame(soft_bits)
                
                # Add to output buffer
                if len(decoded) == 48:
                    self.output_buffer.extend(decoded)
                else:
                    # Pad or truncate to 48 bytes
                    if len(decoded) < 48:
                        self.output_buffer.extend(decoded + b'\x00' * (48 - len(decoded)))
                    else:
                        self.output_buffer.extend(decoded[:48])
                
                # Update frame counter (wraps at superframe_size)
                # After frame 24, counter wraps to 0 (next superframe's auth frame)
                self.frame_counter = (self.frame_counter + 1) % self.superframe_size
        
        # Output decoded bytes from buffer to output stream
        # We output as much as we can fit in the output buffer
        n_output = min(len(self.output_buffer), len(out))
        if n_output > 0:
            decoded_array = np.frombuffer(self.output_buffer[:n_output], dtype=np.uint8)
            out[:n_output] = decoded_array
            self.output_buffer = self.output_buffer[n_output:]
            output_idx = n_output
        
        # For sync_block, we need to return the number of output items produced
        # If we produced output, return that; otherwise return at least 1 to avoid blocking
        if output_idx > 0:
            return len(in0)  # Consume all input, produce output_idx items
        else:
            # No output yet, but consume some input to keep things moving
            # Return at least 1 to avoid blocking
            return min(len(in0), 1)
    
    def __del__(self):
        """Cleanup method"""
        try:
            self.soft_buffer = []
            self.output_buffer = bytearray()
        except:
            pass
        
        if hasattr(type(self), '_instances'):
            try:
                type(self)._instances.remove(self)
            except (ValueError, AttributeError):
                pass


def make_frame_aware_ldpc_decoder_router(auth_matrix_file, voice_matrix_file, superframe_size=25, max_iter=50):
    """Factory function to create frame_aware_ldpc_decoder_router block"""
    return frame_aware_ldpc_decoder_router(auth_matrix_file, voice_matrix_file, superframe_size, max_iter)

