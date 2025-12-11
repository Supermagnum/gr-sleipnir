#!/usr/bin/env python3
"""
Results Analyzer for gr-sleipnir Test Suite

Analyzes test results and generates reports and visualizations.
"""

import json
import argparse
import logging
import numpy as np
import os
import sys
from datetime import datetime
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available, plots will be skipped")
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class ResultsAnalyzer:
    """Analyze test results and generate reports."""
    
    def __init__(self, results_file: str):
        """
        Initialize results analyzer.
        
        Args:
            results_file: Path to results JSON file
        """
        with open(results_file, 'r') as f:
            self.results = json.load(f)
        
        logger.info(f"Loaded {len(self.results)} test results")
    
    def generate_performance_curves(self, output_dir: str):
        """
        Generate performance curves (FER vs SNR, WarpQ vs SNR, etc.).
        
        Args:
            output_dir: Output directory for plots
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available, skipping plot generation")
            return
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Group results by modulation and crypto mode
        grouped = defaultdict(list)
        for result in self.results:
            if 'scenario' not in result:
                continue
            scenario = result['scenario']
            key = (scenario['modulation'], scenario['crypto_mode'])
            grouped[key].append(result)
        
        # Generate FER vs SNR curves
        self._plot_fer_vs_snr(grouped, output_dir)
        
        # Generate WarpQ vs SNR curves
        self._plot_warpq_vs_snr(grouped, output_dir)
        
        # Generate BER vs SNR curves (if available)
        self._plot_ber_vs_snr(grouped, output_dir)
        
        logger.info(f"Performance curves saved to {output_dir}")
    
    def _plot_fer_vs_snr(self, grouped: Dict, output_dir: str):
        """Plot FER vs SNR curves."""
        if not MATPLOTLIB_AVAILABLE:
            return
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for (mod, crypto), results in grouped.items():
            # Sort by SNR
            results_sorted = sorted(results, key=lambda r: r['scenario']['snr_db'])
            
            snr_values = [r['scenario']['snr_db'] for r in results_sorted]
            fer_values = [r['metrics'].get('fer', 1.0) for r in results_sorted]
            
            label = f"{mod}FSK, {crypto}"
            ax.semilogy(snr_values, fer_values, marker='o', label=label)
        
        ax.set_xlabel('SNR (dB)')
        ax.set_ylabel('Frame Error Rate (FER)')
        ax.set_title('Frame Error Rate vs SNR')
        ax.grid(True, which='both')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'fer_vs_snr.png'), dpi=150)
        plt.close()
    
    def _plot_warpq_vs_snr(self, grouped: Dict, output_dir: str):
        """Plot WarpQ vs SNR curves."""
        if not MATPLOTLIB_AVAILABLE:
            return
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for (mod, crypto), results in grouped.items():
            # Sort by SNR
            results_sorted = sorted(results, key=lambda r: r['scenario']['snr_db'])
            
            snr_values = [r['scenario']['snr_db'] for r in results_sorted]
            warpq_values = [r['metrics'].get('audio_quality_score') for r in results_sorted]
            
            # Filter out None values
            valid_data = [(s, w) for s, w in zip(snr_values, warpq_values) if w is not None]
            if valid_data:
                snr_valid, warpq_valid = zip(*valid_data)
                label = f"{mod}FSK, {crypto}"
                ax.plot(snr_valid, warpq_valid, marker='o', label=label)
        
        ax.set_xlabel('SNR (dB)')
        ax.set_ylabel('WarpQ Score')
        ax.set_title('Audio Quality (WarpQ) vs SNR')
        ax.grid(True)
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'warpq_vs_snr.png'), dpi=150)
        plt.close()
    
    def _plot_ber_vs_snr(self, grouped: Dict, output_dir: str):
        """Plot BER vs SNR curves."""
        if not MATPLOTLIB_AVAILABLE:
            return
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for (mod, crypto), results in grouped.items():
            # Sort by SNR
            results_sorted = sorted(results, key=lambda r: r['scenario']['snr_db'])
            
            snr_values = [r['scenario']['snr_db'] for r in results_sorted]
            ber_values = [r['metrics'].get('ber') for r in results_sorted]
            
            # Filter out None values
            valid_data = [(s, b) for s, b in zip(snr_values, ber_values) if b is not None]
            if valid_data:
                snr_valid, ber_valid = zip(*valid_data)
                label = f"{mod}FSK, {crypto}"
                ax.semilogy(snr_valid, ber_valid, marker='o', label=label)
        
        ax.set_xlabel('SNR (dB)')
        ax.set_ylabel('Bit Error Rate (BER)')
        ax.set_title('Bit Error Rate vs SNR')
        ax.grid(True, which='both')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'ber_vs_snr.png'), dpi=150)
        plt.close()
    
    def generate_summary_table(self, output_file: str):
        """
        Generate summary statistics table.
        
        Args:
            output_file: Output file path (CSV or Markdown)
        """
        # Group by scenario type
        summary_data = []
        
        for result in self.results:
            if 'scenario' not in result:
                continue
            
            scenario = result['scenario']
            metrics = result.get('metrics', {})
            validation = result.get('validation', {})
            
            summary_data.append({
                'modulation': scenario['modulation'],
                'crypto_mode': scenario['crypto_mode'],
                'channel': scenario['channel'].get('name', 'unknown'),
                'snr_db': scenario['snr_db'],
                'fer': metrics.get('fer'),
                'warpq': metrics.get('audio_quality_score'),
                'frame_count': metrics.get('frame_count', 0),
                'passed': validation.get('overall_pass', False)
            })
        
        # Generate Markdown table
        with open(output_file, 'w') as f:
            f.write("# Test Results Summary\n\n")
            f.write("| Modulation | Crypto | Channel | SNR (dB) | FER | WarpQ | Frames | Pass |\n")
            f.write("|------------|--------|---------|----------|-----|-------|--------|------|\n")
            
            for row in summary_data:
                fer_str = f"{row['fer']:.4f}" if row['fer'] is not None else 'N/A'
                warpq_str = f"{row['warpq']:.2f}" if row['warpq'] is not None else 'N/A'
                f.write(f"| {row['modulation']}FSK | {row['crypto_mode']} | {row['channel']} | "
                       f"{row['snr_db']:.1f} | {fer_str} | "
                       f"{warpq_str} | "
                       f"{row['frame_count']} | {'✓' if row['passed'] else '✗'} |\n")
        
        logger.info(f"Summary table saved to {output_file}")
    
    def generate_report(self, output_file: str, pass_criteria: Dict[str, Any] = None):
        """
        Generate comprehensive test report.
        
        Args:
            output_file: Output report file path
            pass_criteria: Pass criteria dictionary
        """
        report_lines = []
        report_lines.append("# gr-sleipnir Comprehensive Test Report\n")
        report_lines.append(f"Generated: {datetime.now().isoformat()}\n\n")
        
        # Summary statistics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.get('validation', {}).get('overall_pass', False))
        failed_tests = total_tests - passed_tests
        
        report_lines.append("## Executive Summary\n\n")
        report_lines.append(f"- **Total Tests**: {total_tests}\n")
        report_lines.append(f"- **Passed**: {passed_tests}\n")
        report_lines.append(f"- **Failed**: {failed_tests}\n")
        report_lines.append(f"- **Pass Rate**: {passed_tests/total_tests*100:.1f}%\n\n")
        
        # Performance summary
        report_lines.append("## Performance Summary\n\n")
        
        # Group by modulation
        for mod in [4, 8]:
            mod_results = [r for r in self.results if r.get('scenario', {}).get('modulation') == mod]
            if mod_results:
                report_lines.append(f"### {mod}FSK Mode\n\n")
                # Add statistics here
                report_lines.append("\n")
        
        # Issues identified
        report_lines.append("## Issues Identified\n\n")
        issues = []
        for result in self.results:
            validation = result.get('validation', {})
            for check_name, check_result in validation.items():
                if isinstance(check_result, dict) and not check_result.get('pass', True):
                    issues.extend(check_result.get('issues', []))
        
        if issues:
            for issue in set(issues):  # Remove duplicates
                report_lines.append(f"- {issue}\n")
        else:
            report_lines.append("No issues identified.\n")
        
        report_lines.append("\n## Recommendations\n\n")
        report_lines.append("(To be filled based on analysis)\n")
        
        # Write report
        with open(output_file, 'w') as f:
            f.writelines(report_lines)
        
        logger.info(f"Report saved to {output_file}")
    
    def analyze_crypto_overhead(self):
        """
        Analyze crypto overhead by comparing crypto vs non-crypto performance.
        
        Returns:
            Dict with crypto overhead analysis
        """
        # Group results by modulation, channel, and SNR
        grouped = defaultdict(lambda: {'none': [], 'encrypt': [], 'sign': [], 'both': []})
        
        for result in self.results:
            if 'scenario' not in result:
                continue
            
            scenario = result['scenario']
            mod = scenario['modulation']
            channel_name = scenario['channel'].get('name', 'unknown') if isinstance(scenario['channel'], dict) else 'unknown'
            snr = scenario['snr_db']
            crypto = scenario['crypto_mode']
            
            key = (mod, channel_name, snr)
            grouped[key][crypto].append(result)
        
        # Calculate overhead
        overhead_data = []
        
        for (mod, channel, snr), crypto_results in grouped.items():
            baseline = crypto_results.get('none', [])
            encrypt_results = crypto_results.get('encrypt', [])
            sign_results = crypto_results.get('sign', [])
            
            if baseline and (encrypt_results or sign_results):
                baseline_fer = np.mean([r['metrics'].get('fer', 0) for r in baseline if 'metrics' in r])
                baseline_warpq = np.mean([r['metrics'].get('audio_quality_score', 0) 
                                         for r in baseline if 'metrics' in r and r['metrics'].get('audio_quality_score') is not None])
                
                if encrypt_results:
                    encrypt_fer = np.mean([r['metrics'].get('fer', 0) for r in encrypt_results if 'metrics' in r])
                    encrypt_warpq = np.mean([r['metrics'].get('audio_quality_score', 0) 
                                            for r in encrypt_results if 'metrics' in r and r['metrics'].get('audio_quality_score') is not None])
                    
                    fer_overhead = encrypt_fer - baseline_fer
                    warpq_overhead = encrypt_warpq - baseline_warpq if baseline_warpq and encrypt_warpq else None
                    
                    overhead_data.append({
                        'modulation': mod,
                        'channel': channel,
                        'snr': snr,
                        'mode': 'encrypt',
                        'fer_overhead': fer_overhead,
                        'warpq_overhead': warpq_overhead,
                        'baseline_fer': baseline_fer,
                        'baseline_warpq': baseline_warpq
                    })
                
                if sign_results:
                    sign_fer = np.mean([r['metrics'].get('fer', 0) for r in sign_results if 'metrics' in r])
                    sign_warpq = np.mean([r['metrics'].get('audio_quality_score', 0) 
                                        for r in sign_results if 'metrics' in r and r['metrics'].get('audio_quality_score') is not None])
                    
                    fer_overhead = sign_fer - baseline_fer
                    warpq_overhead = sign_warpq - baseline_warpq if baseline_warpq and sign_warpq else None
                    
                    overhead_data.append({
                        'modulation': mod,
                        'channel': channel,
                        'snr': snr,
                        'mode': 'sign',
                        'fer_overhead': fer_overhead,
                        'warpq_overhead': warpq_overhead,
                        'baseline_fer': baseline_fer,
                        'baseline_warpq': baseline_warpq
                    })
        
        # Print analysis
        print(f"\n{'='*80}")
        print(f"Crypto Overhead Analysis")
        print(f"{'='*80}\n")
        
        if overhead_data:
            # Group by mode
            encrypt_overhead = [d for d in overhead_data if d['mode'] == 'encrypt']
            sign_overhead = [d for d in overhead_data if d['mode'] == 'sign']
            
            if encrypt_overhead:
                avg_fer_overhead_encrypt = np.mean([d['fer_overhead'] for d in encrypt_overhead])
                avg_warpq_overhead_encrypt = np.mean([d['warpq_overhead'] for d in encrypt_overhead if d['warpq_overhead'] is not None])
                
                print(f"Encryption Mode:")
                print(f"  Average FER overhead: {avg_fer_overhead_encrypt*100:.3f}%")
                if not np.isnan(avg_warpq_overhead_encrypt):
                    print(f"  Average WarpQ overhead: {avg_warpq_overhead_encrypt:.3f}")
                print()
            
            if sign_overhead:
                avg_fer_overhead_sign = np.mean([d['fer_overhead'] for d in sign_overhead])
                avg_warpq_overhead_sign = np.mean([d['warpq_overhead'] for d in sign_overhead if d['warpq_overhead'] is not None])
                
                print(f"Signature Mode:")
                print(f"  Average FER overhead: {avg_fer_overhead_sign*100:.3f}%")
                if avg_warpq_overhead_sign:
                    print(f"  Average WarpQ overhead: {avg_warpq_overhead_sign:.3f}")
                print()
            
            # Show detailed breakdown by SNR
            print(f"\nDetailed Breakdown (sample):")
            print(f"{'Mod':<6} {'Channel':<10} {'SNR':<8} {'Mode':<10} {'FER Overhead':<15} {'WarpQ Overhead':<15}")
            print(f"{'-'*80}")
            for d in overhead_data[:20]:  # Show first 20
                fer_oh = f"{d['fer_overhead']*100:+.3f}%" if d['fer_overhead'] is not None else "N/A"
                warpq_oh = f"{d['warpq_overhead']:+.3f}" if d['warpq_overhead'] is not None else "N/A"
                print(f"{d['modulation']}FSK  {d['channel']:<10} {d['snr']:>6.1f}  {d['mode']:<10} {fer_oh:<15} {warpq_oh:<15}")
        else:
            print("No crypto overhead data available (need both crypto and non-crypto results)")
        
        return overhead_data
    
    def compare_data_modes(self):
        """
        Compare performance between different data modes (voice vs voice_text).
        
        Returns:
            Dict with data mode comparison analysis
        """
        # Group results by modulation, crypto, channel, SNR, and data_mode
        grouped = defaultdict(lambda: {'voice': [], 'voice_text': []})
        
        for result in self.results:
            if 'scenario' not in result:
                continue
            
            scenario = result['scenario']
            mod = scenario['modulation']
            crypto = scenario['crypto_mode']
            channel_name = scenario['channel'].get('name', 'unknown') if isinstance(scenario['channel'], dict) else 'unknown'
            snr = scenario['snr_db']
            data_mode = scenario.get('data_mode', 'voice')
            
            # Only compare voice and voice_text modes
            if data_mode not in ['voice', 'voice_text']:
                continue
            
            key = (mod, crypto, channel_name, snr)
            grouped[key][data_mode].append(result)
        
        # Calculate comparison metrics
        comparison_data = []
        
        for (mod, crypto, channel, snr), mode_results in grouped.items():
            voice_results = mode_results.get('voice', [])
            voice_text_results = mode_results.get('voice_text', [])
            
            if voice_results and voice_text_results:
                # Calculate averages
                voice_fer = np.mean([r['metrics'].get('fer', 0) for r in voice_results if 'metrics' in r])
                voice_warpq = np.mean([r['metrics'].get('audio_quality_score', 0) 
                                     for r in voice_results if 'metrics' in r and r['metrics'].get('audio_quality_score') is not None])
                
                voice_text_fer = np.mean([r['metrics'].get('fer', 0) for r in voice_text_results if 'metrics' in r])
                voice_text_warpq = np.mean([r['metrics'].get('audio_quality_score', 0) 
                                          for r in voice_text_results if 'metrics' in r and r['metrics'].get('audio_quality_score') is not None])
                
                # Calculate differences
                fer_diff = voice_text_fer - voice_fer
                warpq_diff = voice_text_warpq - voice_warpq if voice_warpq and voice_text_warpq else None
                
                comparison_data.append({
                    'modulation': mod,
                    'crypto_mode': crypto,
                    'channel': channel,
                    'snr': snr,
                    'voice_fer': voice_fer,
                    'voice_text_fer': voice_text_fer,
                    'fer_diff': fer_diff,
                    'voice_warpq': voice_warpq,
                    'voice_text_warpq': voice_text_warpq,
                    'warpq_diff': warpq_diff
                })
        
        # Print analysis
        print(f"\n{'='*80}")
        print(f"Data Mode Comparison Analysis")
        print(f"{'='*80}\n")
        
        if comparison_data:
            # Overall statistics
            avg_fer_diff = np.mean([d['fer_diff'] for d in comparison_data])
            avg_warpq_diff = np.mean([d['warpq_diff'] for d in comparison_data if d['warpq_diff'] is not None])
            
            print(f"Overall Statistics:")
            print(f"  Average FER difference (voice_text - voice): {avg_fer_diff*100:+.3f}%")
            if not np.isnan(avg_warpq_diff):
                print(f"  Average WarpQ difference (voice_text - voice): {avg_warpq_diff:+.3f}")
            print()
            
            # Group by modulation
            for mod in [4, 8]:
                mod_data = [d for d in comparison_data if d['modulation'] == mod]
                if mod_data:
                    mod_fer_diff = np.mean([d['fer_diff'] for d in mod_data])
                    mod_warpq_diff = np.mean([d['warpq_diff'] for d in mod_data if d['warpq_diff'] is not None])
                    
                    print(f"{mod}FSK Mode:")
                    print(f"  Average FER difference: {mod_fer_diff*100:+.3f}%")
                    if not np.isnan(mod_warpq_diff):
                        print(f"  Average WarpQ difference: {mod_warpq_diff:+.3f}")
                    print(f"  Tests compared: {len(mod_data)}")
                    print()
            
            # Group by crypto mode
            for crypto in ['none', 'sign', 'encrypt', 'both']:
                crypto_data = [d for d in comparison_data if d['crypto_mode'] == crypto]
                if crypto_data:
                    crypto_fer_diff = np.mean([d['fer_diff'] for d in crypto_data])
                    crypto_warpq_diff = np.mean([d['warpq_diff'] for d in crypto_data if d['warpq_diff'] is not None])
                    
                    print(f"Crypto Mode '{crypto}':")
                    print(f"  Average FER difference: {crypto_fer_diff*100:+.3f}%")
                    if not np.isnan(crypto_warpq_diff):
                        print(f"  Average WarpQ difference: {crypto_warpq_diff:+.3f}")
                    print(f"  Tests compared: {len(crypto_data)}")
                    print()
            
            # Show detailed breakdown
            print(f"\nDetailed Breakdown (sample):")
            print(f"{'Mod':<6} {'Crypto':<10} {'Channel':<15} {'SNR':<8} {'Voice FER':<12} {'Voice+Text FER':<15} {'FER Diff':<12} {'Voice WarpQ':<13} {'Voice+Text WarpQ':<16} {'WarpQ Diff':<12}")
            print(f"{'-'*120}")
            for d in comparison_data[:30]:  # Show first 30
                fer_diff_str = f"{d['fer_diff']*100:+.3f}%" if d['fer_diff'] is not None else "N/A"
                warpq_diff_str = f"{d['warpq_diff']:+.3f}" if d['warpq_diff'] is not None else "N/A"
                voice_warpq_str = f"{d['voice_warpq']:.2f}" if d['voice_warpq'] else "N/A"
                voice_text_warpq_str = f"{d['voice_text_warpq']:.2f}" if d['voice_text_warpq'] else "N/A"
                
                print(f"{d['modulation']}FSK  {d['crypto_mode']:<10} {d['channel']:<15} {d['snr']:>6.1f}  "
                      f"{d['voice_fer']*100:>10.3f}%  {d['voice_text_fer']*100:>13.3f}%  {fer_diff_str:<12} "
                      f"{voice_warpq_str:<13} {voice_text_warpq_str:<16} {warpq_diff_str:<12}")
        else:
            print("No data mode comparison available (need both 'voice' and 'voice_text' results)")
            print(f"Available data modes in results:")
            data_modes = set()
            for result in self.results:
                if 'scenario' in result:
                    dm = result['scenario'].get('data_mode', 'voice')
                    data_modes.add(dm)
            print(f"  {', '.join(sorted(data_modes))}")
        
        return comparison_data


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Analyze gr-sleipnir test results')
    parser.add_argument('--input', type=str, required=True,
                       help='Input results JSON file')
    parser.add_argument('--output', type=str,
                       help='Output report file (Markdown)')
    parser.add_argument('--report', type=str,
                       help='Output report file (Markdown) - alias for --output')
    parser.add_argument('--plots-dir', type=str,
                       help='Output directory for plots')
    parser.add_argument('--summary-table', type=str,
                       help='Output file for summary table')
    parser.add_argument('--crypto-overhead', action='store_true',
                       help='Analyze crypto overhead')
    parser.add_argument('--compare-data-modes', action='store_true',
                       help='Compare performance between data modes (voice vs voice_text)')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    analyzer = ResultsAnalyzer(args.input)
    
    if args.plots_dir:
        analyzer.generate_performance_curves(args.plots_dir)
    
    if args.summary_table:
        analyzer.generate_summary_table(args.summary_table)
    
    # Use --report if provided, otherwise --output
    report_file = args.report or args.output
    if report_file:
        analyzer.generate_report(report_file)
    
    if args.crypto_overhead:
        analyzer.analyze_crypto_overhead()
    
    if args.compare_data_modes:
        analyzer.compare_data_modes()
    
    return 0


if __name__ == '__main__':
    import os
    from datetime import datetime
    sys.exit(main())
