#!/usr/bin/env python3
"""
Generate comprehensive test report with plots and statistics from test results.
"""

import json
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from collections import defaultdict

def load_results(results_file: Path) -> List[Dict[str, Any]]:
    """Load test results from JSON file."""
    with open(results_file, 'r') as f:
        return json.load(f)

def calculate_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate summary statistics."""
    stats = {
        'total_tests': len(results),
        'successful_tests': 0,
        'failed_tests': 0,
        'snr_range': {'min': float('inf'), 'max': float('-inf')},
        'fer_stats': {'min': float('inf'), 'max': float('-inf'), 'mean': 0.0, 'median': 0.0},
        'frame_counts': [],
        'modulation_stats': defaultdict(lambda: {'count': 0, 'fer_sum': 0.0, 'fer_count': 0}),
        'channel_stats': defaultdict(lambda: {'count': 0, 'fer_sum': 0.0, 'fer_count': 0}),
        'crypto_stats': defaultdict(lambda: {'count': 0, 'fer_sum': 0.0, 'fer_count': 0})
    }
    
    fers = []
    for result in results:
        if 'error' in result:
            stats['failed_tests'] += 1
            continue
        
        stats['successful_tests'] += 1
        
        test_config = result.get('test_config', {})
        metrics = result.get('metrics', {})
        
        snr_db = test_config.get('snr_db', 0)
        stats['snr_range']['min'] = min(stats['snr_range']['min'], snr_db)
        stats['snr_range']['max'] = max(stats['snr_range']['max'], snr_db)
        
        fer = metrics.get('fer', 1.0)
        if fer < float('inf'):
            fers.append(fer)
            stats['fer_stats']['min'] = min(stats['fer_stats']['min'], fer)
            stats['fer_stats']['max'] = max(stats['fer_stats']['max'], fer)
        
        frame_count = metrics.get('frame_count', 0)
        if frame_count > 0:
            stats['frame_counts'].append(frame_count)
        
        # Per-modulation stats
        mod = test_config.get('modulation', 'unknown')
        stats['modulation_stats'][mod]['count'] += 1
        if fer < float('inf'):
            stats['modulation_stats'][mod]['fer_sum'] += fer
            stats['modulation_stats'][mod]['fer_count'] += 1
        
        # Per-channel stats
        channel = test_config.get('channel_type', 'unknown')
        stats['channel_stats'][channel]['count'] += 1
        if fer < float('inf'):
            stats['channel_stats'][channel]['fer_sum'] += fer
            stats['channel_stats'][channel]['fer_count'] += 1
        
        # Per-crypto stats
        crypto = test_config.get('crypto_mode', 'unknown')
        stats['crypto_stats'][crypto]['count'] += 1
        if fer < float('inf'):
            stats['crypto_stats'][crypto]['fer_sum'] += fer
            stats['crypto_stats'][crypto]['fer_count'] += 1
    
    # Calculate FER statistics
    if fers:
        stats['fer_stats']['mean'] = np.mean(fers)
        stats['fer_stats']['median'] = np.median(fers)
    
    # Calculate average FER per category
    for mod in stats['modulation_stats']:
        if stats['modulation_stats'][mod]['fer_count'] > 0:
            stats['modulation_stats'][mod]['avg_fer'] = (
                stats['modulation_stats'][mod]['fer_sum'] / 
                stats['modulation_stats'][mod]['fer_count']
            )
    
    for channel in stats['channel_stats']:
        if stats['channel_stats'][channel]['fer_count'] > 0:
            stats['channel_stats'][channel]['avg_fer'] = (
                stats['channel_stats'][channel]['fer_sum'] / 
                stats['channel_stats'][channel]['fer_count']
            )
    
    for crypto in stats['crypto_stats']:
        if stats['crypto_stats'][crypto]['fer_count'] > 0:
            stats['crypto_stats'][crypto]['avg_fer'] = (
                stats['crypto_stats'][crypto]['fer_sum'] / 
                stats['crypto_stats'][crypto]['fer_count']
            )
    
    return stats

def plot_fer_vs_snr(results: List[Dict[str, Any]], output_file: Path):
    """Generate FER vs SNR plot."""
    # Group by modulation and channel type
    data = defaultdict(lambda: {'snr': [], 'fer': []})
    
    for result in results:
        if 'error' in result:
            continue
        
        test_config = result.get('test_config', {})
        metrics = result.get('metrics', {})
        
        snr_db = test_config.get('snr_db', 0)
        fer = metrics.get('fer', 1.0)
        mod = test_config.get('modulation', 'unknown')
        channel = test_config.get('channel_type', 'unknown')
        
        key = f"{mod}_{channel}"
        data[key]['snr'].append(snr_db)
        data[key]['fer'].append(fer)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    for key, values in sorted(data.items()):
        if len(values['snr']) == 0:
            continue
        
        # Sort by SNR
        sorted_data = sorted(zip(values['snr'], values['fer']))
        snr_sorted, fer_sorted = zip(*sorted_data)
        
        # Calculate average FER per SNR
        snr_dict = defaultdict(list)
        for snr, fer in zip(snr_sorted, fer_sorted):
            snr_dict[snr].append(fer)
        
        snr_avg = sorted(snr_dict.keys())
        fer_avg = [np.mean(snr_dict[s]) for s in snr_avg]
        fer_std = [np.std(snr_dict[s]) if len(snr_dict[s]) > 1 else 0 for s in snr_avg]
        
        ax.plot(snr_avg, fer_avg, marker='o', label=key, linewidth=2)
        if any(fer_std):
            ax.fill_between(snr_avg, 
                          [f - s for f, s in zip(fer_avg, fer_std)],
                          [f + s for f, s in zip(fer_avg, fer_std)],
                          alpha=0.2)
    
    ax.set_xlabel('SNR (dB)', fontsize=12)
    ax.set_ylabel('Frame Error Rate (FER)', fontsize=12)
    ax.set_title('Frame Error Rate vs SNR', fontsize=14, fontweight='bold')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)
    
    # Add threshold lines
    ax.axhline(y=0.01, color='g', linestyle='--', alpha=0.5, label='1% FER (Good)')
    ax.axhline(y=0.10, color='y', linestyle='--', alpha=0.5, label='10% FER (Acceptable)')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved FER vs SNR plot to {output_file}")

def generate_summary_table(stats: Dict[str, Any], output_file: Path):
    """Generate summary statistics table."""
    lines = []
    lines.append("=" * 80)
    lines.append("GR-SLEIPNIR TEST SUITE SUMMARY REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Total Tests: {stats['total_tests']}")
    lines.append(f"Successful Tests: {stats['successful_tests']}")
    lines.append(f"Failed Tests: {stats['failed_tests']}")
    lines.append("")
    lines.append(f"SNR Range: {stats['snr_range']['min']:.1f} to {stats['snr_range']['max']:.1f} dB")
    lines.append("")
    lines.append("FER Statistics:")
    lines.append(f"  Min: {stats['fer_stats']['min']:.4f}")
    lines.append(f"  Max: {stats['fer_stats']['max']:.4f}")
    lines.append(f"  Mean: {stats['fer_stats']['mean']:.4f}")
    lines.append(f"  Median: {stats['fer_stats']['median']:.4f}")
    lines.append("")
    
    if stats['frame_counts']:
        lines.append(f"Frame Count Statistics:")
        lines.append(f"  Min: {min(stats['frame_counts'])}")
        lines.append(f"  Max: {max(stats['frame_counts'])}")
        lines.append(f"  Mean: {np.mean(stats['frame_counts']):.1f}")
        lines.append(f"  Median: {np.median(stats['frame_counts']):.1f}")
        lines.append("")
    
    lines.append("Performance by Modulation:")
    for mod, mod_stats in sorted(stats['modulation_stats'].items()):
        lines.append(f"  {mod}:")
        lines.append(f"    Tests: {mod_stats['count']}")
        if 'avg_fer' in mod_stats:
            lines.append(f"    Avg FER: {mod_stats['avg_fer']:.4f}")
    lines.append("")
    
    lines.append("Performance by Channel Type:")
    for channel, channel_stats in sorted(stats['channel_stats'].items()):
        lines.append(f"  {channel}:")
        lines.append(f"    Tests: {channel_stats['count']}")
        if 'avg_fer' in channel_stats:
            lines.append(f"    Avg FER: {channel_stats['avg_fer']:.4f}")
    lines.append("")
    
    lines.append("Performance by Crypto Mode:")
    for crypto, crypto_stats in sorted(stats['crypto_stats'].items()):
        lines.append(f"  {crypto}:")
        lines.append(f"    Tests: {crypto_stats['count']}")
        if 'avg_fer' in crypto_stats:
            lines.append(f"    Avg FER: {crypto_stats['avg_fer']:.4f}")
    lines.append("")
    lines.append("=" * 80)
    
    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"Saved summary table to {output_file}")

def generate_pass_fail_report(results: List[Dict[str, Any]], validation_config: Dict[str, Any], output_file: Path):
    """Generate pass/fail report based on validation criteria."""
    fer_threshold_good = validation_config.get('fer_threshold_good', 0.01)
    fer_threshold_acceptable = validation_config.get('fer_threshold_acceptable', 0.10)
    
    lines = []
    lines.append("=" * 80)
    lines.append("PASS/FAIL VALIDATION REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Criteria:")
    lines.append(f"  Good: FER < {fer_threshold_good:.1%}")
    lines.append(f"  Acceptable: FER < {fer_threshold_acceptable:.1%}")
    lines.append(f"  Failed: FER >= {fer_threshold_acceptable:.1%}")
    lines.append("")
    
    # Group by SNR
    snr_results = defaultdict(list)
    for result in results:
        if 'error' in result:
            continue
        test_config = result.get('test_config', {})
        metrics = result.get('metrics', {})
        snr_db = test_config.get('snr_db', 0)
        fer = metrics.get('fer', 1.0)
        snr_results[snr_db].append({
            'fer': fer,
            'config': test_config,
            'metrics': metrics
        })
    
    lines.append("Results by SNR:")
    for snr_db in sorted(snr_results.keys()):
        results_at_snr = snr_results[snr_db]
        good_count = sum(1 for r in results_at_snr if r['fer'] < fer_threshold_good)
        acceptable_count = sum(1 for r in results_at_snr if fer_threshold_good <= r['fer'] < fer_threshold_acceptable)
        failed_count = sum(1 for r in results_at_snr if r['fer'] >= fer_threshold_acceptable)
        
        lines.append(f"  SNR {snr_db:+.1f} dB:")
        lines.append(f"    Good: {good_count}/{len(results_at_snr)} ({100*good_count/len(results_at_snr):.1f}%)")
        lines.append(f"    Acceptable: {acceptable_count}/{len(results_at_snr)} ({100*acceptable_count/len(results_at_snr):.1f}%)")
        lines.append(f"    Failed: {failed_count}/{len(results_at_snr)} ({100*failed_count/len(results_at_snr):.1f}%)")
    
    lines.append("")
    lines.append("=" * 80)
    
    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"Saved pass/fail report to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Generate test report from results')
    parser.add_argument('--results', type=str, required=True,
                       help='Path to all_results.json file')
    parser.add_argument('--output', type=str, default='test_report',
                       help='Output directory for reports (default: test_report)')
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='Config file for validation thresholds (default: config.yaml)')
    
    args = parser.parse_args()
    
    results_file = Path(args.results)
    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}")
        return 1
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load results
    print(f"Loading results from {results_file}...")
    results = load_results(results_file)
    print(f"Loaded {len(results)} test results")
    
    # Load config for validation thresholds
    validation_config = {}
    config_file = Path(args.config)
    if config_file.exists():
        import yaml
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            validation_config = config.get('validation', {})
    
    # Calculate statistics
    print("Calculating statistics...")
    stats = calculate_statistics(results)
    
    # Generate plots
    print("Generating plots...")
    plot_fer_vs_snr(results, output_dir / 'fer_vs_snr.png')
    
    # Generate reports
    print("Generating reports...")
    generate_summary_table(stats, output_dir / 'summary_report.txt')
    generate_pass_fail_report(results, validation_config, output_dir / 'pass_fail_report.txt')
    
    print(f"\nReport generation complete! Output saved to {output_dir}")
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())

