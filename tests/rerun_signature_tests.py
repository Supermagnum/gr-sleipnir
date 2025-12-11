#!/usr/bin/env python3
"""
Targeted re-run script for signature verification tests.

This script re-runs ONLY the sign/both crypto mode tests to get
accurate signature verification data after the placeholder fix.

Usage:
    python3 tests/rerun_signature_tests.py --config tests/config_comprehensive.yaml
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import yaml
import argparse
import json
from test_comprehensive import ComprehensiveTestSuite

def main():
    parser = argparse.ArgumentParser(description='Re-run signature verification tests')
    parser.add_argument('--config', default='tests/config_comprehensive.yaml',
                       help='Test configuration file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be tested without running')
    args = parser.parse_args()
    
    # Load test suite
    suite = ComprehensiveTestSuite(args.config)
    
    # Load existing results to identify sign/both tests
    results_file = suite.test_params.get('output', {}).get('results_json', 
                   'test-results-json/results.json')
    
    existing_results = []
    if os.path.exists(results_file):
        with open(results_file, 'r') as f:
            existing_results = json.load(f)
    
    # Filter for Phase 3 sign/both tests
    def get_val(r, path):
        val = r
        for key in path:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                return None
            if val is None:
                return None
        return val
    
    phase3_sign_both = [
        r for r in existing_results 
        if get_val(r, ['scenario', 'phase']) == 3 and 
           get_val(r, ['scenario', 'crypto_mode']) in ['sign', 'both']
    ]
    
    print("=" * 70)
    print("TARGETED SIGNATURE VERIFICATION TEST RE-RUN")
    print("=" * 70)
    print()
    print(f"Found {len(phase3_sign_both):,} sign/both tests to re-run")
    print()
    
    if args.dry_run:
        print("DRY RUN - Would re-run the following test scenarios:")
        print()
        for i, r in enumerate(phase3_sign_both[:10], 1):
            scenario = r.get('scenario', {})
            print(f"  {i}. {scenario.get('modulation')}FSK, {scenario.get('crypto_mode')}, "
                  f"{scenario.get('channel', {}).get('name')}, SNR={scenario.get('snr_db')}dB")
        if len(phase3_sign_both) > 10:
            print(f"  ... and {len(phase3_sign_both) - 10} more")
        print()
        print(f"Total: {len(phase3_sign_both):,} tests")
        print(f"Estimated time: ~{len(phase3_sign_both) * 10.4 / 50 / 60:.1f} hours")
        return
    
    # Extract scenarios to re-run
    scenarios_to_rerun = []
    for r in phase3_sign_both:
        scenario = r.get('scenario', {})
        scenarios_to_rerun.append({
            'modulation': scenario.get('modulation'),
            'crypto_mode': scenario.get('crypto_mode'),
            'channel': scenario.get('channel'),
            'snr_db': scenario.get('snr_db'),
            'data_mode': scenario.get('data_mode', 'voice'),
            'recipients': scenario.get('recipients', ['TEST1']),
            'phase': 3
        })
    
    print(f"Re-running {len(scenarios_to_rerun):,} tests with FIXED signature verification...")
    print()
    
    # Run tests
    # Note: This would need to be integrated with the test suite's run method
    # For now, this is a framework that shows the approach
    
    print("NOTE: This script needs to be integrated with ComprehensiveTestSuite")
    print("to actually re-run the tests. The framework is ready.")
    print()
    print("To implement:")
    print("1. Modify ComprehensiveTestSuite to accept a list of specific scenarios")
    print("2. Filter out existing results for these scenarios before running")
    print("3. Run only the specified scenarios")
    print("4. Merge new results back into existing results file")

if __name__ == '__main__':
    main()

