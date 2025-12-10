#!/usr/bin/env python3
"""
Test script to verify flowgraph cleanup fixes work.
Runs a small subset of tests to check for memory leaks.
"""

import sys
import os
import time
import gc
import tracemalloc
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import test suite
sys.path.insert(0, str(Path(__file__).parent))
from test_comprehensive import ComprehensiveTestSuite
from flowgraph_builder import build_test_flowgraph
from gnuradio import gr

def test_cleanup_between_tests():
    """Test that flowgraphs are properly cleaned up between tests."""
    print("=== Testing Flowgraph Cleanup ===")
    print()
    
    # Test scenarios: mix of clean and AWGN to catch the failure pattern
    test_scenarios = [
        {'modulation': 4, 'crypto_mode': 'none', 'channel': {'name': 'clean', 'type': 'clean'}, 'snr_db': 10.0, 'phase': 2},
        {'modulation': 4, 'crypto_mode': 'none', 'channel': {'name': 'awgn', 'type': 'awgn'}, 'snr_db': 10.0, 'phase': 2},
        {'modulation': 4, 'crypto_mode': 'none', 'channel': {'name': 'clean', 'type': 'clean'}, 'snr_db': 10.0, 'phase': 2},
        {'modulation': 4, 'crypto_mode': 'none', 'channel': {'name': 'awgn', 'type': 'awgn'}, 'snr_db': 10.0, 'phase': 2},
        {'modulation': 8, 'crypto_mode': 'none', 'channel': {'name': 'clean', 'type': 'clean'}, 'snr_db': 10.0, 'phase': 2},
    ]
    
    # Start memory tracking
    tracemalloc.start()
    initial_snapshot = tracemalloc.take_snapshot()
    
    suite = ComprehensiveTestSuite('tests/config_comprehensive.yaml')
    
    results = []
    for i, scenario in enumerate(test_scenarios):
        print(f"Test {i+1}/{len(test_scenarios)}: {scenario['modulation']}FSK, {scenario['crypto_mode']}, {scenario['channel']['name']}, SNR={scenario['snr_db']} dB")
        
        # Force garbage collection before test
        gc.collect()
        pre_snapshot = tracemalloc.take_snapshot()
        
        try:
            result = suite.run_test_scenario(scenario)
            results.append(result)
            
            # Force garbage collection after test
            gc.collect()
            post_snapshot = tracemalloc.take_snapshot()
            
            # Check memory growth
            top_stats = post_snapshot.compare_to(pre_snapshot, 'lineno')
            memory_growth = sum(stat.size_diff for stat in top_stats[:10])
            
            if 'error' in result:
                print(f"  ✗ FAILED: {result.get('error', 'Unknown error')}")
            elif result.get('validation', {}).get('overall_pass', False):
                print(f"  ✓ PASSED")
            else:
                print(f"  ✗ FAILED: Validation failed")
            
            print(f"  Memory growth: {memory_growth / 1024:.2f} KB")
            
            # Small delay to allow cleanup
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  ✗ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append({'error': str(e)})
    
    # Final memory check
    final_snapshot = tracemalloc.take_snapshot()
    total_growth = final_snapshot.compare_to(initial_snapshot, 'lineno')
    total_memory_growth = sum(stat.size_diff for stat in total_growth[:20])
    
    print()
    print("=== Memory Analysis ===")
    print(f"Total memory growth: {total_memory_growth / 1024:.2f} KB")
    print(f"Average per test: {total_memory_growth / len(test_scenarios) / 1024:.2f} KB")
    
    # Show top memory consumers
    print("\nTop memory growth locations:")
    for stat in total_growth[:10]:
        if stat.size_diff > 0:
            print(f"  {stat.traceback.format()[-1]}: {stat.size_diff / 1024:.2f} KB")
    
    tracemalloc.stop()
    
    # Summary
    passed = sum(1 for r in results if r.get('validation', {}).get('overall_pass', False))
    failed = len(results) - passed
    
    print()
    print("=== Test Summary ===")
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    
    return results

def test_explicit_block_destruction():
    """Test if explicit block destruction helps."""
    print("\n=== Testing Explicit Block Destruction ===")
    print()
    
    from gnuradio import blocks, analog
    
    for i in range(5):
        print(f"Test {i+1}/5: Creating and destroying blocks...")
        
        # Create blocks
        noise = analog.noise_source_c(analog.GR_GAUSSIAN, 0.1, i)
        adder = blocks.add_cc(1)
        sink = blocks.null_sink(gr.sizeof_gr_complex)
        
        # Create flowgraph
        tb = gr.top_block()
        tb.connect(noise, adder)
        tb.connect(adder, sink)
        
        # Run briefly
        tb.start()
        time.sleep(0.1)
        tb.stop()
        tb.wait()
        
        # Try explicit cleanup
        try:
            tb.lock()
            tb.unlock()
            # Delete blocks explicitly
            del noise
            del adder
            del sink
            del tb
            gc.collect()
        except Exception as e:
            print(f"  Warning during cleanup: {e}")
        
        print(f"  ✓ Completed")
    
    print("  Explicit destruction test completed")

if __name__ == "__main__":
    print("Testing cleanup fixes...")
    print()
    
    # Test 1: Cleanup between tests
    results = test_cleanup_between_tests()
    
    # Test 2: Explicit block destruction
    test_explicit_block_destruction()
    
    print("\n=== All Tests Complete ===")

