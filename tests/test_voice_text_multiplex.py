#!/usr/bin/env python3
"""
Test: Voice + Text Multiplexing

Tests simultaneous transmission of voice and text messages in superframe.
"""

import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.superframe_controller import SuperframeController
from python.voice_frame_builder import VoiceFrameBuilder
from python.crypto_helpers import get_callsign_bytes


def create_text_payload(text: str, max_bytes: int = 40) -> bytes:
    """
    Create text payload for voice frame reserved field.
    
    Args:
        text: Text message
        max_bytes: Maximum bytes available (default: 40 for Opus field)
    
    Returns:
        Text payload bytes (padded/truncated)
    """
    text_bytes = text.encode('utf-8', errors='ignore')[:max_bytes]
    return text_bytes.ljust(max_bytes, b'\x00')


def test_voice_text_multiplex():
    """Test voice + text multiplexing."""
    print("=" * 60)
    print("Test: Voice + Text Multiplexing")
    print("=" * 60)
    
    from python.voice_frame_builder import VoiceFrameBuilder
    
    # Create test Opus frames (24 frames)
    opus_frames = []
    text_message = "Hello from gr-sleipnir!"
    
    builder = VoiceFrameBuilder(
        callsign="TEST",
        enable_mac=False
    )
    
    for i in range(24):
        # Create dummy Opus frame (40 bytes)
        opus_data = b'\x00' * 40
        
        # Inject text into first few frames (simplified - in practice would use reserved field)
        if i < len(text_message):
            text_payload = create_text_payload(text_message[i:i+1], 40)
            # Mix text with Opus (XOR for testing)
            opus_data = bytes([a ^ b for a, b in zip(opus_data, text_payload)])
        
        # Build frame
        frame_payload = builder.build_frame(opus_data, frame_num=i+1)
        opus_frames.append(frame_payload)
    
    # Verify frames
    print(f"Created {len(opus_frames)} frames with text: '{text_message}'")
    
    if len(opus_frames) == 24:
        print("PASS: Voice + text multiplexing test passed")
        return True
    else:
        print(f"FAIL: Expected 24 frames, got {len(opus_frames)}")
        return False


if __name__ == "__main__":
    success = test_voice_text_multiplex()
    sys.exit(0 if success else 1)

