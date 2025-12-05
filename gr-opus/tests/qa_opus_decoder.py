#!/usr/bin/env python3
"""
Unit tests for Opus decoder block
"""

import unittest
import numpy as np
from gnuradio import gr, blocks
import sys
import os
import opuslib

# Add parent directory to path to import gr_opus
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from opus_decoder import opus_decoder
from opus_encoder import opus_encoder


class qa_opus_decoder(unittest.TestCase):
    """Test suite for opus_decoder block"""

    def setUp(self):
        """Set up test fixtures"""
        self.tb = gr.top_block()
        self.sample_rate = 48000
        self.channels = 1
        self.frame_size = int(self.sample_rate * 0.020)  # 20ms frames

    def tearDown(self):
        """Clean up after tests"""
        self.tb = None

    def _generate_encoded_packet(self, sample_rate=48000, channels=1):
        """Helper to generate a valid Opus-encoded packet"""
        encoder = opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_AUDIO)
        encoder.bitrate = 64000
        
        # Generate test signal
        frame_size = int(sample_rate * 0.020)
        t = np.linspace(0, 0.020, frame_size, False)
        test_signal = np.sin(2 * np.pi * 440 * t, dtype=np.float32)
        
        # Convert to int16
        int16_samples = (test_signal * 32767.0).astype(np.int16)
        
        # Encode
        encoded = encoder.encode(int16_samples.tobytes(), frame_size)
        return encoded

    def test_001_decoder_initialization(self):
        """Test decoder initialization with default parameters"""
        decoder = opus_decoder()
        self.assertEqual(decoder.sample_rate, 48000)
        self.assertEqual(decoder.channels, 1)
        self.assertEqual(decoder.packet_size, 0)
        self.assertIsNotNone(decoder.decoder)

    def test_002_decoder_initialization_custom_params(self):
        """Test decoder initialization with custom parameters"""
        decoder = opus_decoder(
            sample_rate=16000,
            channels=2,
            packet_size=100
        )
        self.assertEqual(decoder.sample_rate, 16000)
        self.assertEqual(decoder.channels, 2)
        self.assertEqual(decoder.packet_size, 100)
        self.assertEqual(decoder.frame_size, int(16000 * 0.020))

    def test_003_decoder_sample_rates(self):
        """Test decoder with different sample rates"""
        for rate in [8000, 12000, 16000, 24000, 48000]:
            decoder = opus_decoder(sample_rate=rate)
            self.assertEqual(decoder.sample_rate, rate)
            self.assertEqual(decoder.frame_size, int(rate * 0.020))

    def test_004_decoder_mono_stereo(self):
        """Test decoder with mono and stereo"""
        decoder_mono = opus_decoder(channels=1)
        self.assertEqual(decoder_mono.channels, 1)
        
        decoder_stereo = opus_decoder(channels=2)
        self.assertEqual(decoder_stereo.channels, 2)

    def test_005_decoder_fixed_packet_size(self):
        """Test decoder with fixed packet size"""
        # Generate encoded packet
        encoded_packet = self._generate_encoded_packet(
            sample_rate=self.sample_rate,
            channels=self.channels
        )
        packet_size = len(encoded_packet)
        
        decoder = opus_decoder(
            sample_rate=self.sample_rate,
            channels=self.channels,
            packet_size=packet_size
        )
        
        # Convert to uint8 array
        input_data = np.frombuffer(encoded_packet, dtype=np.uint8)
        output_data = np.zeros(self.frame_size * 2, dtype=np.float32)
        
        produced = decoder.work([input_data], [output_data])
        
        self.assertGreater(produced, 0)
        # Check that decoded samples are reasonable
        self.assertGreater(np.max(np.abs(output_data[:produced])), 0)

    def test_006_decoder_variable_packet_size(self):
        """Test decoder with variable packet size (auto-detect)"""
        # Generate encoded packet
        encoded_packet = self._generate_encoded_packet(
            sample_rate=self.sample_rate,
            channels=self.channels
        )
        
        decoder = opus_decoder(
            sample_rate=self.sample_rate,
            channels=self.channels,
            packet_size=0  # Auto-detect
        )
        
        # Convert to uint8 array
        input_data = np.frombuffer(encoded_packet, dtype=np.uint8)
        output_data = np.zeros(self.frame_size * 2, dtype=np.float32)
        
        produced = decoder.work([input_data], [output_data])
        
        self.assertGreater(produced, 0)

    def test_007_decoder_partial_packet(self):
        """Test decoder with partial packet (should buffer)"""
        # Generate encoded packet
        encoded_packet = self._generate_encoded_packet(
            sample_rate=self.sample_rate,
            channels=self.channels
        )
        
        decoder = opus_decoder(
            sample_rate=self.sample_rate,
            channels=self.channels,
            packet_size=len(encoded_packet)
        )
        
        # Send partial packet
        partial_size = len(encoded_packet) // 2
        input_data = np.frombuffer(encoded_packet[:partial_size], dtype=np.uint8)
        output_data = np.zeros(self.frame_size * 2, dtype=np.float32)
        
        produced = decoder.work([input_data], [output_data])
        
        # Should not produce output yet (partial packet)
        self.assertEqual(produced, 0)
        # Buffer should contain the partial packet
        self.assertGreater(len(decoder.packet_buffer), 0)

    def test_008_decoder_multiple_packets(self):
        """Test decoder with multiple packets"""
        # Generate multiple encoded packets
        encoded_packet = self._generate_encoded_packet(
            sample_rate=self.sample_rate,
            channels=self.channels
        )
        packet_size = len(encoded_packet)
        
        decoder = opus_decoder(
            sample_rate=self.sample_rate,
            channels=self.channels,
            packet_size=packet_size
        )
        
        # Create input with multiple packets
        num_packets = 3
        input_data = np.tile(np.frombuffer(encoded_packet, dtype=np.uint8), num_packets)
        output_data = np.zeros(self.frame_size * num_packets * 2, dtype=np.float32)
        
        produced = decoder.work([input_data], [output_data])
        
        self.assertGreater(produced, 0)

    def test_009_decoder_stereo(self):
        """Test decoder with stereo"""
        # Generate stereo encoded packet
        encoded_packet = self._generate_encoded_packet(
            sample_rate=self.sample_rate,
            channels=2
        )
        
        decoder = opus_decoder(
            sample_rate=self.sample_rate,
            channels=2,
            packet_size=len(encoded_packet)
        )
        
        input_data = np.frombuffer(encoded_packet, dtype=np.uint8)
        output_data = np.zeros(self.frame_size * 2 * 2, dtype=np.float32)
        
        produced = decoder.work([input_data], [output_data])
        
        self.assertGreater(produced, 0)

    def test_010_decoder_invalid_packet(self):
        """Test decoder with invalid packet (should not crash)"""
        decoder = opus_decoder(
            sample_rate=self.sample_rate,
            channels=self.channels,
            packet_size=0  # Auto-detect
        )
        
        # Create invalid packet (random data)
        invalid_packet = np.random.randint(0, 256, 100, dtype=np.uint8)
        output_data = np.zeros(self.frame_size * 2, dtype=np.float32)
        
        # Should not crash
        produced = decoder.work([invalid_packet], [output_data])
        self.assertIsInstance(produced, int)

    def test_011_decoder_empty_input(self):
        """Test decoder with empty input"""
        decoder = opus_decoder(
            sample_rate=self.sample_rate,
            channels=self.channels
        )
        
        empty_input = np.array([], dtype=np.uint8)
        output_data = np.zeros(self.frame_size * 2, dtype=np.float32)
        
        produced = decoder.work([empty_input], [output_data])
        
        self.assertEqual(produced, 0)

    def test_012_decoder_output_range(self):
        """Test that decoder output is in valid range [-1.0, 1.0]"""
        # Generate encoded packet
        encoded_packet = self._generate_encoded_packet(
            sample_rate=self.sample_rate,
            channels=self.channels
        )
        
        decoder = opus_decoder(
            sample_rate=self.sample_rate,
            channels=self.channels,
            packet_size=len(encoded_packet)
        )
        
        input_data = np.frombuffer(encoded_packet, dtype=np.uint8)
        output_data = np.zeros(self.frame_size * 2, dtype=np.float32)
        
        produced = decoder.work([input_data], [output_data])
        
        if produced > 0:
            # Check that samples are in reasonable range
            # (allowing some margin for rounding)
            self.assertLessEqual(np.max(np.abs(output_data[:produced])), 1.1)


if __name__ == '__main__':
    unittest.main()

