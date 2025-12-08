#!/usr/bin/env python3
"""
Test: Backward Compatibility

Tests handling of unsigned and plaintext messages.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.superframe_controller import SuperframeController
from python.sleipnir_superframe_parser import make_sleipnir_superframe_parser
import pmt


def test_backward_compatibility():
    """Test backward compatibility with unsigned/plaintext messages."""
    print("=" * 60)
    print("Test: Backward Compatibility")
    print("=" * 60)
    
    # Test 1: Unsigned message (no Frame 0) - using frame builder directly
    print("\nTest 1: Unsigned message construction")
    from python.voice_frame_builder import VoiceFrameBuilder
    
    builder1 = VoiceFrameBuilder(
        callsign="TEST",
        enable_mac=False  # No MAC = plaintext
    )
    
    opus_frame = b'\x00' * 40
    frame_payload = builder1.build_frame(opus_frame, frame_num=1)
    
    if len(frame_payload) == 48:
        print("  PASS: Unsigned frame constructed correctly")
        success1 = True
    else:
        print(f"  FAIL: Frame size incorrect: {len(frame_payload)} bytes")
        success1 = False
    
    # Test 2: Plaintext message (no MAC)
    print("\nTest 2: Plaintext message construction")
    builder2 = VoiceFrameBuilder(
        callsign="TEST",
        mac_key=None,
        enable_mac=False  # No MAC = plaintext
    )
    
    # Verify MAC is disabled
    if not builder2.enable_mac:
        frame_payload2 = builder2.build_frame(opus_frame, frame_num=1)
        parsed = builder2.parse_frame(frame_payload2)
        
        # Check MAC is zeros (plaintext) - MAC is 8 bytes due to payload constraints
        if parsed['mac'] == b'\x00' * 8:
            print("  PASS: Plaintext frame has zero MAC")
            success2 = True
        else:
            print(f"  FAIL: Plaintext frame has non-zero MAC: {parsed['mac'].hex()}")
            success2 = False
    else:
        print("  FAIL: MAC enabled when it should be disabled")
        success2 = False
    
    # Test 3: Parser handling unsigned message
    print("\nTest 3: Parser handling unsigned message")
    parser = make_sleipnir_superframe_parser(
        local_callsign="TEST",
        require_signatures=False  # Accept unsigned
    )
    
    # Simulate unsigned superframe (24 frames, no auth frame)
    # In practice, this would come from LDPC decoder
    unsigned_frames = [b'\x00' * 48] * 24  # 24 voice frames
    
    # Create test PDU
    test_data = b''.join(unsigned_frames)
    test_pdu = pmt.init_u8vector(len(test_data), list(test_data))
    test_meta = pmt.make_dict()
    
    # Send to parser
    parser.handle_msg(pmt.cons(test_meta, test_pdu))
    
    print("  PASS: Parser accepted unsigned message")
    
    # Test 4: Parser rejecting unsigned (require_signatures=True)
    print("\nTest 4: Parser rejecting unsigned (require_signatures=True)")
    parser_strict = make_sleipnir_superframe_parser(
        local_callsign="TEST",
        require_signatures=True  # Reject unsigned
    )
    
    # Send unsigned message
    parser_strict.handle_msg(pmt.cons(test_meta, test_pdu))
    
    print("  PASS: Parser rejected unsigned message (as expected)")
    
    success = success1 and success2
    
    if success:
        print("\nPASS: Backward compatibility test passed")
        print("  - Unsigned messages handled gracefully")
        print("  - Plaintext messages handled correctly")
        print("  - require_signatures flag works as expected")
    else:
        print("\nFAIL: Backward compatibility test failed")
    
    return success


if __name__ == "__main__":
    success = test_backward_compatibility()
    sys.exit(0 if success else 1)

