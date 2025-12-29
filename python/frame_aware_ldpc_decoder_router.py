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
    then outputs decoded frames as a tagged stream.
    
    Input: float32 soft decisions (LLRs) via stream
    Output: uint8 decoded bytes via tagged stream (with "packet_len" tags)
    
    Uses tagged stream instead of message ports for better compatibility
    with hier_block2 contexts.
    """
    
    def __init__(self, auth_matrix_file, voice_matrix_file, superframe_size=25, max_iter=50,
                 algorithm='sum_product', min_sum_scale=0.75):
        # Use sync_block with tagged stream output
        # Tagged streams work reliably in hier_block2 contexts
        gr.sync_block.__init__(
            self,
            name="frame_aware_ldpc_decoder_router",
            in_sig=[np.float32],  # Soft decisions
            out_sig=[np.uint8]  # Tagged stream output (decoded bytes with packet_len tags)
        )
        
        # CRITICAL: Request larger input buffers to accumulate data faster
        # This allows GNU Radio to pass more items per work() call
        # Request buffers that are multiples of reasonable sizes
        try:
            # Request input buffers that are multiples of 512 items (good for accumulation)
            # This allows faster accumulation of soft bits
            self.set_output_multiple(512)  # Request output in multiples of 512
            # Also set minimum input buffer to encourage larger chunks
            self.set_min_output_buffer(1536)  # At least enough for one auth frame
            print(f"Decoder router: Set output_multiple=512, min_output_buffer=1536")
        except Exception as e:
            print(f"Decoder router: Could not set buffer sizes: {e}")
        
        # Tag key for packet length
        self.tag_key = pmt.intern("packet_len")
        
        # Register message port for direct PDU output (bypasses tag propagation issues)
        self.message_port_register_out(pmt.intern("pdus"))
        
        # Buffer for decoded frames waiting to be output as tagged stream
        self.output_frame_buffer = []
        
        print(f"Decoder router: Using tagged stream output (reliable through hier_block2)")
        
        # Note: set_min_output_buffer is optional and causes type errors in some GNU Radio versions
        # GNU Radio will automatically size buffers, so we don't need to set it explicitly
        # If buffer sizing becomes an issue, we can investigate the correct method signature
        
        self.auth_matrix_file = auth_matrix_file
        self.voice_matrix_file = voice_matrix_file
        self.superframe_size = superframe_size
        self.max_iter = max_iter
        self.algorithm = algorithm
        self.min_sum_scale = min_sum_scale
        self.frame_counter = 0
        
        # Soft decision buffer
        self.soft_buffer = []
        
        # Decoded frame buffer (output queue)
        self.output_buffer = bytearray()
        
        # Track if we've decoded frames (to know when to pad with zeros)
        self._has_decoded_frames = False
        
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
            info_bits = ldpc_decode_soft(soft_array, self.auth_H, self.max_iter,
                                        self.algorithm, self.min_sum_scale)
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
            info_bits = ldpc_decode_soft(soft_array, self.voice_H, self.max_iter,
                                        self.algorithm, self.min_sum_scale)
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
        
        Uses message ports for output (no stream output).
        Always consumes all input (buffers it for decoding).
        """
        in0 = input_items[0]
        
        # CRITICAL: Always log when called to verify block is being invoked
        if not hasattr(self, '_first_call_logged'):
            print(f"Decoder router: work() called for first time, input_items length: {len(in0)} (tagged stream output)")
            self._first_call_logged = True
        
        if len(in0) == 0:
            # No input available - return 0 for sync_block
            return 0
        
        # CRITICAL: For sync_block, we must consume all input and produce equal output
        # Track how many input items we consume
        input_consumed = len(in0)
        
        # Add new soft decisions to buffer
        # CRITICAL: Always add input to buffer, even if we can't output yet
        # This ensures we don't lose data
        self.soft_buffer.extend(in0.tolist())
        
        # Debug: Track if we're receiving data and scheduler behavior
        if not hasattr(self, '_debug_call_count'):
            self._debug_call_count = 0
            self._debug_total_input = 0
            self._debug_last_call_time = None
        self._debug_call_count += 1
        self._debug_total_input += len(in0)
        
        import time
        current_time = time.time()
        if self._debug_last_call_time:
            time_since_last = current_time - self._debug_last_call_time
        else:
            time_since_last = 0
        self._debug_last_call_time = current_time
        
        # Log first 20 calls, then every 1000 calls, or when buffer reaches threshold
        # Also log when buffer is close to threshold (every 100 items when > 1000)
        should_log = (self._debug_call_count <= 20 or 
                     self._debug_call_count % 1000 == 0 or 
                     len(self.soft_buffer) >= 1536 or
                     (len(self.soft_buffer) > 1000 and len(self.soft_buffer) % 100 == 0))
        
        if should_log:
            if len(self.soft_buffer) >= 1536:
                print(f"Decoder router: Call #{self._debug_call_count}, Buffer has {len(self.soft_buffer)} soft bits (enough for auth frame), received {len(in0)} new items, time since last: {time_since_last*1000:.2f}ms")
            elif len(self.soft_buffer) > 1000:
                print(f"Decoder router: Call #{self._debug_call_count}, Buffer has {len(self.soft_buffer)} soft bits (approaching auth threshold of 1536), received {len(in0)} new items")
            else:
                print(f"Decoder router: Call #{self._debug_call_count}, Received {len(in0)} items, buffer now has {len(self.soft_buffer)} items (total: {self._debug_total_input}), time since last: {time_since_last*1000:.2f}ms")
        
        output_idx = 0
        
        # Process frames from buffer
        # Note: We process frames and add to output_buffer, then output from buffer
        # This allows us to handle variable output sizes
        # Process as many frames as possible from the buffer
        # IMPORTANT: Continue processing even if output buffer is full - we'll output
        # in subsequent calls. This ensures we decode all available frames.
        frames_decoded_this_call = 0
        max_frames_to_process = 100  # Safety limit to prevent infinite loops
        frames_processed = 0
        
        while len(self.soft_buffer) > 0 and frames_processed < max_frames_to_process:
            if self.frame_counter == 0:
                # Auth frame: need 1536 soft bits
                if len(self.soft_buffer) < 1536:
                    # Debug: Log when waiting for more bits
                    if not hasattr(self, '_waiting_for_auth_logged') or self._waiting_for_auth_logged < 5:
                        if not hasattr(self, '_waiting_for_auth_logged'):
                            self._waiting_for_auth_logged = 0
                        self._waiting_for_auth_logged += 1
                        print(f"Decoder router: Waiting for auth frame: need 1536 bits, have {len(self.soft_buffer)} bits")
                    break
                
                # Extract 1536 soft bits
                soft_bits = self.soft_buffer[:1536]
                self.soft_buffer = self.soft_buffer[1536:]
                
                # Decode auth frame (64 bytes)
                decoded = self._decode_auth_frame(soft_bits)
                
                # Track frame number before updating counter
                current_frame_num = self.frame_counter
                frame_size_bytes = 64
                
                # Ensure decoded frame is correct size
                if len(decoded) != 64:
                    if len(decoded) < 64:
                        decoded = decoded + b'\x00' * (64 - len(decoded))
                    else:
                        decoded = decoded[:64]
                
                # Add to output buffer for tagged stream
                # NOTE: Don't skip all-zero frames - they may be valid decoded frames
                # The parser will handle validation
                frame_data = bytes(decoded)
                self.output_frame_buffer.append({
                    'data': frame_data,
                    'size': frame_size_bytes,
                    'frame_num': current_frame_num
                })
                frames_decoded_this_call += 1
                
                # Debug: Log frame creation
                if frames_decoded_this_call <= 20 or current_frame_num == 0:
                    is_all_zero = all(b == 0 for b in frame_data)
                    print(f"Decoder router: Decoded auth frame {current_frame_num}, size {frame_size_bytes} bytes, queued for tagged stream, all_zero={is_all_zero}, first few: {list(frame_data[:min(8, len(frame_data))])}")
                
                # Update frame counter (wraps at superframe_size)
                self.frame_counter = (self.frame_counter + 1) % self.superframe_size
                
            else:
                # Voice frame: need 576 soft bits
                if len(self.soft_buffer) < 576:
                    # Debug: Log when waiting for more bits
                    if not hasattr(self, '_waiting_for_voice_logged') or self._waiting_for_voice_logged < 5:
                        if not hasattr(self, '_waiting_for_voice_logged'):
                            self._waiting_for_voice_logged = 0
                        self._waiting_for_voice_logged += 1
                        print(f"Decoder router: Waiting for voice frame: need 576 bits, have {len(self.soft_buffer)} bits, frame_counter={self.frame_counter}")
                    break
                
                # Extract 576 soft bits
                soft_bits = self.soft_buffer[:576]
                self.soft_buffer = self.soft_buffer[576:]
                
                # Decode voice frame (48 bytes)
                decoded = self._decode_voice_frame(soft_bits)
                
                # Track frame number before updating counter
                current_frame_num = self.frame_counter
                frame_size_bytes = 48
                
                # Ensure decoded frame is correct size
                if len(decoded) != 48:
                    if len(decoded) < 48:
                        decoded = decoded + b'\x00' * (48 - len(decoded))
                    else:
                        decoded = decoded[:48]
                
                # Add to output buffer for tagged stream
                # NOTE: Don't skip all-zero frames - they may be valid decoded frames
                # The parser will handle validation
                frame_data = bytes(decoded)
                self.output_frame_buffer.append({
                    'data': frame_data,
                    'size': frame_size_bytes,
                    'frame_num': current_frame_num
                })
                frames_decoded_this_call += 1
                
                # Debug: Log frame creation
                if frames_decoded_this_call <= 20:
                    is_all_zero = all(b == 0 for b in frame_data)
                    print(f"Decoder router: Decoded voice frame {current_frame_num}, size {frame_size_bytes} bytes, queued for tagged stream, all_zero={is_all_zero}")
                
                # Update frame counter (wraps at superframe_size)
                # After frame 24, counter wraps to 0 (next superframe's auth frame)
                self.frame_counter = (self.frame_counter + 1) % self.superframe_size
                frames_processed += 1
        
        # Track input consumed
        input_consumed = len(in0)
        
        # Output frames from buffer as tagged stream
        output_produced = 0
        out0 = output_items[0]
        written_offset = self.nitems_written(0)  # Use OUTPUT position for tags
        
        # Debug: Log buffer status before output
        if len(self.output_frame_buffer) > 0 and not hasattr(self, '_output_debug_logged'):
            print(f"Decoder router: DEBUG - output_frame_buffer has {len(self.output_frame_buffer)} frames, output buffer size={len(out0)}")
            self._output_debug_logged = True
        
        while len(self.output_frame_buffer) > 0 and output_produced < len(out0):
            frame_info = self.output_frame_buffer[0]
            frame_data = frame_info['data']
            frame_size = frame_info['size']
            
            # Debug: Log before output attempt
            if not hasattr(self, '_output_attempt_logged'):
                print(f"Decoder router: Attempting to output frame: size={frame_size}, output_produced={output_produced}, out0_size={len(out0)}")
                self._output_attempt_logged = True
            
            # Check if we have enough output space
            space_check = output_produced + frame_size
            if space_check > len(out0):
                # Not enough space - will output in next call
                if not hasattr(self, '_space_warning_logged'):
                    print(f"Decoder router: WARNING - Output buffer too small: need {frame_size} bytes at offset {output_produced}, have {len(out0)} total, available={len(out0) - output_produced}")
                    self._space_warning_logged = True
                break
            
            # Debug: Log that we're proceeding with output
            if not hasattr(self, '_output_proceed_logged'):
                print(f"Decoder router: Proceeding with output: space_check={space_check}, len(out0)={len(out0)}, condition={space_check <= len(out0)}")
                self._output_proceed_logged = True
            
            # CRITICAL: Calculate tag offset BEFORE writing data
            # Tag offset must be absolute OUTPUT position (written_offset + output_produced)
            # Tags must reference output stream positions, not input positions
            # Tag must be added at the START of the frame data
            tag_offset = written_offset + output_produced
            
            # Write frame data to output FIRST
            try:
                frame_array = np.array(list(frame_data), dtype=np.uint8)
                out0[output_produced:output_produced + frame_size] = frame_array
                if not hasattr(self, '_frame_write_logged'):
                    print(f"Decoder router: Frame data written successfully: {frame_size} bytes")
                    self._frame_write_logged = True
            except Exception as e:
                print(f"Decoder router: ERROR writing frame data: {e}")
                break
            
            # Initialize output log count before using it
            if not hasattr(self, '_output_log_count'):
                self._output_log_count = 0
            self._output_log_count += 1
            
            # CRITICAL: Add tag AFTER writing data, at the exact position where data starts
            # Tags added after data are more reliably propagated in GNU Radio
            # ALSO publish PDU directly via message port (bypasses tag propagation issues)
            try:
                tag_pmt = pmt.from_long(frame_size)
                self.add_item_tag(0, tag_offset, self.tag_key, tag_pmt)
                
                # ALSO publish PDU directly via message port (bypasses tag propagation issues)
                # This ensures frames are delivered even if tags don't propagate through hier_block2
                try:
                    packet_pmt = pmt.init_u8vector(len(frame_array), list(frame_array))
                    meta = pmt.make_dict()
                    meta = pmt.dict_add(meta, pmt.intern("packet_len"), tag_pmt)
                    pdu = pmt.cons(meta, packet_pmt)
                    self.message_port_pub(pmt.intern("pdus"), pdu)
                    
                    if self._output_log_count <= 10:
                        print(f"Decoder router: Published PDU directly via message port: {frame_size} bytes, data: {list(frame_array[:min(8, len(frame_array))])}")
                except Exception as e:
                    print(f"Decoder router: ERROR publishing PDU: {e}")
                
                if self._output_log_count <= 10:
                    # Verify tag was added immediately
                    try:
                        tags_at_offset = self.get_tags_in_range(0, tag_offset, tag_offset + 1)
                        if tags_at_offset:
                            tag_found = any(pmt.eq(t.key, self.tag_key) and pmt.to_long(t.value) == frame_size for t in tags_at_offset)
                            if tag_found:
                                print(f"Decoder router: Tag verified immediately at offset {tag_offset}, value={frame_size}")
                            else:
                                print(f"Decoder router: WARNING - Tag added but not found at offset {tag_offset}")
                        else:
                            print(f"Decoder router: WARNING - No tags found at offset {tag_offset} after adding")
                    except Exception as e:
                        print(f"Decoder router: ERROR verifying tag: {e}")
                    
                    print(f"Decoder router: Outputting frame #{self._output_log_count} as tagged stream: {frame_size} bytes at offset {tag_offset}, data: {list(frame_array[:min(8, len(frame_array))])}")
                        
                if not hasattr(self, '_tag_add_logged'):
                    print(f"Decoder router: Tag added at offset {tag_offset}, value={frame_size}, written_offset={written_offset}, output_produced={output_produced}")
                    self._tag_add_logged = True
            except Exception as e:
                print(f"Decoder router: ERROR adding tag: {e}")
                import traceback
                traceback.print_exc()
                # Don't break - continue even if tag fails
            
            # CRITICAL: Increment output_produced AFTER successfully writing frame
            output_produced += frame_size
            self.output_frame_buffer.pop(0)
            
            # Debug: Log after output
            if self._output_log_count <= 10:
                print(f"Decoder router: Frame output complete: output_produced={output_produced}, frame_size={frame_size}, buffer remaining={len(self.output_frame_buffer)} frames")
        
        # CRITICAL: Always produce some output to keep stream active and block scheduled
        # If no frames to output, produce zeros to maintain 1:1 ratio for sync_block
        # This ensures the block is always scheduled and can process input
        # BUT: Only add dummy output if we didn't already output frames
        if output_produced == 0 and len(out0) > 0:
            # Produce at least 1 item to keep scheduler active
            # This ensures work() continues to be called even when no frames are ready
            out0[0] = 0
            output_produced = 1
        
        # Debug: Log when we decode frames or output frames
        if frames_decoded_this_call > 0 or output_produced > 0:
            if frames_decoded_this_call > 0:
                print(f"Decoder router: Decoded {frames_decoded_this_call} frames, output {output_produced} bytes as tagged stream, frame_counter={self.frame_counter}, soft_buffer={len(self.soft_buffer)}")
            elif output_produced > 0:
                print(f"Decoder router: Output {output_produced} bytes as tagged stream (no new frames decoded this call)")
        
        # Debug: Log what we did (first 20 calls or when we decode/produce)
        if not hasattr(self, '_work_call_count'):
            self._work_call_count = 0
        self._work_call_count += 1
        
        if frames_decoded_this_call > 0 or output_produced > 0 or self._work_call_count <= 20:
            print(f"Decoder router: Call #{self._work_call_count}, consumed {input_consumed} items, decoded {frames_decoded_this_call} frames, produced {output_produced} bytes tagged stream, buffer={len(self.output_frame_buffer)} frames")
        
        # CRITICAL: For sync_block, we must return the number of input items consumed
        # NOT the number of output items produced
        # sync_block requires: output_items == input_items (1:1 ratio)
        # But we buffer input and produce variable output, so we need to:
        # 1. Always consume all input (to keep data flowing)
        # 2. Always produce at least as many output items as input items
        # If we don't have enough output, we need to pad with zeros
        
        # Ensure we produce at least as many output items as we consume
        # This maintains the 1:1 ratio required by sync_block
        if output_produced < input_consumed:
            # Pad output with zeros to match input consumption
            padding_needed = input_consumed - output_produced
            if output_produced + padding_needed <= len(out0):
                out0[output_produced:output_produced + padding_needed] = 0
                output_produced += padding_needed
        
        # Return number of input items consumed (required for sync_block)
        # This ensures we consume all input and keep the stream flowing
        return input_consumed
    
    def forecast(self, noutput_items, ninputs):
        """
        Forecast how many input items we need to produce noutput_items.
        
        For variable rate (decoding produces variable output), we request
        enough input to potentially produce the requested output.
        """
        # Request enough input to accumulate data quickly
        # We buffer input and need 1536 items for auth frame
        # Request at least 1536 items if possible, or as much as we can get
        # This helps accumulate soft bits faster
        requested = max(noutput_items, 1536)  # Request at least 1536 items
        return [requested]
    
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


def make_frame_aware_ldpc_decoder_router(auth_matrix_file, voice_matrix_file, superframe_size=25, max_iter=50,
                                        algorithm='sum_product', min_sum_scale=0.75):
    """Factory function to create frame_aware_ldpc_decoder_router block"""
    return frame_aware_ldpc_decoder_router(auth_matrix_file, voice_matrix_file, superframe_size, max_iter,
                                          algorithm, min_sum_scale)

