#!/usr/bin/env python3
"""
GNU Radio block for Opus audio encoding
"""

import numpy as np
from gnuradio import gr
import opuslib

class opus_encoder(gr.sync_block):
    """
    Opus audio encoder block

    Encodes PCM audio samples to Opus format.
    Input: Float32 audio samples (mono or stereo)
    Output: Bytes containing Opus-encoded packets
    """

    def __init__(self, sample_rate=48000, channels=1, bitrate=64000, application='audio'):
        """
        Initialize Opus encoder

        Args:
            sample_rate: Input sample rate (8000, 12000, 16000, 24000, or 48000 Hz)
            channels: Number of channels (1 for mono, 2 for stereo)
            bitrate: Target bitrate in bits per second
            application: Opus application type ('voip', 'audio', or 'lowdelay')
        """
        gr.sync_block.__init__(
            self,
            name="opus_encoder",
            in_sig=[np.float32],
            out_sig=[np.uint8]
        )
        
        self.sample_rate = sample_rate
        self.channels = channels
        self.bitrate = bitrate
        
        # Map application string to opuslib constant
        app_map = {
            'voip': opuslib.APPLICATION_VOIP,
            'audio': opuslib.APPLICATION_AUDIO,
            'lowdelay': opuslib.APPLICATION_RESTRICTED_LOWDELAY
        }
        self.application = app_map.get(application.lower(), opuslib.APPLICATION_AUDIO)
        
        # Create Opus encoder
        self.encoder = opuslib.Encoder(sample_rate, channels, self.application)
        self.encoder.bitrate = bitrate
        
        # Frame size in samples (20ms frames for good quality)
        self.frame_size = int(sample_rate * 0.020)  # 20ms frames
        
        # Buffer for accumulating samples
        self.sample_buffer = np.array([], dtype=np.float32)
        
        # Convert float32 samples to int16 for Opus
        self.max_int16 = 32767.0
        
    def work(self, input_items, output_items):
        """
        Process audio samples and encode to Opus
        """
        in0 = input_items[0]
        out = output_items[0]
        
        # Add new samples to buffer
        self.sample_buffer = np.concatenate([self.sample_buffer, in0])
        
        output_idx = 0
        
        # Process complete frames
        while len(self.sample_buffer) >= self.frame_size * self.channels and output_idx < len(out):
            # Extract frame
            frame_samples = self.sample_buffer[:self.frame_size * self.channels]
            self.sample_buffer = self.sample_buffer[self.frame_size * self.channels:]
            
            # Reshape for multi-channel
            if self.channels > 1:
                frame_samples = frame_samples.reshape(-1, self.channels)
            
            # Convert float32 [-1.0, 1.0] to int16
            int16_samples = (frame_samples * self.max_int16).astype(np.int16)
            
            # Encode frame
            try:
                encoded_data = self.encoder.encode(int16_samples.tobytes(), self.frame_size)
                
                # Write encoded packet to output
                if output_idx + len(encoded_data) <= len(out):
                    out[output_idx:output_idx + len(encoded_data)] = np.frombuffer(encoded_data, dtype=np.uint8)
                    output_idx += len(encoded_data)
                else:
                    # Not enough space, put frame back in buffer
                    self.sample_buffer = np.concatenate([frame_samples.flatten(), self.sample_buffer])
                    break
            except Exception as e:
                print(f"Opus encoding error: {e}")
                break
        
        # For sync_block, we must consume all input
        # Return number of output items produced
        return output_idx

