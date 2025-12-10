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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Analyze gr-sleipnir test results')
    parser.add_argument('--input', type=str, required=True,
                       help='Input results JSON file')
    parser.add_argument('--output', type=str,
                       help='Output report file (Markdown)')
    parser.add_argument('--plots-dir', type=str,
                       help='Output directory for plots')
    parser.add_argument('--summary-table', type=str,
                       help='Output file for summary table')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    analyzer = ResultsAnalyzer(args.input)
    
    if args.plots_dir:
        analyzer.generate_performance_curves(args.plots_dir)
    
    if args.summary_table:
        analyzer.generate_summary_table(args.summary_table)
    
    if args.output:
        analyzer.generate_report(args.output)
    
    return 0


if __name__ == '__main__':
    import os
    from datetime import datetime
    sys.exit(main())
