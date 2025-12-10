#!/usr/bin/env python3
"""
Diagnostic script to isolate failure modes in Phase 2 tests.
Tests each problematic configuration individually to identify root causes.
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flowgraph_builder import build_test_flowgraph
from gnuradio import gr
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_configuration(modulation, crypto_mode, channel_name, snr_db):
    """Test a single configuration and return success/failure."""
    logger.info(f"Testing: {modulation}FSK, {crypto_mode}, {channel_name}, SNR={snr_db} dB")
    
    channel_config = {
        'name': channel_name,
        'type': 'clean' if channel_name == 'clean' else 'awgn' if channel_name == 'awgn' else 'fading',
        'snr_db': snr_db
    }
    
    if channel_name == 'rician':
        channel_config['fading_type'] = 'rician'
        channel_config['k_factor'] = 3.0
        channel_config['doppler_freq'] = 1.0
    elif channel_name == 'rayleigh':
        channel_config['fading_type'] = 'rayleigh'
        channel_config['doppler_freq'] = 1.0
    
    try:
        # Find WAV file
        wav_path = "wav/cq_pcm.wav"
        if not os.path.exists(wav_path):
            wav_path = os.path.join(Path(__file__).parent.parent, "wav", "cq_pcm.wav")
        
        output_wav = f"test_output_{modulation}fsk_{crypto_mode}_{channel_name}_snr{snr_db}.wav"
        tb = build_test_flowgraph(
            input_wav=wav_path,
            output_wav=output_wav,
            modulation=modulation,
            crypto_mode=crypto_mode,
            channel=channel_config,
            test_duration=2.0  # Short test
        )
        
        # Try to start the flowgraph
        tb.start()
        logger.info("  Flowgraph started successfully")
        
        # Run briefly
        import time
        time.sleep(0.5)
        
        # Stop and cleanup
        tb.stop()
        tb.wait()
        
        # Cleanup
        try:
            tb.lock()
            tb.unlock()
            tb.disconnect_all()
            del tb
            import gc
            gc.collect()
            gc.collect()
        except:
            pass
        
        logger.info("  ✓ Test passed")
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run diagnostic tests."""
    print("=" * 60)
    print("Phase 2 Failure Mode Diagnostics")
    print("=" * 60)
    print()
    
    # Test 1: 8FSK (should fail)
    print("Test 1: 8FSK mode")
    result1 = test_configuration(8, 'none', 'clean', 10.0)
    print()
    
    # Test 2: Crypto mode (should fail)
    print("Test 2: Crypto mode (sign)")
    result2 = test_configuration(4, 'sign', 'clean', 10.0)
    print()
    
    # Test 3: Rician fading (should fail)
    print("Test 3: Rician fading")
    result3 = test_configuration(4, 'none', 'rician', 10.0)
    print()
    
    # Test 4: Working configuration (should pass)
    print("Test 4: Working configuration (4FSK, none, clean)")
    result4 = test_configuration(4, 'none', 'clean', 10.0)
    print()
    
    print("=" * 60)
    print("Summary:")
    print(f"  8FSK: {'PASS' if result1 else 'FAIL'}")
    print(f"  Crypto: {'PASS' if result2 else 'FAIL'}")
    print(f"  Rician: {'PASS' if result3 else 'FAIL'}")
    print(f"  Baseline: {'PASS' if result4 else 'FAIL'}")
    print("=" * 60)

if __name__ == "__main__":
    main()

