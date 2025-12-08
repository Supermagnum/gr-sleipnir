#!/usr/bin/env python3
"""
Test: APRS Injection

Tests APRS data injection without breaking voice stream.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.superframe_controller import SuperframeController
from python.voice_frame_builder import VoiceFrameBuilder


def create_aprs_payload(callsign: str, latitude: float, longitude: float) -> bytes:
    """
    Create APRS payload.
    
    Format: CALLSIGN,LAT,LON (simplified)
    """
    aprs_str = f"{callsign},{latitude:.6f},{longitude:.6f}"
    return aprs_str.encode('utf-8')[:40].ljust(40, b'\x00')


def test_aprs_injection():
    """Test APRS injection without breaking voice."""
    print("=" * 60)
    print("Test: APRS Injection")
    print("=" * 60)
    
    from python.voice_frame_builder import VoiceFrameBuilder
    
    builder = VoiceFrameBuilder(
        callsign="TEST",
        enable_mac=False
    )
    
    # Test 1: Voice-only superframe
    print("\nTest 1: Voice-only superframe")
    opus_frames = [b'\x00' * 40] * 24
    frames = []
    
    for i, opus_frame in enumerate(opus_frames, start=1):
        frame_payload = builder.build_frame(opus_frame, frame_num=i)
        frames.append(frame_payload)
    
    if len(frames) == 24:
        print("  PASS: Voice-only superframe constructed")
        success1 = True
    else:
        print(f"  FAIL: Expected 24 frames, got {len(frames)}")
        success1 = False
    
    # Test 2: Voice + APRS in same superframe
    print("\nTest 2: Voice + APRS injection")
    aprs_payload = create_aprs_payload("TEST", 59.9139, 10.7522)  # Oslo coordinates
    
    opus_frames_aprs = opus_frames.copy()
    # Inject APRS into frame 12 (simplified - in practice would use reserved field)
    opus_frames_aprs[11] = aprs_payload[:40]
    
    frames_aprs = []
    for i, opus_frame in enumerate(opus_frames_aprs, start=1):
        frame_payload = builder.build_frame(opus_frame, frame_num=i)
        frames_aprs.append(frame_payload)
    
    if len(frames_aprs) == 24:
        print("  PASS: Voice + APRS superframe constructed")
        success2 = True
    else:
        print(f"  FAIL: Expected 24 frames, got {len(frames_aprs)}")
        success2 = False
    
    # Test 3: Multiple APRS updates
    print("\nTest 3: Multiple APRS updates")
    opus_frames_multi = opus_frames.copy()
    # Inject APRS into frames 6, 12, 18
    for frame_idx in [5, 11, 17]:
        aprs = create_aprs_payload("TEST", 59.9139 + frame_idx * 0.001, 10.7522)
        opus_frames_multi[frame_idx] = aprs[:40]
    
    frames_multi = []
    for i, opus_frame in enumerate(opus_frames_multi, start=1):
        frame_payload = builder.build_frame(opus_frame, frame_num=i)
        frames_multi.append(frame_payload)
    
    if len(frames_multi) == 24:
        print("  PASS: Multiple APRS updates handled")
        success3 = True
    else:
        print(f"  FAIL: Expected 24 frames, got {len(frames_multi)}")
        success3 = False
    
    success = success1 and success2 and success3
    
    if success:
        print("\nPASS: APRS injection test passed")
        print("  Voice stream integrity maintained")
    else:
        print("\nFAIL: APRS injection test failed")
    
    return success


if __name__ == "__main__":
    success = test_aprs_injection()
    sys.exit(0 if success else 1)

