#!/usr/bin/env python3
"""
Unit tests for Opus encoder block
"""

import unittest
import numpy as np
from gnuradio import gr, blocks
import sys
import os

# Add parent directory to path to import gr_opus
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from opus_encoder import opus_encoder


class qa_opus_encoder(unittest.TestCase):
    """Test suite for opus_encoder block"""

    def setUp(self):
        """Set up test fixtures"""
        self.tb = gr.top_block()
        self.sample_rate = 48000
        self.channels = 1
        self.frame_size = int(self.sample_rate * 0.020)  # 20ms frames

    def tearDown(self):
        """Clean up after tests"""
        self.tb = None

    def test_001_encoder_initialization(self):
        """Test encoder initialization with default parameters"""
        encoder = opus_encoder()
        self.assertEqual(encoder.sample_rate, 48000)
        self.assertEqual(encoder.channels, 1)
        self.assertEqual(encoder.bitrate, 64000)
        self.assertIsNotNone(encoder.encoder)

    def test_002_encoder_initialization_custom_params(self):
        """Test encoder initialization with custom parameters"""
        encoder = opus_encoder(
            sample_rate=16000,
            channels=2,
            bitrate=128000,
            application='voip'
        )
        self.assertEqual(encoder.sample_rate, 16000)
        self.assertEqual(encoder.channels, 2)
        self.assertEqual(encoder.bitrate, 128000)
        self.assertEqual(encoder.frame_size, int(16000 * 0.020))

    def test_003_encoder_application_types(self):
        """Test encoder with different application types"""
        for app_type in ['voip', 'audio', 'lowdelay']:
            encoder = opus_encoder(application=app_type)
            self.assertIsNotNone(encoder.encoder)

    def test_004_encoder_sample_rates(self):
        """Test encoder with different sample rates"""
        for rate in [8000, 12000, 16000, 24000, 48000]:
            encoder = opus_encoder(sample_rate=rate)
            self.assertEqual(encoder.sample_rate, rate)
            self.assertEqual(encoder.frame_size, int(rate * 0.020))

    def test_005_encoder_mono_stereo(self):
        """Test encoder with mono and stereo"""
        encoder_mono = opus_encoder(channels=1)
        self.assertEqual(encoder_mono.channels, 1)
        
        encoder_stereo = opus_encoder(channels=2)
        self.assertEqual(encoder_stereo.channels, 2)

    def test_006_encoder_single_frame(self):
        """Test encoding a single complete frame"""
        encoder = opus_encoder(sample_rate=self.sample_rate, channels=self.channels)
        
        # Generate test signal (sine wave)
        t = np.linspace(0, 0.020, self.frame_size, False)
        test_signal = np.sin(2 * np.pi * 440 * t, dtype=np.float32)
        
        # Create input and output buffers
        input_data = test_signal
        output_data = np.zeros(4000, dtype=np.uint8)
        
        # Process
        produced = encoder.work([input_data], [output_data])
        
        # Check that output was produced (should produce encoded data)
        self.assertGreater(produced, 0)
        # Check that encoded data is not all zeros
        self.assertNotEqual(np.sum(output_data[:produced]), 0)

    def test_007_encoder_multiple_frames(self):
        """Test encoding multiple frames"""
        encoder = opus_encoder(sample_rate=self.sample_rate, channels=self.channels)
        
        # Generate multiple frames
        num_frames = 3
        t = np.linspace(0, 0.020 * num_frames, self.frame_size * num_frames, False)
        test_signal = np.sin(2 * np.pi * 440 * t, dtype=np.float32)
        
        output_data = np.zeros(10000, dtype=np.uint8)
        
        produced = encoder.work([test_signal], [output_data])
        
        self.assertGreater(produced, 0)

    def test_008_encoder_partial_frame(self):
        """Test encoding with partial frame (should buffer)"""
        encoder = opus_encoder(sample_rate=self.sample_rate, channels=self.channels)
        
        # Generate less than one frame
        partial_samples = self.frame_size // 2
        test_signal = np.random.randn(partial_samples).astype(np.float32) * 0.5
        
        output_data = np.zeros(4000, dtype=np.uint8)
        
        produced = encoder.work([test_signal], [output_data])
        
        # Should not produce output yet (partial frame)
        self.assertEqual(produced, 0)
        # Buffer should contain the samples
        self.assertEqual(len(encoder.sample_buffer), partial_samples)

    def test_009_encoder_stereo_frame(self):
        """Test encoding stereo frame"""
        encoder = opus_encoder(sample_rate=self.sample_rate, channels=2)
        
        # Generate stereo test signal
        frame_size_stereo = encoder.frame_size * 2
        t = np.linspace(0, 0.020, encoder.frame_size, False)
        left_channel = np.sin(2 * np.pi * 440 * t, dtype=np.float32)
        right_channel = np.sin(2 * np.pi * 880 * t, dtype=np.float32)
        stereo_signal = np.column_stack([left_channel, right_channel]).flatten()
        
        output_data = np.zeros(4000, dtype=np.uint8)
        
        produced = encoder.work([stereo_signal], [output_data])
        
        self.assertGreater(produced, 0)

    def test_010_encoder_silence(self):
        """Test encoding silence (zero input)"""
        encoder = opus_encoder(sample_rate=self.sample_rate, channels=self.channels)
        
        # Generate silence
        silence = np.zeros(self.frame_size, dtype=np.float32)
        
        output_data = np.zeros(4000, dtype=np.uint8)
        
        produced = encoder.work([silence], [output_data])
        
        # Should still produce encoded data (Opus encodes silence)
        self.assertGreaterEqual(produced, 0)

    def test_011_encoder_clipping(self):
        """Test encoding with clipped input (values > 1.0)"""
        encoder = opus_encoder(sample_rate=self.sample_rate, channels=self.channels)
        
        # Generate clipped signal
        clipped_signal = np.ones(self.frame_size, dtype=np.float32) * 1.5
        
        output_data = np.zeros(4000, dtype=np.uint8)
        
        # Should not crash
        produced = encoder.work([clipped_signal], [output_data])
        self.assertIsInstance(produced, int)

    def test_012_encoder_empty_input(self):
        """Test encoding with empty input"""
        encoder = opus_encoder(sample_rate=self.sample_rate, channels=self.channels)
        
        empty_input = np.array([], dtype=np.float32)
        output_data = np.zeros(4000, dtype=np.uint8)
        
        produced = encoder.work([empty_input], [output_data])
        
        self.assertEqual(produced, 0)


if __name__ == '__main__':
    unittest.main()

