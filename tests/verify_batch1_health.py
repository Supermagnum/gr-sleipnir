#!/usr/bin/env python3
"""
Batch 1 Health Check Script

Verifies Batch 1 results match expected healthy patterns.
"""

import json
import os
from collections import defaultdict

def verify_batch1_health(results_file='test_results_comprehensive/results_intermediate.json'):
    """Verify Batch 1 results match expected healthy patterns."""
    
    if not os.path.exists(results_file):
        print('Results file not found - Batch 1 may still be running')
        return False
    
    with open(results_file) as f:
        results = json.load(f)
    
    phase2 = [r for r in results if r.get('scenario', {}).get('phase') == 2]
    batch1 = phase2[:50] if len(phase2) >= 50 else phase2
    
    if len(batch1) < 50:
        print(f'Batch 1 incomplete: {len(batch1)}/50 tests')
        return False
    
    print('=' * 70)
    print('BATCH 1 HEALTH CHECK')
    print('=' * 70)
    print()
    
    # Overall stats
    passed = sum(1 for r in batch1 if r.get('validation', {}).get('overall_pass', False))
    decoded = sum(1 for r in batch1 if r.get('metrics', {}).get('frame_count', 0) > 0)
    total = len(batch1)
    pass_rate = passed / total * 100
    
    print(f'Overall Results:')
    print(f'  Passed: {passed}/{total} ({pass_rate:.1f}%)')
    print(f'  Decoded: {decoded}/{total} ({decoded/total*100:.1f}%)')
    print()
    
    # FER analysis
    fers = [r.get('metrics', {}).get('fer') for r in batch1 if r.get('metrics', {}).get('fer') is not None]
    if fers:
        fer_min = min(fers)
        fer_max = max(fers)
        fer_non_zero = sum(1 for f in fers if f > 0.0)
        print(f'FER Analysis:')
        print(f'  Range: {fer_min:.4f} to {fer_max:.4f}')
        print(f'  Non-zero FERs: {fer_non_zero}/{len(fers)}')
        print()
    else:
        print('FER Analysis: No FER values found')
        print()
    
    # By channel
    by_channel = defaultdict(lambda: {'total': 0, 'passed': 0})
    for r in batch1:
        channel = r.get('scenario', {}).get('channel', {}).get('name', 'unknown')
        by_channel[channel]['total'] += 1
        if r.get('validation', {}).get('overall_pass', False):
            by_channel[channel]['passed'] += 1
    
    print('By Channel:')
    print('-' * 70)
    for channel in ['clean', 'awgn']:
        if channel in by_channel:
            stats = by_channel[channel]
            ch_pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f'{channel.upper()}: {stats["passed"]}/{stats["total"]} passed ({ch_pass_rate:.1f}%)')
    print()
    
    # By SNR
    by_snr = defaultdict(lambda: {'total': 0, 'passed': 0})
    for r in batch1:
        snr = r.get('scenario', {}).get('snr_db', 0)
        if snr < 0:
            snr_range = '< 0'
        elif snr < 10:
            snr_range = '0-10'
        else:
            snr_range = '>= 10'
        by_snr[snr_range]['total'] += 1
        if r.get('validation', {}).get('overall_pass', False):
            by_snr[snr_range]['passed'] += 1
    
    print('By SNR:')
    print('-' * 70)
    for snr_range in ['< 0', '0-10', '>= 10']:
        if snr_range in by_snr:
            stats = by_snr[snr_range]
            snr_pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f'SNR {snr_range} dB: {stats["passed"]}/{stats["total"]} passed ({snr_pass_rate:.1f}%)')
    print()
    
    # Health check
    print('=' * 70)
    print('HEALTH CHECK')
    print('=' * 70)
    print()
    
    issues = []
    warnings = []
    
    # Check 1: Pass rate
    if pass_rate == 100:
        issues.append('CRITICAL: 100% pass rate - thresholds too lenient or no noise')
    elif pass_rate == 0:
        issues.append('CRITICAL: 0% pass rate - too much noise or validation broken')
    elif 70 <= pass_rate <= 85:
        print('OK: Pass rate healthy (70-85%)')
    else:
        warnings.append(f'WARNING: Pass rate ({pass_rate:.1f}%) outside expected range (70-85%)')
    
    # Check 2: FER tracking
    if fers:
        if all(f == 0.0 for f in fers):
            issues.append('CRITICAL: All FER values are 0.0 - error tracking broken')
        elif fer_non_zero >= 15:
            print(f'OK: FER tracking working ({fer_non_zero}/{len(fers)} tests with non-zero FER)')
        else:
            warnings.append(f'WARNING: Only {fer_non_zero}/{len(fers)} tests have non-zero FER')
    else:
        issues.append('CRITICAL: No FER values found')
    
    # Check 3: Channel performance
    clean_rate = by_channel.get('clean', {}).get('passed', 0) / by_channel.get('clean', {}).get('total', 1) * 100 if by_channel.get('clean', {}).get('total', 0) > 0 else 0
    awgn_rate = by_channel.get('awgn', {}).get('passed', 0) / by_channel.get('awgn', {}).get('total', 1) * 100 if by_channel.get('awgn', {}).get('total', 0) > 0 else 0
    
    if clean_rate > 0 and awgn_rate > 0:
        if clean_rate >= awgn_rate + 20:  # Clean should be significantly better
            print(f'OK: Channel performance correct (Clean {clean_rate:.1f}% > AWGN {awgn_rate:.1f}%)')
        elif abs(clean_rate - awgn_rate) < 5:
            issues.append(f'CRITICAL: Clean ({clean_rate:.1f}%) = AWGN ({awgn_rate:.1f}%) - channels mislabeled')
        else:
            warnings.append(f'WARNING: Clean ({clean_rate:.1f}%) not significantly better than AWGN ({awgn_rate:.1f}%)')
    
    # Check 4: SNR progression
    low_snr_rate = by_snr.get('< 0', {}).get('passed', 0) / by_snr.get('< 0', {}).get('total', 1) * 100 if by_snr.get('< 0', {}).get('total', 0) > 0 else 0
    mid_snr_rate = by_snr.get('0-10', {}).get('passed', 0) / by_snr.get('0-10', {}).get('total', 1) * 100 if by_snr.get('0-10', {}).get('total', 0) > 0 else 0
    high_snr_rate = by_snr.get('>= 10', {}).get('passed', 0) / by_snr.get('>= 10', {}).get('total', 1) * 100 if by_snr.get('>= 10', {}).get('total', 0) > 0 else 0
    
    if low_snr_rate < mid_snr_rate < high_snr_rate:
        print('OK: SNR progression correct (low < mid < high)')
    elif low_snr_rate >= high_snr_rate:
        issues.append('CRITICAL: SNR progression reversed (low SNR performing better than high)')
    else:
        warnings.append('WARNING: SNR progression not as expected')
    
    # Check 5: Decode rate
    decode_rate = decoded / total * 100
    if decode_rate == 0:
        issues.append('CRITICAL: Nothing decoded - flowgraph broken')
    elif decode_rate >= 70:
        print(f'OK: Decode rate healthy ({decode_rate:.1f}%)')
    else:
        warnings.append(f'WARNING: Decode rate low ({decode_rate:.1f}%)')
    
    print()
    if issues:
        print('CRITICAL ISSUES:')
        for issue in issues:
            print(f'  [X] {issue}')
        print()
    
    if warnings:
        print('WARNINGS:')
        for warning in warnings:
            print(f'  [!] {warning}')
        print()
    
    if not issues and not warnings:
        print('SUCCESS: ALL CHECKS PASSED - Tests are working correctly!')
    elif not issues:
        print('WARNING: Some warnings, but no critical issues')
    else:
        print('FAILURE: CRITICAL ISSUES FOUND - Tests need fixing')
    
    print()
    print('=' * 70)
    
    return len(issues) == 0

if __name__ == '__main__':
    verify_batch1_health()
