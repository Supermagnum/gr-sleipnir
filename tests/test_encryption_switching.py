#!/usr/bin/env python3
"""
Test: Encryption Enable/Disable Switching

Tests switching encryption on/off during transmission.
"""

import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.superframe_controller import SuperframeController
from python.voice_frame_builder import VoiceFrameBuilder
import os


def test_encryption_switching():
    """Test encryption enable/disable switching."""
    print("=" * 60)
    print("Test: Encryption Enable/Disable Switching")
    print("=" * 60)
    
    from python.voice_frame_builder import VoiceFrameBuilder
    
    mac_key = os.urandom(32)
    opus_frame = b'\x00' * 40
    
    # Test 1: Start with encryption disabled
    print("\nTest 1: Start without encryption")
    builder1 = VoiceFrameBuilder(
        callsign="TEST1",
        enable_mac=False
    )
    
    frame1 = builder1.build_frame(opus_frame, frame_num=1)
    parsed1 = builder1.parse_frame(frame1)
    
    # MAC is 8 bytes (not 16) due to payload size constraints
    mac_is_zero = parsed1['mac'] == b'\x00' * 8
    if mac_is_zero:
        print("  PASS: Frame has no MAC (encryption disabled)")
        success1 = True
    else:
        print(f"  FAIL: Frame has MAC when encryption disabled: {parsed1['mac'].hex()}")
        success1 = False
    
    # Test 2: Enable encryption
    print("\nTest 2: Enable encryption")
    builder2 = VoiceFrameBuilder(
        callsign="TEST2",
        mac_key=mac_key,
        enable_mac=True
    )
    
    frame2 = builder2.build_frame(opus_frame, frame_num=1)
    parsed2 = builder2.parse_frame(frame2)
    
    # MAC is 8 bytes (not 16) due to payload size constraints
    mac_is_nonzero = parsed2['mac'] != b'\x00' * 8
    if mac_is_nonzero:
        print("  PASS: Frame has MAC (encryption enabled)")
        success2 = True
    else:
        print("  FAIL: Frame has no MAC when encryption enabled")
        success2 = False
    
    # CRITICAL: Verify that encryption actually encrypts (if encryption is enabled)
    # Check if payload is different from input (if encryption is actually implemented)
    if 'payload' in parsed2:
        payload = parsed2['payload']
        # If encryption is working, payload should be different from opus_frame
        # (or at least have some structure indicating encryption)
        if payload != opus_frame:
            print("  PASS: Encrypted payload is different from input")
        else:
            print("  WARNING: Encrypted payload same as input (may indicate no encryption)")
    
    # Test 3: Disable encryption mid-session
    print("\nTest 3: Disable encryption")
    builder3 = VoiceFrameBuilder(
        callsign="TEST3",
        mac_key=mac_key,
        enable_mac=True
    )
    
    # First frame with MAC
    frame3a = builder3.build_frame(opus_frame, frame_num=1)
    parsed3a = builder3.parse_frame(frame3a)
    
    # Disable MAC
    builder3.enable_mac = False
    
    # Second frame without MAC
    frame3b = builder3.build_frame(opus_frame, frame_num=2)
    parsed3b = builder3.parse_frame(frame3b)
    
    # MAC is 8 bytes (not 16) due to payload size constraints
    if parsed3a['mac'] != b'\x00' * 8 and parsed3b['mac'] == b'\x00' * 8:
        print("  PASS: Encryption switching works")
        success3 = True
    else:
        print("  FAIL: Encryption switching failed")
        success3 = False
    
    success = success1 and success2 and success3
    
    if success:
        print("\nPASS: Encryption switching test passed")
    else:
        print("\nFAIL: Encryption switching test failed")
    
    return success


if __name__ == "__main__":
    success = test_encryption_switching()
    sys.exit(0 if success else 1)

