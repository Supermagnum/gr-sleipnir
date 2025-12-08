#!/usr/bin/env python3
"""
Test: Latency Measurement

Compares latency between encrypted and plaintext modes.
"""

import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.superframe_controller import SuperframeController
from python.voice_frame_builder import VoiceFrameBuilder
import os


def measure_frame_building_latency(builder, opus_frame, mac_key=None, iterations=100):
    """
    Measure frame building latency.
    
    Returns:
        List of latency measurements in seconds
    """
    latencies = []
    
    for i in range(iterations):
        start_time = time.perf_counter()
        frame_payload = builder.build_frame(opus_frame, frame_num=1)
        end_time = time.perf_counter()
        
        latency = end_time - start_time
        latencies.append(latency)
    
    return latencies


def test_latency_measurement():
    """Test latency measurement comparing encrypted vs plaintext."""
    print("=" * 60)
    print("Test: Latency Measurement")
    print("=" * 60)
    
    from python.voice_frame_builder import VoiceFrameBuilder
    
    opus_frame = b'\x00' * 40
    iterations = 100
    
    # Test 1: Plaintext mode
    print("\nTest 1: Plaintext mode (no encryption, no MAC)")
    builder_plain = VoiceFrameBuilder(
        callsign="TEST",
        enable_mac=False
    )
    
    latencies_plain = measure_frame_building_latency(
        builder_plain, opus_frame, iterations=iterations
    )
    
    if latencies_plain:
        avg_plain = statistics.mean(latencies_plain)
        min_plain = min(latencies_plain)
        max_plain = max(latencies_plain)
        std_plain = statistics.stdev(latencies_plain) if len(latencies_plain) > 1 else 0
        
        print(f"  Average latency: {avg_plain*1000:.3f} ms per frame")
        print(f"  Min latency: {min_plain*1000:.3f} ms")
        print(f"  Max latency: {max_plain*1000:.3f} ms")
        print(f"  Std deviation: {std_plain*1000:.3f} ms")
        print(f"  Superframe (24 frames): {avg_plain*24*1000:.2f} ms")
    
    # Test 2: Encrypted mode (with MAC)
    print("\nTest 2: Encrypted mode (with MAC)")
    mac_key = os.urandom(32)
    builder_enc = VoiceFrameBuilder(
        callsign="TEST",
        mac_key=mac_key,
        enable_mac=True
    )
    
    latencies_enc = measure_frame_building_latency(
        builder_enc, opus_frame, mac_key=mac_key, iterations=iterations
    )
    
    if latencies_enc:
        avg_enc = statistics.mean(latencies_enc)
        min_enc = min(latencies_enc)
        max_enc = max(latencies_enc)
        std_enc = statistics.stdev(latencies_enc) if len(latencies_enc) > 1 else 0
        
        print(f"  Average latency: {avg_enc*1000:.3f} ms per frame")
        print(f"  Min latency: {min_enc*1000:.3f} ms")
        print(f"  Max latency: {max_enc*1000:.3f} ms")
        print(f"  Std deviation: {std_enc*1000:.3f} ms")
        print(f"  Superframe (24 frames): {avg_enc*24*1000:.2f} ms")
    
    # Comparison
    if latencies_plain and latencies_enc:
        print("\nComparison:")
        overhead = ((avg_enc - avg_plain) / avg_plain) * 100
        overhead_ms = (avg_enc - avg_plain) * 1000
        
        print(f"  Encryption overhead: {overhead:.1f}% ({overhead_ms:.3f} ms per frame)")
        print(f"  Plaintext: {avg_plain*1000:.3f} ms per frame")
        print(f"  Encrypted: {avg_enc*1000:.3f} ms per frame")
        
        if overhead < 10:
            print("  PASS: Encryption overhead is acceptable (< 10%)")
        else:
            print(f"  WARNING: Encryption overhead is high ({overhead:.1f}%)")
    
    print("\nPASS: Latency measurement test completed")
    return True


if __name__ == "__main__":
    success = test_latency_measurement()
    sys.exit(0 if success else 1)

