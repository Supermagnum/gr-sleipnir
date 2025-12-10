#!/usr/bin/env python3
"""
Single test to verify FER tracking fix
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

# Change to project root
os.chdir(project_root)

from flowgraph_builder import build_test_flowgraph
from metrics_collector import MetricsCollectorBlock, MetricsCollector
from test_utils import compute_warpq
from gnuradio import gr

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

print('=' * 70)
print('SINGLE TEST VERIFICATION')
print('=' * 70)
print()

# Test configuration: Low SNR to ensure some errors occur
input_wav = 'wav/cq_pcm.wav'
output_wav = 'test_fer_verification.wav'
os.makedirs(os.path.dirname(output_wav) if os.path.dirname(output_wav) else '.', exist_ok=True)

print('Test Configuration:')
print(f'  Input: {input_wav}')
print(f'  Output: {output_wav}')
print(f'  Modulation: 4FSK')
print(f'  Crypto: none')
print(f'  Channel: clean')
print(f'  SNR: -5.0 dB (low SNR to generate errors)')
print(f'  Duration: 5.0 seconds')
print()

try:
    # Build flowgraph (it creates metrics_block internally)
    metrics_aggregator = MetricsCollector()
    metrics_aggregator.start_test()
    
    tb = build_test_flowgraph(
        input_wav=input_wav,
        output_wav=output_wav,
        modulation=4,
        crypto_mode='none',
        channel={'name': 'clean', 'type': 'clean'},
        snr_db=-5.0,
        audio_samp_rate=8000.0,
        rf_samp_rate=48000.0,
        symbol_rate=4800.0,
        fsk_deviation=2400.0,
        auth_matrix_file='ldpc_matrices/ldpc_auth_768_256.alist',
        voice_matrix_file='ldpc_matrices/ldpc_voice_576_384.alist',
        test_duration=5.0
    )
    
    # Get metrics block from flowgraph
    metrics_block = tb._metrics_block if hasattr(tb, '_metrics_block') else None
    
    print('Flowgraph created. Starting test...')
    tb.start()
    time.sleep(6.0)  # Run slightly longer than test_duration
    tb.stop()
    tb.wait()
    
    # Get metrics from block
    block_metrics = metrics_block.get_metrics()
    metrics_aggregator.frame_count = block_metrics.get('frame_count', 0)
    metrics_aggregator.frame_error_count = block_metrics.get('frame_error_count', 0)
    metrics_aggregator.superframe_count = block_metrics.get('superframe_count', 0)
    if 'total_frames_received' in block_metrics:
        metrics_aggregator._total_frames_received = block_metrics.get('total_frames_received', 0)
    
    # Compute final metrics
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
    
    print()
    print('=' * 70)
    print('TEST RESULTS')
    print('=' * 70)
    print()
    print(f'frame_count: {test_metrics.get("frame_count", "N/A")}')
    print(f'frame_error_count: {test_metrics.get("frame_error_count", "N/A")}')
    print(f'total_frames_received: {test_metrics.get("total_frames_received", "N/A")}')
    fer = test_metrics.get('fer')
    fer_str = f'{fer:.4f}' if isinstance(fer, (int, float)) else str(fer)
    print(f'fer: {fer_str}')
    print(f'superframe_count: {test_metrics.get("superframe_count", "N/A")}')
    print()
    
    # Verification
    frame_count = test_metrics.get('frame_count', 0)
    frame_error_count = test_metrics.get('frame_error_count', 0)
    total_frames_received = test_metrics.get('total_frames_received')
    fer = test_metrics.get('fer')
    
    print('Verification:')
    print('-' * 70)
    if total_frames_received is not None and total_frames_received > 0:
        print('✓ total_frames_received is tracked')
    else:
        print('✗ total_frames_received is NOT tracked')
    
    if frame_error_count > 0:
        print(f'✓ frame_error_count is non-zero: {frame_error_count}')
    else:
        print(f'✗ frame_error_count is still 0 (should be > 0 at low SNR)')
    
    if fer is not None and isinstance(fer, (int, float)) and fer > 0:
        print(f'✓ FER is non-zero: {fer:.4f}')
    else:
        print(f'✗ FER is still 0.0 (should be > 0 at low SNR)')
    
    if total_frames_received is not None and frame_count > 0:
        expected_errors = total_frames_received - frame_count
        if abs(frame_error_count - expected_errors) < max(expected_errors * 0.2, 10):  # Within 20% or 10 frames
            print(f'✓ frame_error_count ({frame_error_count}) approximately matches expected ({expected_errors})')
        else:
            print(f'⚠ frame_error_count ({frame_error_count}) differs from expected ({expected_errors})')
            print(f'  Difference: {abs(frame_error_count - expected_errors)} frames')
    
    print()
    print('=' * 70)
    
    # Final verdict
    if total_frames_received and frame_error_count > 0 and fer and fer > 0:
        print('SUCCESS: FER tracking is working correctly!')
        exit_code = 0
    else:
        print('FAILURE: FER tracking still has issues')
        exit_code = 1
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    exit_code = 1

if __name__ == '__main__':
    sys.exit(exit_code if 'exit_code' in locals() else 0)

