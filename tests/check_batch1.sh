#!/bin/bash
# Quick check script for Batch 1 results
# Usage: ./check_batch1.sh

python3 -c "
import json
import os

# Check for batch results file
results_file = 'test_results_comprehensive/results_intermediate.json'
if not os.path.exists(results_file):
    print('Results file not found. Batch 1 may not have completed yet.')
    exit(1)

with open(results_file) as f:
    results = json.load(f)

# Filter for Phase 2 results (first 50 tests)
phase2 = [r for r in results if r.get('scenario', {}).get('phase') == 2]
batch1 = phase2[:50] if len(phase2) >= 50 else phase2

if len(batch1) == 0:
    print('No Batch 1 results yet.')
    exit(1)

passed = sum(1 for t in batch1 if t.get('validation', {}).get('overall_pass', False))
decoded = sum(1 for t in batch1 if t.get('metrics', {}).get('frame_count', 0) > 0)
total = len(batch1)

print(f'Batch 1 Results: {total} tests')
print(f'Passed: {passed}/{total} ({passed/total*100:.0f}%)')
print(f'Decoded: {decoded}/{total} ({decoded/total*100:.0f}%)')
print()

if decoded == 0:
    print('ERROR: Nothing decoded - still broken!')
elif passed == 0:
    print('WARNING: Decoding works but all failing validation')
elif passed == total:
    print('WARNING: All passing - thresholds too lenient')
else:
    print('SUCCESS: Tests working correctly!')
"

