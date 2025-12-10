#!/usr/bin/env python3
"""
Monitor Phase 2 test suite progress and generate report when complete.
"""

import json
import os
import time
import subprocess
from datetime import datetime
from pathlib import Path

def check_phase2_complete():
    """Check if Phase 2 test suite has completed."""
    # Check if test process is still running
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    test_running = 'test_comprehensive.py --phase 2' in result.stdout
    
    # Check both intermediate and final results files
    results_files = [
        'test_results_comprehensive/results.json',
        'test_results_comprehensive/results_intermediate.json'
    ]
    
    phase2_results = []
    for results_file in results_files:
        if os.path.exists(results_file):
            try:
                with open(results_file) as f:
                    results = json.load(f)
                
                phase2_results = [r for r in results if r.get('scenario', {}).get('phase') == 2]
                
                # Phase 2 complete if we have 832 results or test process stopped with results
                if len(phase2_results) >= 832:
                    return True, phase2_results
                elif not test_running and len(phase2_results) > 0:
                    # Test stopped but has results - might be complete or crashed
                    # Check if we're close to 832 (within 10 tests)
                    if len(phase2_results) >= 822:
                        return True, phase2_results
                    break
            except Exception as e:
                print(f"Error reading {results_file}: {e}")
                continue
    
    return False, phase2_results

def generate_phase2_report(phase2_results):
    """Generate comprehensive Phase 2 progress report."""
    
    total_tests = len(phase2_results)
    passed = sum(1 for r in phase2_results if r.get('validation', {}).get('overall_pass', False))
    failed = total_tests - passed
    pass_rate = passed / total_tests * 100 if total_tests > 0 else 0
    
    # Calculate timing
    timestamps = [r.get('timestamp') for r in phase2_results if r.get('timestamp')]
    if len(timestamps) >= 2:
        start = datetime.fromisoformat(timestamps[0])
        end = datetime.fromisoformat(timestamps[-1])
        duration = (end - start).total_seconds()
    else:
        duration = None
    
    # Breakdown by configuration
    by_mod = {}
    by_crypto = {}
    by_channel = {}
    by_snr = {}
    
    for r in phase2_results:
        s = r.get('scenario', {})
        mod = s.get('modulation')
        crypto = s.get('crypto_mode')
        channel = s.get('channel', {}).get('name', 'unknown')
        snr = s.get('snr_db')
        
        if mod not in by_mod:
            by_mod[mod] = {'total': 0, 'passed': 0}
        if crypto not in by_crypto:
            by_crypto[crypto] = {'total': 0, 'passed': 0}
        if channel not in by_channel:
            by_channel[channel] = {'total': 0, 'passed': 0}
        if snr not in by_snr:
            by_snr[snr] = {'total': 0, 'passed': 0, 'frames': [], 'fers': []}
        
        passed_test = r.get('validation', {}).get('overall_pass', False)
        metrics = r.get('metrics', {})
        
        by_mod[mod]['total'] += 1
        by_crypto[crypto]['total'] += 1
        by_channel[channel]['total'] += 1
        by_snr[snr]['total'] += 1
        
        if passed_test:
            by_mod[mod]['passed'] += 1
            by_crypto[crypto]['passed'] += 1
            by_channel[channel]['passed'] += 1
            by_snr[snr]['passed'] += 1
        
        by_snr[snr]['frames'].append(metrics.get('frame_count', 0))
        fer = metrics.get('fer')
        if fer is not None:
            by_snr[snr]['fers'].append(fer)
    
    # Generate report
    report_lines = []
    report_lines.append("# Phase 2 Comprehensive Test Suite - Progress Report\n")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    report_lines.append("## Executive Summary\n\n")
    report_lines.append(f"- **Total Tests**: {total_tests}/832\n")
    report_lines.append(f"- **Passed**: {passed} ({pass_rate:.1f}%)\n")
    report_lines.append(f"- **Failed**: {failed}\n")
    if duration:
        report_lines.append(f"- **Duration**: {duration/60:.1f} minutes ({duration/3600:.2f} hours)\n")
        report_lines.append(f"- **Average Test Time**: {duration/total_tests:.1f} seconds\n")
    report_lines.append("\n")
    
    # Performance metrics
    report_lines.append("## Performance Metrics\n\n")
    all_frames = [r.get('metrics', {}).get('frame_count', 0) for r in phase2_results]
    all_fers = [r.get('metrics', {}).get('fer', 1.0) for r in phase2_results if r.get('metrics', {}).get('fer') is not None]
    
    if all_frames:
        report_lines.append(f"- **Total Frames Decoded**: {sum(all_frames):,}\n")
        report_lines.append(f"- **Average Frames per Test**: {sum(all_frames)/len(all_frames):.1f}\n")
        report_lines.append(f"- **Min Frames**: {min(all_frames)}\n")
        report_lines.append(f"- **Max Frames**: {max(all_frames)}\n")
    
    if all_fers:
        report_lines.append(f"- **Average FER**: {sum(all_fers)/len(all_fers):.4f}\n")
        report_lines.append(f"- **Best FER**: {min(all_fers):.4f}\n")
        report_lines.append(f"- **Worst FER**: {max(all_fers):.4f}\n")
    
    report_lines.append("\n")
    
    # Breakdown by modulation
    report_lines.append("## Results by Modulation Mode\n\n")
    report_lines.append("| Modulation | Tests | Passed | Failed | Pass Rate |\n")
    report_lines.append("|------------|-------|--------|--------|-----------|\n")
    for mod in sorted(by_mod.keys()):
        stats = by_mod[mod]
        mod_pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        report_lines.append(f"| {mod}FSK | {stats['total']} | {stats['passed']} | {stats['total'] - stats['passed']} | {mod_pass_rate:.1f}% |\n")
    report_lines.append("\n")
    
    # Breakdown by crypto mode
    report_lines.append("## Results by Crypto Mode\n\n")
    report_lines.append("| Crypto Mode | Tests | Passed | Failed | Pass Rate |\n")
    report_lines.append("|-------------|-------|--------|--------|-----------|\n")
    for crypto in sorted(by_crypto.keys()):
        stats = by_crypto[crypto]
        crypto_pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        report_lines.append(f"| {crypto} | {stats['total']} | {stats['passed']} | {stats['total'] - stats['passed']} | {crypto_pass_rate:.1f}% |\n")
    report_lines.append("\n")
    
    # Breakdown by channel
    report_lines.append("## Results by Channel Condition\n\n")
    report_lines.append("| Channel | Tests | Passed | Failed | Pass Rate |\n")
    report_lines.append("|---------|-------|--------|--------|-----------|\n")
    for channel in sorted(by_channel.keys()):
        stats = by_channel[channel]
        channel_pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        report_lines.append(f"| {channel} | {stats['total']} | {stats['passed']} | {stats['total'] - stats['passed']} | {channel_pass_rate:.1f}% |\n")
    report_lines.append("\n")
    
    # Results by SNR
    report_lines.append("## Results by SNR\n\n")
    report_lines.append("| SNR (dB) | Tests | Passed | Avg Frames | Avg FER |\n")
    report_lines.append("|----------|-------|--------|------------|----------|\n")
    for snr in sorted(by_snr.keys()):
        stats = by_snr[snr]
        avg_frames = sum(stats['frames']) / len(stats['frames']) if stats['frames'] else 0
        avg_fer = sum(stats['fers']) / len(stats['fers']) if stats['fers'] else None
        fer_str = f"{avg_fer:.4f}" if avg_fer is not None else "N/A"
        report_lines.append(f"| {snr:.1f} | {stats['total']} | {stats['passed']} | {avg_frames:.0f} | {fer_str} |\n")
    report_lines.append("\n")
    
    # Issues identified
    report_lines.append("## Issues Identified\n\n")
    issues = set()
    for r in phase2_results:
        validation = r.get('validation', {})
        for check, result in validation.items():
            if isinstance(result, dict) and result.get('issues'):
                issues.update(result['issues'])
    
    if issues:
        for issue in sorted(issues):
            report_lines.append(f"- {issue}\n")
    else:
        report_lines.append("No issues identified.\n")
    report_lines.append("\n")
    
    # Recommendations
    report_lines.append("## Recommendations\n\n")
    if pass_rate < 100:
        report_lines.append("- Investigate failed test scenarios\n")
        report_lines.append("- Review error logs for patterns\n")
    
    if all_fers and max(all_fers) > 0.01:
        report_lines.append("- Some tests show elevated FER - review channel conditions\n")
    
    report_lines.append("- Consider running Phase 3 (edge cases) after reviewing Phase 2 results\n")
    report_lines.append("\n")
    
    # Write report
    report_file = 'test_results_comprehensive/phase2_progress_report.md'
    with open(report_file, 'w') as f:
        f.writelines(report_lines)
    
    print(f"Phase 2 progress report generated: {report_file}")
    return report_file

def main():
    """Monitor Phase 2 and generate report when complete."""
    print("Monitoring Phase 2 test suite...")
    print("Checking every 60 seconds for completion...")
    
    check_count = 0
    while True:
        check_count += 1
        complete, phase2_results = check_phase2_complete()
        
        if complete:
            print(f"\nPhase 2 test suite completed!")
            print(f"Generating progress report...")
            report_file = generate_phase2_report(phase2_results)
            print(f"\nReport generated: {report_file}")
            break
        else:
            if phase2_results:
                print(f"Check {check_count}: {len(phase2_results)}/832 tests completed ({len(phase2_results)/832*100:.1f}%)")
            else:
                print(f"Check {check_count}: Waiting for Phase 2 results...")
        
        time.sleep(60)  # Check every minute

if __name__ == '__main__':
    main()

