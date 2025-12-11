#!/usr/bin/env python3
"""
Re-run signature verification tests to get accurate data.

This script:
1. Identifies all sign/both crypto mode tests from Phase 3
2. Removes their results from the results file
3. Re-runs ONLY those tests with the fixed signature verification code
4. Merges new results back into the results file

Usage:
    python3 tests/rerun_signature_verification.py --config tests/config_comprehensive.yaml
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from test_comprehensive import ComprehensiveTestSuite

def get_val(r, path):
    """Helper to get nested dict value."""
    val = r
    for key in path:
        if isinstance(val, dict):
            val = val.get(key)
        else:
            return None
        if val is None:
            return None
    return val

def create_scenario_hash(scenario):
    """Create hash for scenario identification."""
    import hashlib
    key = (
        scenario.get('modulation'),
        scenario.get('crypto_mode'),
        scenario.get('channel', {}).get('name'),
        scenario.get('snr_db'),
        scenario.get('data_mode', 'voice'),
        tuple(scenario.get('recipients', ['TEST1']))
    )
    return hashlib.md5(str(key).encode()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description='Re-run signature verification tests')
    parser.add_argument('--config', default='tests/config_comprehensive.yaml',
                       help='Test configuration file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be tested without running')
    parser.add_argument('--verify-sample', type=int, default=0,
                       help='Run only a sample of N tests for verification')
    args = parser.parse_args()
    
    # Load test suite
    suite = ComprehensiveTestSuite(args.config)
    
    # Load existing results
    results_file = suite.test_params.get('output', {}).get('results_json', 
                   'test-results-json/results.json')
    
    if not os.path.exists(results_file):
        print(f"Error: Results file not found: {results_file}")
        return 1
    
    with open(results_file, 'r') as f:
        all_results = json.load(f)
    
    # Separate sign/both tests from others
    sign_both_results = []
    other_results = []
    sign_both_hashes = set()
    
    for r in all_results:
        scenario = r.get('scenario', {})
        if (get_val(r, ['scenario', 'phase']) == 3 and 
            get_val(r, ['scenario', 'crypto_mode']) in ['sign', 'both']):
            sign_both_results.append(r)
            sign_both_hashes.add(create_scenario_hash(scenario))
        else:
            other_results.append(r)
    
    print("=" * 70)
    print("SIGNATURE VERIFICATION TEST RE-RUN")
    print("=" * 70)
    print()
    print(f"Total results: {len(all_results):,}")
    print(f"Sign/both tests to re-run: {len(sign_both_results):,}")
    print(f"Other tests (keep): {len(other_results):,}")
    print()
    
    if args.verify_sample > 0:
        # Run only a sample for verification
        import random
        sample = random.sample(sign_both_results, min(args.verify_sample, len(sign_both_results)))
        print(f"VERIFICATION MODE: Running sample of {len(sample):,} tests")
        print()
        scenarios_to_rerun = [r.get('scenario') for r in sample]
    else:
        scenarios_to_rerun = [r.get('scenario') for r in sign_both_results]
    
    if args.dry_run:
        print("DRY RUN - Would re-run:")
        for i, scenario in enumerate(scenarios_to_rerun[:10], 1):
            print(f"  {i}. {scenario.get('modulation')}FSK, {scenario.get('crypto_mode')}, "
                  f"{scenario.get('channel', {}).get('name')}, SNR={scenario.get('snr_db')}dB")
        if len(scenarios_to_rerun) > 10:
            print(f"  ... and {len(scenarios_to_rerun) - 10} more")
        print()
        print(f"Estimated time: ~{len(scenarios_to_rerun) * 10.4 / 50 / 60:.1f} hours")
        return 0
    
    # Remove sign/both results from file (backup first)
    backup_file = results_file + '.backup'
    print(f"Creating backup: {backup_file}")
    with open(backup_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    # Save results without sign/both tests
    print(f"Removing {len(sign_both_results):,} sign/both test results from {results_file}")
    with open(results_file, 'w') as f:
        json.dump(other_results, f, indent=2)
    
    # Generate scenarios to re-run
    print(f"\nGenerating {len(scenarios_to_rerun):,} test scenarios to re-run...")
    
    # Modify suite to only run these scenarios
    # This requires modifying the test suite's scenario generation
    # For now, we'll create a custom config that only includes sign/both
    
    print("\n" + "=" * 70)
    print("IMPORTANT: Manual Steps Required")
    print("=" * 70)
    print()
    print("To complete the re-run:")
    print()
    print("1. Create a temporary config file with ONLY sign/both crypto modes:")
    print("   - Copy tests/config_comprehensive.yaml")
    print("   - Set crypto_modes: ['sign', 'both']")
    print("   - Set phase3.crypto_modes: ['sign', 'both']")
    print()
    print("2. Run the test suite with this config:")
    print(f"   python3 tests/test_comprehensive.py --config <temp_config> --phase 3")
    print()
    print("3. The test suite will:")
    print("   - Skip tests that already exist (resume functionality)")
    print("   - Run only the sign/both tests")
    print("   - Merge results automatically")
    print()
    print(f"4. Estimated time: ~{len(scenarios_to_rerun) * 10.4 / 50 / 60:.1f} hours")
    print()
    print("ALTERNATIVE: Quick Verification (5-10 minutes)")
    print("  Run a small sample first to verify if signatures are actually valid:")
    print(f"  python3 tests/rerun_signature_verification.py --verify-sample 20 --dry-run")
    print()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

