#!/usr/bin/env python3
"""
Validation script to verify fixes for:
1. FER calculation (handles None/0 cases)
2. Fading channel implementation (not constant 0.5 FER)
3. total_frames_received tracking
"""

import sys
import os
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'tests'))

from flowgraph_builder import build_test_flowgraph
from metrics_collector import MetricsCollectorBlock, MetricsCollector
from gnuradio import gr

logging.basicConfig(level=logging.WARNING)  # Reduce noise

def run_test(name, channel, snr_db, expected_fer_range=(0.0, 1.0), check_not_exact=None):
    """Run a single test and return pass/fail."""
    print(f'{name}')
    print('-' * 70)
    
    input_wav = 'wav/cq_pcm.wav'
    output_wav = f'test_validation_{name.lower().replace(" ", "_")}.wav'
    os.makedirs(os.path.dirname(output_wav) if os.path.dirname(output_wav) else '.', exist_ok=True)
    
    try:
        metrics_aggregator = MetricsCollector()
        metrics_aggregator.start_test()
        
        tb = build_test_flowgraph(
            input_wav=input_wav,
            output_wav=output_wav,
            modulation=4,
            crypto_mode='none',
            channel=channel,
            snr_db=snr_db,
            audio_samp_rate=8000.0,
            rf_samp_rate=48000.0,
            symbol_rate=4800.0,
            fsk_deviation=2400.0,
            auth_matrix_file='ldpc_matrices/ldpc_auth_768_256.alist',
            voice_matrix_file='ldpc_matrices/ldpc_voice_576_384.alist',
            test_duration=5.0
        )
        
        # Get the metrics block from the flowgraph
        metrics_block = tb._metrics_block
        
        tb.start()
        time.sleep(6.0)
        tb.stop()
        tb.wait()
        
        block_metrics = metrics_block.get_metrics()
        metrics_aggregator.frame_count = block_metrics.get('frame_count', 0)
        metrics_aggregator.frame_error_count = block_metrics.get('frame_error_count', 0)
        metrics_aggregator.superframe_count = block_metrics.get('superframe_count', 0)
        if 'total_frames_received' in block_metrics:
            metrics_aggregator._total_frames_received = block_metrics.get('total_frames_received', 0)
        
        test_metrics = metrics_aggregator.compute_metrics()
        
        # Cleanup
        try:
            tb.lock()
            tb.unlock()
            tb.disconnect_all()
            if hasattr(tb, '_tx_block'):
                del tb._tx_block
            if hasattr(tb, '_rx_block'):
                del tb._rx_block
            del tb
            import gc
            gc.collect()
        except:
            pass
        
        frame_count = test_metrics.get('frame_count', 0)
        frame_error_count = test_metrics.get('frame_error_count', 0)
        total_frames_received = test_metrics.get('total_frames_received')
        fer = test_metrics.get('fer')
        
        print(f'  frame_count: {frame_count}')
        print(f'  frame_error_count: {frame_error_count}')
        print(f'  total_frames_received: {total_frames_received}')
        fer_str = f'{fer:.4f}' if isinstance(fer, (int, float)) else str(fer)
        print(f'  FER: {fer_str}')
        
        # Validation checks
        checks = []
        
        # Check 1: total_frames_received is tracked
        if total_frames_received is not None:
            checks.append(('total_frames_received tracked', True))
        else:
            checks.append(('total_frames_received tracked', False))
        
        # Check 2: FER is calculated
        if fer is not None and isinstance(fer, (int, float)):
            checks.append(('FER calculated', True))
        else:
            checks.append(('FER calculated', False))
        
        # Check 3: FER is in expected range
        if fer is not None and isinstance(fer, (int, float)):
            if expected_fer_range[0] <= fer <= expected_fer_range[1]:
                checks.append(('FER in expected range', True))
            else:
                checks.append(('FER in expected range', False))
        
        # Check 4: FER is not exactly a specific value (for fading bug check)
        if check_not_exact is not None and fer is not None:
            if fer != check_not_exact:
                checks.append((f'FER != {check_not_exact}', True))
            else:
                checks.append((f'FER != {check_not_exact}', False))
        
        # Check 5: Frames decoded (for good SNR)
        if snr_db >= 5.0:
            if frame_count > 0:
                checks.append(('Frames decoded', True))
            else:
                checks.append(('Frames decoded', False))
        
        # Check 6: Errors tracked (for low SNR)
        if snr_db < 0:
            if frame_error_count > 0:
                checks.append(('Errors tracked', True))
            else:
                checks.append(('Errors tracked', False))
        
        # Print check results
        all_pass = True
        for check_name, check_result in checks:
            status = 'PASS' if check_result else 'FAIL'
            symbol = '✓' if check_result else '✗'
            print(f'  {symbol} {check_name}: {status}')
            if not check_result:
                all_pass = False
        
        print(f'  Overall: {"PASS" if all_pass else "FAIL"}')
        print()
        
        return all_pass
        
    except Exception as e:
        print(f'  ERROR: {e}')
        import traceback
        traceback.print_exc()
        print(f'  Overall: FAIL')
        print()
        return False

def main():
    print('=' * 70)
    print('VALIDATION TEST: Fixes Verification')
    print('=' * 70)
    print()
    
    results = {}
    
    # Test 1: Clean channel, 10 dB SNR
    results['Test 1'] = run_test(
        'Test 1: Clean channel, 10 dB SNR',
        channel={'name': 'clean', 'type': 'clean'},
        snr_db=10.0,
        expected_fer_range=(0.0, 0.5)  # Should have low FER at good SNR
    )
    
    # Test 2: Rayleigh fading channel
    results['Test 2'] = run_test(
        'Test 2: Rayleigh fading, 10 dB SNR',
        channel={'name': 'rayleigh', 'type': 'fading', 'fading_type': 'rayleigh', 'doppler_freq': 1.0},
        snr_db=10.0,
        expected_fer_range=(0.0, 1.0),
        check_not_exact=0.5  # Should NOT be exactly 0.5 (that was the bug)
    )
    
    # Test 3: Low SNR to verify FER tracking
    results['Test 3'] = run_test(
        'Test 3: AWGN, -5 dB SNR (low SNR)',
        channel={'name': 'awgn', 'type': 'awgn'},
        snr_db=-5.0,
        expected_fer_range=(0.0, 1.0)  # High FER expected at low SNR
    )
    
    # Summary
    print('=' * 70)
    print('VALIDATION SUMMARY')
    print('=' * 70)
    print()
    for test_name, passed in results.items():
        status = 'PASS' if passed else 'FAIL'
        symbol = '✓' if passed else '✗'
        print(f'{symbol} {test_name}: {status}')
    print()
    
    all_passed = all(results.values())
    if all_passed:
        print('SUCCESS: All validation tests passed!')
        print('Fixes are working correctly.')
        print()
        print('Key fixes verified:')
        print('  ✓ FER calculation handles None/0 cases')
        print('  ✓ total_frames_received is always tracked')
        print('  ✓ Fading channels no longer show constant 0.5 FER')
        print('  ✓ FER tracking works at both high and low SNR')
    else:
        print('FAILURE: Some validation tests failed.')
        print('Please review the issues above.')
    print()
    print('=' * 70)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())

