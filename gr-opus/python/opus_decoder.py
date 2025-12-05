#!/usr/bin/env python3
"""
GNU Radio block for Opus audio decoding
"""

import numpy as np
from gnuradio import gr
import opuslib

class opus_decoder(gr.sync_block):
    """
    Opus audio decoder block

    Decodes Opus-encoded packets to PCM audio samples.
    Input: Bytes containing Opus-encoded packets
    Output: Float32 audio samples (mono or stereo)
    """

    def __init__(self, sample_rate=48000, channels=1, packet_size=0):
        """
        Initialize Opus decoder

        Args:
            sample_rate: Output sample rate (8000, 12000, 16000, 24000, or 48000 Hz)
            channels: Number of channels (1 for mono, 2 for stereo)
            packet_size: Fixed packet size in bytes (0 for variable/auto-detect)
        """
        gr.sync_block.__init__(
            self,
            name="opus_decoder",
            in_sig=[np.uint8],
            out_sig=[np.float32]
        )
        
        self.sample_rate = sample_rate
        self.channels = channels
        self.packet_size = packet_size
        
        # Create Opus decoder
        self.decoder = opuslib.Decoder(sample_rate, channels)
        
        # Frame size in samples (20ms frames)
        self.frame_size = int(sample_rate * 0.020)  # 20ms frames
        
        # Buffer for accumulating encoded packets
        self.packet_buffer = bytearray()
        
        # Convert int16 samples to float32
        self.max_int16 = 32767.0
        
    def work(self, input_items, output_items):
        """
        Process Opus packets and decode to audio samples
        """
        in0 = input_items[0]
        out = output_items[0]
        
        # Add new data to buffer
        self.packet_buffer.extend(in0.tobytes())
        
        output_idx = 0
        
        # Decode packets
        if self.packet_size > 0:
            # Fixed packet size mode
            while len(self.packet_buffer) >= self.packet_size and output_idx < len(out):
                packet = bytes(self.packet_buffer[:self.packet_size])
                self.packet_buffer = self.packet_buffer[self.packet_size:]
                
                try:
                    decoded_pcm = self.decoder.decode(packet, self.frame_size)
                    
                    if decoded_pcm:
                        # Convert int16 to float32
                        int16_samples = np.frombuffer(decoded_pcm, dtype=np.int16)
                        float_samples = int16_samples.astype(np.float32) / self.max_int16
                        
                        # Reshape for multi-channel
                        if self.channels > 1:
                            float_samples = float_samples.reshape(-1, self.channels)
                        
                        # Flatten for output (handles both mono and stereo)
                        float_samples_flat = float_samples.flatten()
                        
                        # Write to output
                        samples_to_write = min(len(float_samples_flat), len(out) - output_idx)
                        if samples_to_write > 0:
                            out[output_idx:output_idx + samples_to_write] = float_samples_flat[:samples_to_write]
                            output_idx += samples_to_write
                except Exception as e:
                    # Skip invalid packet
                    continue
        else:
            # Variable packet size - try common Opus packet sizes first
            # Opus packets are typically 1-4000 bytes, but common sizes are:
            # - Small packets (1-60 bytes) for low bitrate/silence
            # - Medium packets (60-200 bytes) for normal audio
            # - Large packets (200-4000 bytes) for high bitrate
            
            # Estimate packet size based on typical Opus frame sizes
            # For 20ms frames: ~40-400 bytes depending on bitrate
            estimated_packet_size = max(40, min(400, len(self.packet_buffer) // 5))
            
            # Try packet sizes in order: estimated, then common sizes, then sequential
            packet_size_candidates = []
            if estimated_packet_size <= len(self.packet_buffer):
                packet_size_candidates.append(estimated_packet_size)
            
            # Add common Opus packet sizes
            for size in [60, 80, 100, 120, 150, 180, 200, 250, 300, 350, 400]:
                if size <= len(self.packet_buffer) and size not in packet_size_candidates:
                    packet_size_candidates.append(size)
            
            # Add sequential sizes as fallback
            for size in range(1, min(4000, len(self.packet_buffer) + 1)):
                if size not in packet_size_candidates:
                    packet_size_candidates.append(size)
                if len(packet_size_candidates) > 100:  # Limit search
                    break
            
            while output_idx < len(out) and len(self.packet_buffer) > 0:
                decoded = False
                
                # Try candidate packet sizes
                for packet_size in packet_size_candidates:
                    if packet_size > len(self.packet_buffer):
                        continue
                        
                    try:
                        packet = bytes(self.packet_buffer[:packet_size])
                        decoded_pcm = self.decoder.decode(packet, self.frame_size)
                        
                        if decoded_pcm:
                            # Verify decoded data is not all zeros (silence detection)
                            int16_check = np.frombuffer(decoded_pcm, dtype=np.int16)
                            if np.max(np.abs(int16_check)) > 100:  # Not silence
                                # Convert int16 to float32
                                float_samples = int16_check.astype(np.float32) / self.max_int16
                                
                                # Reshape for multi-channel
                                if self.channels > 1:
                                    float_samples = float_samples.reshape(-1, self.channels)
                                
                                # Flatten for output (handles both mono and stereo)
                                float_samples_flat = float_samples.flatten()
                                
                                # Write to output
                                samples_to_write = min(len(float_samples_flat), len(out) - output_idx)
                                if samples_to_write > 0:
                                    out[output_idx:output_idx + samples_to_write] = float_samples_flat[:samples_to_write]
                                    output_idx += samples_to_write
                                
                                # Remove consumed packet from buffer
                                self.packet_buffer = self.packet_buffer[packet_size:]
                                decoded = True
                                break
                    except Exception:
                        # Try next packet size
                        continue
                
                if not decoded:
                    # Couldn't decode, wait for more data
                    break
        
        # For sync_block, we must consume all input
        # Return number of output items produced
        return output_idx

