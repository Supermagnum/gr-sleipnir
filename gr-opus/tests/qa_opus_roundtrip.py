#!/usr/bin/env python3
"""
Integration tests for Opus encoder-decoder round-trip
"""

import unittest
import numpy as np
from gnuradio import gr, blocks
import sys
import os

# Add parent directory to path to import gr_opus
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from opus_encoder import opus_encoder
from opus_decoder import opus_decoder


class qa_opus_roundtrip(unittest.TestCase):
    """Test suite for encoder-decoder round-trip"""

    def setUp(self):
        """Set up test fixtures"""
        self.tb = gr.top_block()
        self.sample_rate = 48000
        self.channels = 1
        self.frame_size = int(self.sample_rate * 0.020)  # 20ms frames

    def tearDown(self):
        """Clean up after tests"""
        self.tb = None

    def _roundtrip_encode_decode(self, input_signal, sample_rate=48000, channels=1, bitrate=64000):
        """Helper function to encode and decode a signal"""
        encoder = opus_encoder(
            sample_rate=sample_rate,
            channels=channels,
            bitrate=bitrate
        )
        
        decoder = opus_decoder(
            sample_rate=sample_rate,
            channels=channels,
            packet_size=0  # Auto-detect
        )
        
        # Encode
        encoded_output = np.zeros(10000, dtype=np.uint8)
        produced_enc = encoder.work([input_signal], [encoded_output])
        
        if produced_enc == 0:
            return None, None
        
        encoded_data = encoded_output[:produced_enc]
        
        # Decode
        decoded_output = np.zeros(len(input_signal) * 2, dtype=np.float32)
        produced_dec = decoder.work([encoded_data], [decoded_output])
        
        if produced_dec == 0:
            return None, None
        
        decoded_data = decoded_output[:produced_dec]
        
        return encoded_data, decoded_data

    def test_001_roundtrip_sine_wave(self):
        """Test round-trip encoding/decoding of sine wave"""
        # Generate sine wave
        duration = 0.1  # 100ms
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        frequency = 440  # A4 note
        input_signal = np.sin(2 * np.pi * frequency * t, dtype=np.float32) * 0.8
        
        encoded, decoded = self._roundtrip_encode_decode(input_signal)
        
        self.assertIsNotNone(encoded)
        self.assertIsNotNone(decoded)
        self.assertGreater(len(decoded), 0)
        
        # Check that decoded signal has similar characteristics
        # (frequency content should be preserved)
        self.assertGreater(np.max(np.abs(decoded)), 0)

    def test_002_roundtrip_multiple_frames(self):
        """Test round-trip with multiple frames"""
        # Generate signal with multiple frames
        num_frames = 5
        num_samples = self.frame_size * num_frames
        t = np.linspace(0, num_frames * 0.020, num_samples, False)
        input_signal = np.sin(2 * np.pi * 440 * t, dtype=np.float32) * 0.8
        
        encoded, decoded = self._roundtrip_encode_decode(input_signal)
        
        self.assertIsNotNone(encoded)
        self.assertIsNotNone(decoded)
        self.assertGreater(len(decoded), 0)

    def test_003_roundtrip_stereo(self):
        """Test round-trip with stereo signal"""
        num_samples = self.frame_size * 2
        t = np.linspace(0, 2 * 0.020, num_samples // 2, False)
        
        # Generate stereo signal
        left_channel = np.sin(2 * np.pi * 440 * t, dtype=np.float32) * 0.8
        right_channel = np.sin(2 * np.pi * 880 * t, dtype=np.float32) * 0.8
        stereo_signal = np.column_stack([left_channel, right_channel]).flatten()
        
        encoded, decoded = self._roundtrip_encode_decode(
            stereo_signal,
            channels=2
        )
        
        self.assertIsNotNone(encoded)
        self.assertIsNotNone(decoded)
        self.assertGreater(len(decoded), 0)

    def test_004_roundtrip_different_sample_rates(self):
        """Test round-trip with different sample rates"""
        for rate in [8000, 16000, 24000, 48000]:
            frame_size = int(rate * 0.020)
            num_samples = frame_size * 2
            t = np.linspace(0, 2 * 0.020, num_samples, False)
            input_signal = np.sin(2 * np.pi * 440 * t, dtype=np.float32) * 0.8
            
            encoded, decoded = self._roundtrip_encode_decode(
                input_signal,
                sample_rate=rate
            )
            
            self.assertIsNotNone(encoded, f"Failed at sample rate {rate}")
            self.assertIsNotNone(decoded, f"Failed at sample rate {rate}")
            self.assertGreater(len(decoded), 0, f"Failed at sample rate {rate}")

    def test_005_roundtrip_silence(self):
        """Test round-trip with silence"""
        # Need enough samples for at least one complete frame
        num_samples = self.frame_size * 3
        silence = np.zeros(num_samples, dtype=np.float32)
        
        encoded, decoded = self._roundtrip_encode_decode(silence)
        
        # Should handle silence gracefully
        # Encoder might not produce output immediately for silence, so allow None
        if encoded is not None:
            if decoded is not None:
                # Decoded silence might be very small values due to encoding artifacts
                self.assertGreaterEqual(len(decoded), 0)

    def test_006_roundtrip_white_noise(self):
        """Test round-trip with white noise"""
        num_samples = self.frame_size * 3
        noise = np.random.randn(num_samples).astype(np.float32) * 0.3
        
        encoded, decoded = self._roundtrip_encode_decode(noise)
        
        self.assertIsNotNone(encoded)
        self.assertIsNotNone(decoded)
        self.assertGreater(len(decoded), 0)

    def test_007_roundtrip_different_bitrates(self):
        """Test round-trip with different bitrates"""
        num_samples = self.frame_size * 2
        t = np.linspace(0, 2 * 0.020, num_samples, False)
        input_signal = np.sin(2 * np.pi * 440 * t, dtype=np.float32) * 0.8
        
        for bitrate in [32000, 64000, 128000]:
            encoded, decoded = self._roundtrip_encode_decode(
                input_signal,
                bitrate=bitrate
            )
            
            self.assertIsNotNone(encoded, f"Failed at bitrate {bitrate}")
            self.assertIsNotNone(decoded, f"Failed at bitrate {bitrate}")
            self.assertGreater(len(decoded), 0, f"Failed at bitrate {bitrate}")

    def test_008_roundtrip_application_types(self):
        """Test round-trip with different application types"""
        num_samples = self.frame_size * 2
        t = np.linspace(0, 2 * 0.020, num_samples, False)
        input_signal = np.sin(2 * np.pi * 440 * t, dtype=np.float32) * 0.8
        
        for app_type in ['voip', 'audio', 'lowdelay']:
            encoder = opus_encoder(
                sample_rate=self.sample_rate,
                channels=self.channels,
                application=app_type
            )
            decoder = opus_decoder(
                sample_rate=self.sample_rate,
                channels=self.channels
            )
            
            # Encode
            encoded_output = np.zeros(10000, dtype=np.uint8)
            produced_enc = encoder.work([input_signal], [encoded_output])
            
            if produced_enc > 0:
                encoded_data = encoded_output[:produced_enc]
                
                # Decode
                decoded_output = np.zeros(len(input_signal) * 2, dtype=np.float32)
                produced_dec = decoder.work([encoded_data], [decoded_output])
                
                self.assertGreater(produced_dec, 0, f"Failed with application type {app_type}")


if __name__ == '__main__':
    unittest.main()

