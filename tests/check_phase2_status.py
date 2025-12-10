#!/usr/bin/env python3
"""
Quick status check for Phase 2 test suite.
"""

import json
import os
import subprocess
from datetime import datetime

def get_phase2_status():
    """Get current Phase 2 test status."""
    status = {
        'running': False,
        'completed': 0,
        'total': 832,
        'passed': 0,
        'failed': 0,
        'pass_rate': 0.0
    }
    
    # Check if test process is running
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    status['running'] = 'test_comprehensive.py --phase 2' in result.stdout
    
    # Check results
    results_file = 'test_results_comprehensive/results_intermediate.json'
    if not os.path.exists(results_file):
        results_file = 'test_results_comprehensive/results.json'
    
    if os.path.exists(results_file):
        with open(results_file) as f:
            results = json.load(f)
        
        phase2_results = [r for r in results if r.get('scenario', {}).get('phase') == 2]
        status['completed'] = len(phase2_results)
        status['passed'] = sum(1 for r in phase2_results if r.get('validation', {}).get('overall_pass', False))
        status['failed'] = status['completed'] - status['passed']
        status['pass_rate'] = status['passed'] / status['completed'] * 100 if status['completed'] > 0 else 0
    
    return status

if __name__ == '__main__':
    status = get_phase2_status()
    
    print("=" * 60)
    print("Phase 2 Test Suite Status")
    print("=" * 60)
    print(f"Status: {'RUNNING' if status['running'] else 'COMPLETED or STOPPED'}")
    print(f"Progress: {status['completed']}/{status['total']} tests ({status['completed']/status['total']*100:.2f}%)")
    print(f"Passed: {status['passed']} ({status['pass_rate']:.1f}%)")
    print(f"Failed: {status['failed']}")
    
    if status['running'] and status['completed'] > 0:
        remaining = status['total'] - status['completed']
        print(f"Remaining: {remaining} tests")
        if status['completed'] >= 10:
            # Rough estimate: ~12 seconds per test
            est_minutes = (remaining * 12) / 60
            print(f"Estimated time remaining: ~{est_minutes:.1f} minutes ({est_minutes/60:.1f} hours)")
    
    print("=" * 60)
    print(f"\nMonitor script is running and will generate report when Phase 2 completes.")
    print(f"Report location: test_results_comprehensive/phase2_progress_report.md")

