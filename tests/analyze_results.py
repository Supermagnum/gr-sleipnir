#!/usr/bin/env python3
"""
Results Analysis and Plotting for gr-sleipnir Test Suite

Analyzes test results and generates performance curves and statistics.

Usage:
    python analyze_results.py [--results results_dir] [--output output_dir]
"""

import sys
import json
import csv
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ResultsAnalyzer:
    """Analyze test results and generate plots."""
    
    def __init__(self, results_dir: str):
        self.results_dir = Path(results_dir)
        self.results = []
        self.load_results()
    
    def load_results(self):
        """Load all test results."""
        results_file = self.results_dir / 'all_results.json'
        if results_file.exists():
            with open(results_file, 'r') as f:
                self.results = json.load(f)
            logger.info(f"Loaded {len(self.results)} test results")
        else:
            logger.warning(f"Results file not found: {results_file}")
    
    def filter_results(self, **filters) -> List[Dict]:
        """Filter results by test parameters."""
        filtered = []
        for result in self.results:
            if 'error' in result:
                continue
            
            test_config = result.get('test_config', {})
            match = True
            
            for key, value in filters.items():
                if test_config.get(key) != value:
                    match = False
                    break
            
            if match:
                filtered.append(result)
        
        return filtered
    
    def plot_fer_vs_snr(
        self,
        output_file: str,
        modulation: str = None,
        crypto_mode: str = None,
        channel_type: str = None
    ):
        """Plot Frame Error Rate vs SNR."""
        # Filter results
        filters = {}
        if modulation:
            filters['modulation'] = modulation
        if crypto_mode:
            filters['crypto_mode'] = crypto_mode
        if channel_type:
            filters['channel_type'] = channel_type
        
        filtered = self.filter_results(**filters)
        
        if len(filtered) == 0:
            logger.warning("No results to plot")
            return
        
        # Group by SNR
        snr_data = defaultdict(list)
        for result in filtered:
            snr = result.get('test_config', {}).get('snr_db', 0)
            fer = result.get('metrics', {}).get('fer', 1.0)
            snr_data[snr].append(fer)
        
        # Calculate statistics
        snr_values = sorted(snr_data.keys())
        fer_mean = [np.mean(snr_data[snr]) for snr in snr_values]
        fer_std = [np.std(snr_data[snr]) for snr in snr_values]
        
        # Plot
        plt.figure(figsize=(10, 6))
        plt.errorbar(snr_values, fer_mean, yerr=fer_std, marker='o', linestyle='-', capsize=3)
        plt.xlabel('SNR (dB)')
        plt.ylabel('Frame Error Rate')
        plt.title(f'FER vs SNR ({modulation or "All"} {crypto_mode or "All"} {channel_type or "All"})')
        plt.grid(True, alpha=0.3)
        plt.yscale('log')
        plt.ylim(1e-4, 1.0)
        
        # Add threshold lines
        plt.axhline(y=0.01, color='g', linestyle='--', label='1% FER (Good)')
        plt.axhline(y=0.10, color='orange', linestyle='--', label='10% FER (Acceptable)')
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=150)
        logger.info(f"Saved FER plot to {output_file}")
        plt.close()
    
    def plot_comparison(
        self,
        output_file: str,
        parameter: str,
        snr_db: float = 10.0
    ):
        """Plot comparison across different parameter values."""
        # Filter by SNR
        filtered = [r for r in self.results if 
                   abs(r.get('test_config', {}).get('snr_db', 0) - snr_db) < 0.5]
        
        if len(filtered) == 0:
            logger.warning(f"No results found for SNR={snr_db}dB")
            return
        
        # Group by parameter
        param_data = defaultdict(list)
        for result in filtered:
            param_value = result.get('test_config', {}).get(parameter, 'unknown')
            fer = result.get('metrics', {}).get('fer', 1.0)
            param_data[param_value].append(fer)
        
        # Calculate statistics
        param_values = sorted(param_data.keys())
        fer_mean = [np.mean(param_data[pv]) for pv in param_values]
        fer_std = [np.std(param_data[pv]) for pv in param_values]
        
        # Plot
        plt.figure(figsize=(10, 6))
        x_pos = np.arange(len(param_values))
        plt.bar(x_pos, fer_mean, yerr=fer_std, capsize=5, alpha=0.7)
        plt.xlabel(parameter.replace('_', ' ').title())
        plt.ylabel('Frame Error Rate')
        plt.title(f'FER Comparison at SNR={snr_db}dB')
        plt.xticks(x_pos, param_values, rotation=45, ha='right')
        plt.yscale('log')
        plt.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=150)
        logger.info(f"Saved comparison plot to {output_file}")
        plt.close()
    
    def generate_summary_table(self, output_file: str):
        """Generate summary statistics table."""
        if len(self.results) == 0:
            logger.warning("No results to summarize")
            return
        
        # Group by test configuration
        summary_data = defaultdict(lambda: {
            'count': 0,
            'fer_sum': 0.0,
            'frame_count_sum': 0,
            'error_count_sum': 0,
            'elapsed_time_sum': 0.0
        })
        
        for result in self.results:
            if 'error' in result:
                continue
            
            config = result.get('test_config', {})
            key = (
                config.get('modulation', ''),
                config.get('crypto_mode', ''),
                config.get('channel_type', ''),
                config.get('snr_db', 0)
            )
            
            metrics = result.get('metrics', {})
            summary_data[key]['count'] += 1
            summary_data[key]['fer_sum'] += metrics.get('fer', 1.0)
            summary_data[key]['frame_count_sum'] += metrics.get('frame_count', 0)
            summary_data[key]['error_count_sum'] += metrics.get('error_count', 0)
            summary_data[key]['elapsed_time_sum'] += metrics.get('elapsed_time', 0.0)
        
        # Generate table
        with open(output_file, 'w') as f:
            f.write("# Test Results Summary\n\n")
            f.write("| Modulation | Crypto | Channel | SNR (dB) | Tests | Avg FER | Total Frames | Total Errors |\n")
            f.write("|------------|--------|---------|----------|-------|---------|--------------|--------------|\n")
            
            for key, data in sorted(summary_data.items()):
                mod, crypto, channel, snr = key
                avg_fer = data['fer_sum'] / data['count'] if data['count'] > 0 else 0.0
                f.write(f"| {mod} | {crypto} | {channel} | {snr:.1f} | "
                       f"{data['count']} | {avg_fer:.4f} | {data['frame_count_sum']} | "
                       f"{data['error_count_sum']} |\n")
        
        logger.info(f"Saved summary table to {output_file}")
    
    def generate_report(self, output_file: str, config_file: str = None):
        """Generate comprehensive test report."""
        if len(self.results) == 0:
            logger.warning("No results to report")
            return
        
        # Load validation thresholds if config provided
        thresholds = {}
        if config_file:
            try:
                import yaml
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    thresholds = config.get('validation', {})
            except Exception as e:
                logger.warning(f"Could not load config: {e}")
        
        # Calculate statistics
        total_tests = len(self.results)
        failed_tests = sum(1 for r in self.results if 'error' in r)
        passed_tests = total_tests - failed_tests
        
        # FER statistics
        fers = [r.get('metrics', {}).get('fer', 1.0) for r in self.results if 'error' not in r]
        avg_fer = np.mean(fers) if fers else 0.0
        min_fer = np.min(fers) if fers else 0.0
        max_fer = np.max(fers) if fers else 0.0
        
        # Generate report
        with open(output_file, 'w') as f:
            f.write("# gr-sleipnir Test Suite Report\n\n")
            f.write(f"Generated: {Path(output_file).stat().st_mtime}\n\n")
            
            f.write("## Summary\n\n")
            f.write(f"- Total Tests: {total_tests}\n")
            f.write(f"- Passed: {passed_tests}\n")
            f.write(f"- Failed: {failed_tests}\n")
            f.write(f"- Success Rate: {100.0 * passed_tests / total_tests if total_tests > 0 else 0:.1f}%\n\n")
            
            f.write("## Frame Error Rate Statistics\n\n")
            f.write(f"- Average FER: {avg_fer:.4f}\n")
            f.write(f"- Minimum FER: {min_fer:.4f}\n")
            f.write(f"- Maximum FER: {max_fer:.4f}\n\n")
            
            # Pass/fail criteria
            fer_threshold = thresholds.get('fer_threshold_good', 0.01)
            tests_below_threshold = sum(1 for fer in fers if fer < fer_threshold)
            f.write(f"## Pass/Fail Criteria\n\n")
            f.write(f"- Tests with FER < {fer_threshold} (Good): {tests_below_threshold}/{len(fers)}\n")
            
            # Performance by parameter
            f.write("\n## Performance by Modulation\n\n")
            for mod in ['4FSK', '8FSK']:
                mod_results = self.filter_results(modulation=mod)
                if mod_results:
                    mod_fers = [r.get('metrics', {}).get('fer', 1.0) for r in mod_results]
                    f.write(f"- {mod}: Avg FER = {np.mean(mod_fers):.4f}\n")
            
            f.write("\n## Performance by Crypto Mode\n\n")
            for crypto in ['none', 'sign', 'encrypt', 'both']:
                crypto_results = self.filter_results(crypto_mode=crypto)
                if crypto_results:
                    crypto_fers = [r.get('metrics', {}).get('fer', 1.0) for r in crypto_results]
                    f.write(f"- {crypto}: Avg FER = {np.mean(crypto_fers):.4f}\n")
            
            f.write("\n## Performance by Channel Type\n\n")
            for channel in ['clean', 'AWGN', 'rayleigh', 'rician']:
                channel_results = self.filter_results(channel_type=channel)
                if channel_results:
                    channel_fers = [r.get('metrics', {}).get('fer', 1.0) for r in channel_results]
                    f.write(f"- {channel}: Avg FER = {np.mean(channel_fers):.4f}\n")
        
        logger.info(f"Saved test report to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Analyze gr-sleipnir test results')
    parser.add_argument('--results', type=str, default='test_results',
                       help='Results directory (default: test_results)')
    parser.add_argument('--output', type=str, default='analysis_output',
                       help='Output directory (default: analysis_output)')
    parser.add_argument('--config', type=str, default='config.yaml',
                       help='Config file for thresholds (default: config.yaml)')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Analyze results
    analyzer = ResultsAnalyzer(args.results)
    
    # Generate plots
    logger.info("Generating plots...")
    
    # FER vs SNR for different modulations
    for mod in ['4FSK', '8FSK']:
        analyzer.plot_fer_vs_snr(
            str(output_dir / f'fer_vs_snr_{mod.lower()}.png'),
            modulation=mod
        )
    
    # FER vs SNR for different crypto modes
    for crypto in ['none', 'sign', 'encrypt', 'both']:
        analyzer.plot_fer_vs_snr(
            str(output_dir / f'fer_vs_snr_crypto_{crypto}.png'),
            crypto_mode=crypto
        )
    
    # Comparison plots
    for snr in [0, 5, 10, 15, 20]:
        analyzer.plot_comparison(
            str(output_dir / f'comparison_snr{snr}db.png'),
            'modulation',
            snr_db=float(snr)
        )
    
    # Generate summary
    logger.info("Generating summary...")
    analyzer.generate_summary_table(str(output_dir / 'summary.md'))
    
    # Generate report
    logger.info("Generating report...")
    config_path = Path(args.config)
    if config_path.exists():
        analyzer.generate_report(str(output_dir / 'test_report.md'), str(config_path))
    else:
        analyzer.generate_report(str(output_dir / 'test_report.md'))
    
    logger.info(f"Analysis complete. Output saved to {output_dir}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

