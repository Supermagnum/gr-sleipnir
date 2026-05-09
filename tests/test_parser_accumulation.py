#!/usr/bin/env python3
"""
Test parser frame accumulation behavior.

This test investigates why the parser's frame_buffer becomes empty
even when frames are being sent to it.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

import numpy as np
from sleipnir_superframe_parser import sleipnir_superframe_parser
import pmt

def test_parser_accumulation():
    """Test parser frame accumulation behavior."""
    
    print("=" * 70)
    print("PARSER FRAME ACCUMULATION TEST")
    print("=" * 70)
    print()
    
    # Initialize parser
    parser = sleipnir_superframe_parser(
        local_callsign="N0CALL",
        enable_sync_detection=False,  # Disable sync detection for this test
        mac_key=None
    )
    
    print(f"Initial state:")
    print(f"  Frame buffer: {len(parser.frame_buffer)} frames")
    print(f"  Total frames received: {parser.total_frames_received}")
    print(f"  Frame errors: {parser.frame_error_count}")
    print()
    
    # Test 1: Send frames one at a time and check buffer after each
    print("=" * 70)
    print("TEST 1: Send frames one at a time")
    print("=" * 70)
    
    # Create 25 test frames (1 auth + 24 voice)
    # Use random data (not realistic, but enough to test accumulation)
    frames = []
    frames.append(b'\x00' * 64)  # Auth frame (64 bytes)
    for i in range(24):
        frames.append(b'\x00' * 48)  # Voice frames (48 bytes each)
    
    print(f"Sending {len(frames)} frames (1 auth + 24 voice)")
    print()
    
    for i, frame in enumerate(frames):
        frame_pmt = pmt.init_u8vector(len(frame), list(frame))
        meta = pmt.make_dict()
        meta = pmt.dict_add(meta, pmt.intern("frame_size"), pmt.from_long(len(frame)))
        meta = pmt.dict_add(meta, pmt.intern("frame_num"), pmt.from_long(i))
        
        print(f"  Sending frame {i}: {len(frame)} bytes")
        print(f"    Buffer before: {len(parser.frame_buffer)} frames")
        
        # Call handle_msg
        parser.handle_msg(pmt.cons(meta, frame_pmt))
        
        print(f"    Buffer after: {len(parser.frame_buffer)} frames")
        print(f"    Total received: {parser.total_frames_received}")
        print(f"    Frame errors: {parser.frame_error_count}")
        print()
        
        # Check if buffer was cleared
        if len(parser.frame_buffer) == 0 and i < 24:
            print(f"    WARNING: Buffer cleared after frame {i} (before superframe complete)")
    
    print(f"Final state:")
    print(f"  Frame buffer: {len(parser.frame_buffer)} frames")
    print(f"  Total frames received: {parser.total_frames_received}")
    print(f"  Frame errors: {parser.frame_error_count}")
    print()
    
    # Test 2: Check what process_superframe does
    print("=" * 70)
    print("TEST 2: Check process_superframe behavior")
    print("=" * 70)
    
    # Reset parser
    parser.frame_buffer = []
    parser.total_frames_received = 0
    parser.frame_error_count = 0
    
    # Add 25 frames to buffer manually
    parser.frame_buffer = frames.copy()
    print(f"Manually added {len(parser.frame_buffer)} frames to buffer")
    print()
    
    # Check if we have enough frames
    if len(parser.frame_buffer) >= 25:
        print(f"Buffer has {len(parser.frame_buffer)} frames (need 25 for superframe with auth)")
        superframe_frames = parser.frame_buffer[:25]
        print(f"Extracting {len(superframe_frames)} frames for processing")
        
        # Call process_superframe
        result = parser.process_superframe(superframe_frames)
        
        print(f"process_superframe returned: {result is not None}")
        if result:
            opus_frames, status = result
            print(f"  Opus frames: {len(opus_frames)}")
            print(f"  Status: {status}")
        else:
            print(f"  process_superframe returned None (frames failed validation)")
        
        print(f"Buffer after process_superframe: {len(parser.frame_buffer)} frames")
        print(f"  (Note: frames should be removed from buffer even if process_superframe returns None)")
    print()
    
    # Test 3: Check handle_msg processing logic
    print("=" * 70)
    print("TEST 3: Check handle_msg processing logic")
    print("=" * 70)
    
    # Reset parser
    parser.frame_buffer = []
    parser.total_frames_received = 0
    parser.frame_error_count = 0
    
    # Send frames and track buffer state
    buffer_states = []
    for i, frame in enumerate(frames):
        frame_pmt = pmt.init_u8vector(len(frame), list(frame))
        meta = pmt.make_dict()
        meta = pmt.dict_add(meta, pmt.intern("frame_size"), pmt.from_long(len(frame)))
        meta = pmt.dict_add(meta, pmt.intern("frame_num"), pmt.from_long(i))
        
        buffer_before = len(parser.frame_buffer)
        parser.handle_msg(pmt.cons(meta, frame_pmt))
        buffer_after = len(parser.frame_buffer)
        
        buffer_states.append((i, buffer_before, buffer_after))
    
    print("Buffer state after each frame:")
    for i, before, after in buffer_states:
        change = after - before
        print(f"  Frame {i}: {before} -> {after} (change: {change:+d})")
        if change < 0:
            print(f"    WARNING: Buffer decreased! Frames were removed.")
    
    print()
    print(f"Final buffer: {len(parser.frame_buffer)} frames")
    print()
    
    # Analysis
    print("=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    print()
    
    if len(parser.frame_buffer) == 0:
        print("ISSUE IDENTIFIED: Frame buffer is empty after sending all frames")
        print()
        print("Root cause:")
        print("  1. Frames are added to buffer in handle_msg()")
        print("  2. handle_msg() immediately checks if buffer has 24-25 frames")
        print("  3. If yes, it calls process_superframe() and removes frames from buffer")
        print("  4. Even if process_superframe() returns None (validation failed),")
        print("     frames are still removed from buffer")
        print()
        print("This means:")
        print("  - When frames fail validation, they're removed but not counted as errors")
        print("  - Buffer becomes empty even though frames were received")
        print("  - This explains why frame_buffer has 0 frames but total_frames_received = 25")
    else:
        print("Buffer still has frames - issue may be elsewhere")
    
    return len(parser.frame_buffer) > 0

if __name__ == '__main__':
    success = test_parser_accumulation()
    sys.exit(0 if success else 1)

