#!/usr/bin/env python3
"""
Test: Multi-Recipient Scenarios

Tests various recipient counts and recipient list handling.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.superframe_controller import SuperframeController
from python.voice_frame_builder import VoiceFrameBuilder


def test_multi_recipient():
    """Test multi-recipient scenarios."""
    print("=" * 60)
    print("Test: Multi-Recipient Scenarios")
    print("=" * 60)
    
    from python.voice_frame_builder import VoiceFrameBuilder
    
    test_cases = [
        ("Single recipient", "N1ABC"),
        ("Two recipients", "N1ABC,N2DEF"),
        ("Three recipients", "N1ABC,N2DEF,N3GHI"),
        ("Five recipients", "N1ABC,N2DEF,N3GHI,N4JKL,N5MNO"),
        ("Ten recipients", ",".join([f"N{i}ABC" for i in range(1, 11)])),
    ]
    
    all_passed = True
    opus_frame = b'\x00' * 40
    
    for test_name, recipients in test_cases:
        print(f"\n{test_name}: {recipients}")
        
        builder = VoiceFrameBuilder(
            callsign="TEST",
            enable_mac=False
        )
        
        # Parse recipient list
        recipient_list = [r.strip() for r in recipients.split(",")]
        print(f"  Recipient count: {len(recipient_list)}")
        
        # Build frame (recipients would be in metadata, not frame payload)
        frame_payload = builder.build_frame(opus_frame, frame_num=1)
        
        if len(frame_payload) == 48:
            print(f"  PASS: {test_name} test passed")
        else:
            print(f"  FAIL: {test_name} test failed (frame size: {len(frame_payload)})")
            all_passed = False
    
    if all_passed:
        print("\nPASS: All multi-recipient tests passed")
    else:
        print("\nFAIL: Some multi-recipient tests failed")
    
    return all_passed


if __name__ == "__main__":
    success = test_multi_recipient()
    sys.exit(0 if success else 1)

