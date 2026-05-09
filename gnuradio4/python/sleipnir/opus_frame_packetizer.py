#!/usr/bin/env python3
"""
Opus Frame Packetizer Block

Converts variable-size Opus frames to fixed-size packets for stream_to_tagged_stream.
Opus frames are padded/truncated to a fixed size (default 40 bytes).
"""

import numpy as np
from gnuradio import gr


class opus_frame_packetizer(gr.sync_block):
    """
    Packetize variable-size Opus frames into fixed-size packets.
    
    Input: Variable-size Opus frames (uint8 stream)
    Output: Fixed-size packets (uint8 stream with tags)
    """
    
    def __init__(self, frame_size_bytes=40):
        """
        Initialize Opus frame packetizer.
        
        Args:
            frame_size_bytes: Fixed size for output packets (default: 40 bytes)
        """
        gr.sync_block.__init__(
            self,
            name="opus_frame_packetizer",
            in_sig=[np.uint8],
            out_sig=[np.uint8]
        )
        
        self.frame_size_bytes = frame_size_bytes
        self.buffer = bytearray()
        
        # Store reference to self to prevent garbage collection issues
        # This helps prevent NoneType errors when GNU Radio gateway accesses the block
        self._self_ref = self
        
        # Store references to critical methods to ensure they're always accessible
        # This prevents the gateway from getting None when accessing these methods
        self._forecast_ref = self.forecast
        self._work_ref = self.work
        
        # Store instance in class-level list to prevent garbage collection
        # This ensures the Python object stays alive even if local references are cleared
        if not hasattr(type(self), '_instances'):
            type(self)._instances = []
        type(self)._instances.append(self)
        
        # Store all critical references in a dict to prevent GC
        self._refs = {
            'self': self,
            'forecast': self.forecast,
            'work': self.work,
            'gateway': self.gateway
        }
        
    def work(self, input_items, output_items):
        """
        Process variable-size Opus frames and output fixed-size packets.
        """
        in0 = input_items[0]
        out = output_items[0]
        
        ninput = len(in0)
        noutput = len(out)
        
        # Add new data to buffer
        self.buffer.extend(in0.tobytes())
        
        output_idx = 0
        frames_produced = 0
        
        # Process complete frames
        while len(self.buffer) >= self.frame_size_bytes and output_idx < noutput:
            # Extract frame
            frame_data = bytes(self.buffer[:self.frame_size_bytes])
            self.buffer = self.buffer[self.frame_size_bytes:]
            
            # Write to output
            if output_idx + self.frame_size_bytes <= noutput:
                out[output_idx:output_idx + self.frame_size_bytes] = np.frombuffer(frame_data, dtype=np.uint8)
                output_idx += self.frame_size_bytes
                frames_produced += 1
            else:
                # Not enough space, put back
                self.buffer = bytearray(frame_data) + self.buffer
                break
        
        # Debug output to track frame production rate (write to file for subprocess visibility)
        if frames_produced > 0:
            if not hasattr(self, '_debug_count'):
                self._debug_count = 0
                self._total_frames = 0
                self._last_log_time = 0
                import time
                self._start_time = time.time()
            
            self._debug_count += 1
            self._total_frames += frames_produced
            
            # Log every 100 frames or every 5 seconds, whichever comes first
            import time
            current_time = time.time()
            if self._debug_count % 100 == 0 or (current_time - self._last_log_time) >= 5.0 or self._debug_count <= 20:
                elapsed = current_time - self._start_time if hasattr(self, '_start_time') else 1.0
                rate = self._total_frames / elapsed if elapsed > 0 else 0
                msg = f"Opus packetizer: Total {self._total_frames} frames produced, rate: {rate:.2f} frames/sec, buffer: {len(self.buffer)} bytes"
                print(msg)
                # Also write to file for subprocess visibility
                try:
                    with open('/tmp/opus_packetizer_debug.log', 'a') as f:
                        f.write(msg + '\n')
                        f.flush()
                except:
                    pass
                if self._last_log_time > 0:  # Don't reset on first log
                    self._last_log_time = current_time
                elif self._last_log_time == 0:
                    self._last_log_time = current_time
        
        # Consume all input (sync_block requirement)
        # Return number of output items produced
        return output_idx
    
    def __del__(self):
        """Cleanup method to release resources"""
        # Clear buffer to free memory
        try:
            self.buffer = bytearray()
        except:
            pass
        
        # Remove from class instances list
        if hasattr(type(self), '_instances'):
            try:
                type(self)._instances.remove(self)
            except (ValueError, AttributeError):
                pass

