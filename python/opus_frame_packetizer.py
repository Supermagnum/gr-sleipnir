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
        
        # Debug output (only occasionally to avoid spam)
        if frames_produced > 0 and not hasattr(self, '_debug_count'):
            self._debug_count = 0
        if frames_produced > 0:
            self._debug_count = getattr(self, '_debug_count', 0) + 1
            if self._debug_count % 10 == 0:  # Print every 10th frame
                print(f"Opus packetizer: Produced {frames_produced} frames, buffer has {len(self.buffer)} bytes remaining")
        
        # Consume all input (sync_block requirement)
        # Return number of output items produced
        return output_idx
    
    def __del__(self):
        """Cleanup method to release resources"""
        # Remove from class instances list
        if hasattr(type(self), '_instances'):
            try:
                type(self)._instances.remove(self)
            except (ValueError, AttributeError):
                pass

