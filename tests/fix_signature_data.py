#!/usr/bin/env python3
"""
Fix signature verification data by re-running affected tests.

This script will:
1. Identify all Phase 3 sign/both tests
2. Remove them from results (with backup)
3. Re-run ONLY those tests with fixed signature verification
4. Merge results back

Usage:
    # Quick verification (20 tests, ~5-10 minutes)
    python3 tests/fix_signature_data.py --verify-sample 20
    
    # Full re-run (3,864 tests, ~13 hours)
    python3 tests/fix_signature_data.py --full
"""

import sys
import os
import json
import argparse
import shutil
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import yaml
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
    # Normalize recipients to tuple
    recipients = scenario.get('recipients', ['TEST1'])
    if isinstance(recipients, list):
        recipients = tuple(sorted(recipients))
    
    key = (
        scenario.get('modulation'),
        scenario.get('crypto_mode'),
        scenario.get('channel', {}).get('name') if isinstance(scenario.get('channel'), dict) else scenario.get('channel'),
        scenario.get('snr_db'),
        scenario.get('data_mode', 'voice'),
        recipients
    )
    return hashlib.md5(str(key).encode()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description='Fix signature verification data')
    parser.add_argument('--config', default='tests/config_comprehensive.yaml',
                       help='Test configuration file')
    parser.add_argument('--verify-sample', type=int, default=0,
                       help='Run only N tests for verification (quick check)')
    parser.add_argument('--full', action='store_true',
                       help='Re-run all 3,864 sign/both tests')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without running')
    args = parser.parse_args()
    
    if not args.verify_sample and not args.full:
        print("Error: Must specify --verify-sample N or --full")
        print()
        print("Quick verification (recommended first):")
        print("  python3 tests/fix_signature_data.py --verify-sample 20")
        print()
        print("Full re-run (if verification shows issues):")
        print("  python3 tests/fix_signature_data.py --full")
        return 1
    
    # Load test suite
    suite = ComprehensiveTestSuite(args.config)
    
    # Load existing results
    results_file = suite.test_params.get('output', {}).get('results_json', 
                   'test-results-json/results.json')
    
    if not os.path.exists(results_file):
        print(f"Error: Results file not found: {results_file}")
        return 1
    
    print("=" * 70)
    print("SIGNATURE VERIFICATION DATA FIX")
    print("=" * 70)
    print()
    
    with open(results_file, 'r') as f:
        all_results = json.load(f)
    
    # Separate sign/both tests from others
    sign_both_results = []
    other_results = []
    
    for r in all_results:
        scenario = r.get('scenario', {})
        if (get_val(r, ['scenario', 'phase']) == 3 and 
            get_val(r, ['scenario', 'crypto_mode']) in ['sign', 'both']):
            sign_both_results.append(r)
        else:
            other_results.append(r)
    
    print(f"Total results: {len(all_results):,}")
    print(f"Sign/both tests found: {len(sign_both_results):,}")
    print(f"Other tests (keep): {len(other_results):,}")
    print()
    
    # Select tests to re-run
    if args.verify_sample > 0:
        import random
        random.seed(42)  # Reproducible
        tests_to_rerun = random.sample(sign_both_results, min(args.verify_sample, len(sign_both_results)))
        print(f"VERIFICATION MODE: {len(tests_to_rerun):,} test sample")
        print(f"Estimated time: ~{len(tests_to_rerun) * 10.4 / 50 / 60:.1f} hours (~{len(tests_to_rerun) * 10.4 / 50:.0f} minutes)")
    else:
        tests_to_rerun = sign_both_results
        print(f"FULL RE-RUN MODE: {len(tests_to_rerun):,} tests")
        print(f"Estimated time: ~{len(tests_to_rerun) * 10.4 / 50 / 60:.1f} hours")
    
    print()
    
    if args.dry_run:
        print("DRY RUN - Would:")
        print(f"  1. Backup {results_file} to {results_file}.backup")
        print(f"  2. Remove {len(tests_to_rerun):,} sign/both test results")
        print(f"  3. Re-run {len(tests_to_rerun):,} tests with FIXED signature verification")
        print(f"  4. Merge new results back")
        return 0
    
    # Create backup
    backup_file = results_file + f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    print(f"1. Creating backup: {backup_file}")
    shutil.copy2(results_file, backup_file)
    
    # Create hash set of tests to remove
    tests_to_remove_hashes = {create_scenario_hash(r.get('scenario', {})) for r in tests_to_rerun}
    
    # Remove selected tests from results
    print(f"2. Removing {len(tests_to_rerun):,} test results from {results_file}")
    filtered_results = []
    removed_count = 0
    
    for r in all_results:
        scenario = r.get('scenario', {})
        scenario_hash = create_scenario_hash(scenario)
        if scenario_hash in tests_to_remove_hashes:
            removed_count += 1
        else:
            filtered_results.append(r)
    
    print(f"   Removed {removed_count:,} test results")
    print(f"   Remaining: {len(filtered_results):,} test results")
    
    # Save filtered results
    with open(results_file, 'w') as f:
        json.dump(filtered_results, f, indent=2)
    
    print()
    print("3. Next steps:")
    print()
    print("   The test suite will now skip these tests (they're removed from results)")
    print("   and re-run them with the FIXED signature verification code.")
    print()
    print("   Run:")
    if args.verify_sample > 0:
        print(f"   python3 tests/test_comprehensive.py --config {args.config} --phase 3 --resume")
        print()
        print("   This will:")
        print(f"   - Re-run the {len(tests_to_rerun):,} selected tests")
        print("   - Use FIXED signature verification (no placeholder)")
        print("   - Merge results automatically")
        print()
        print("   After verification, if signatures are invalid:")
        print("   python3 tests/fix_signature_data.py --full")
    else:
        print(f"   python3 tests/test_comprehensive.py --config {args.config} --phase 3 --resume")
        print()
        print("   This will:")
        print(f"   - Re-run all {len(tests_to_rerun):,} sign/both tests")
        print("   - Use FIXED signature verification (no placeholder)")
        print("   - Merge results automatically")
        print(f"   - Take ~{len(tests_to_rerun) * 10.4 / 50 / 60:.1f} hours")
    
    print()
    print("=" * 70)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

