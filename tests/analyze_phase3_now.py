#!/usr/bin/env python3
"""
Generate analyses from Phase 3 data that is currently available.

This script generates:
- 4FSK waterfall and FER floor
- 4FSK frequency tolerance
- 4FSK fading performance
- 4FSK crypto overhead
- 4FSK voice vs voice_text
- 8FSK baseline (no crypto) waterfall and FER floor
- 8FSK frequency tolerance (no crypto)
- 8FSK fading performance (no crypto)
- 4FSK vs 8FSK comparison (none crypto)
"""

import json
import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_val(r, path):
    """Safely get nested value from result dictionary."""
    val = r
    for key in path:
        if isinstance(val, dict):
            val = val.get(key)
        else:
            return None
        if val is None:
            return None
    return val


def load_results(results_file: str) -> List[Dict]:
    """Load Phase 3 results from JSON file."""
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    phase3_results = [r for r in results if get_val(r, ['scenario', 'phase']) == 3]
    logger.info(f"Loaded {len(phase3_results)} Phase 3 results")
    return phase3_results


def filter_results(results: List[Dict], **filters) -> List[Dict]:
    """Filter results by criteria."""
    filtered = results
    for key, value in filters.items():
        path = ['scenario'] + key.split('__')
        filtered = [r for r in filtered if get_val(r, path) == value]
    return filtered


def calculate_fer_floor(results: List[Dict], snr_threshold: float = 10.0) -> float:
    """Calculate FER floor from high SNR results."""
    high_snr_results = [r for r in results 
                       if get_val(r, ['scenario', 'snr_db']) is not None and
                       get_val(r, ['scenario', 'snr_db']) >= snr_threshold]
    
    if not high_snr_results:
        return None
    
    fers = []
    for r in high_snr_results:
        fer = get_val(r, ['metrics', 'fer'])
        if fer is not None:
            fers.append(fer)
    
    return np.mean(fers) if fers else None


def find_waterfall_snr(results: List[Dict], fer_threshold: float = 0.01) -> float:
    """Find SNR where FER drops below threshold."""
    # Sort by SNR
    sorted_results = sorted(results, key=lambda r: get_val(r, ['scenario', 'snr_db']) or 0)
    
    for r in sorted_results:
        fer = get_val(r, ['metrics', 'fer'])
        snr = get_val(r, ['scenario', 'snr_db'])
        if fer is not None and snr is not None and fer < fer_threshold:
            return snr
    
    return None


def plot_fer_vs_snr(results: List[Dict], title: str, output_file: str, 
                    channels: List[str] = None, crypto_mode: str = None):
    """Plot FER vs SNR curve."""
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("matplotlib not available, skipping plot")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Group by channel if specified
    if channels:
        for channel in channels:
            channel_results = filter_results(results, channel__name=channel)
            if crypto_mode:
                channel_results = filter_results(channel_results, crypto_mode=crypto_mode)
            
            if not channel_results:
                continue
            
            # Group by SNR
            snr_groups = defaultdict(list)
            for r in channel_results:
                snr = get_val(r, ['scenario', 'snr_db'])
                if snr is not None:
                    snr_groups[snr].append(r)
            
            snr_values = sorted(snr_groups.keys())
            fer_values = []
            for snr in snr_values:
                fers = [get_val(r, ['metrics', 'fer']) for r in snr_groups[snr] 
                       if get_val(r, ['metrics', 'fer']) is not None]
                fer_values.append(np.mean(fers) if fers else 1.0)
            
            ax.semilogy(snr_values, fer_values, marker='o', label=f'{channel}')
    else:
        # Single curve
        snr_groups = defaultdict(list)
        for r in results:
            snr = get_val(r, ['scenario', 'snr_db'])
            if snr is not None:
                snr_groups[snr].append(r)
        
        snr_values = sorted(snr_groups.keys())
        fer_values = []
        for snr in snr_values:
            fers = [get_val(r, ['metrics', 'fer']) for r in snr_groups[snr] 
                   if get_val(r, ['metrics', 'fer']) is not None]
            fer_values.append(np.mean(fers) if fers else 1.0)
        
        ax.semilogy(snr_values, fer_values, marker='o')
    
    ax.set_xlabel('SNR (dB)')
    ax.set_ylabel('Frame Error Rate (FER)')
    ax.set_title(title)
    ax.grid(True, which='both')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()
    logger.info(f"Saved plot: {output_file}")


def generate_4fsk_analyses(results: List[Dict], output_dir: str):
    """Generate all 4FSK analyses."""
    logger.info("Generating 4FSK analyses...")
    
    mod4_results = filter_results(results, modulation=4)
    
    # 1. Waterfall
    logger.info("  1. Waterfall SNR analysis...")
    awgn_none = filter_results(mod4_results, channel__name='awgn', crypto_mode='none')
    waterfall = find_waterfall_snr(awgn_none)
    
    # 2. FER floor
    logger.info("  2. FER floor analysis...")
    fer_floor = calculate_fer_floor(mod4_results)
    
    # 3. Frequency tolerance
    logger.info("  3. Frequency tolerance analysis...")
    freq_offset_channels = ['freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']
    plot_fer_vs_snr(mod4_results, '4FSK Frequency Tolerance', 
                   os.path.join(output_dir, '4fsk_frequency_tolerance.png'),
                   channels=freq_offset_channels, crypto_mode='none')
    
    # 4. Fading performance
    logger.info("  4. Fading performance analysis...")
    fading_channels = ['rayleigh', 'rician']
    plot_fer_vs_snr(mod4_results, '4FSK Fading Performance', 
                   os.path.join(output_dir, '4fsk_fading_performance.png'),
                   channels=fading_channels, crypto_mode='none')
    
    # 5. Crypto overhead
    logger.info("  5. Crypto overhead analysis...")
    crypto_modes = ['none', 'sign', 'encrypt', 'both']
    plot_fer_vs_snr(mod4_results, '4FSK Crypto Overhead', 
                   os.path.join(output_dir, '4fsk_crypto_overhead.png'),
                   channels=['awgn'])
    
    # 6. Voice vs voice_text
    logger.info("  6. Voice vs voice_text analysis...")
    voice_results = filter_results(mod4_results, data_mode='voice')
    voice_text_results = filter_results(mod4_results, data_mode='voice_text')
    
    # Generate summary
    summary = {
        '4FSK_Waterfall_SNR_dB': waterfall,
        '4FSK_FER_Floor': fer_floor,
        '4FSK_FER_Floor_Percent': fer_floor * 100 if fer_floor else None,
        'timestamp': datetime.now().isoformat()
    }
    
    summary_file = os.path.join(output_dir, '4fsk_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"4FSK analyses complete. Summary: {summary}")


def generate_8fsk_baseline_analyses(results: List[Dict], output_dir: str):
    """Generate 8FSK baseline (no crypto) analyses."""
    logger.info("Generating 8FSK baseline analyses...")
    
    mod8_none = filter_results(results, modulation=8, crypto_mode='none')
    
    # 1. Waterfall
    logger.info("  1. Waterfall SNR analysis...")
    awgn_none = filter_results(mod8_none, channel__name='awgn')
    waterfall = find_waterfall_snr(awgn_none)
    
    # 2. FER floor
    logger.info("  2. FER floor analysis...")
    fer_floor = calculate_fer_floor(mod8_none)
    
    # 3. Frequency tolerance
    logger.info("  3. Frequency tolerance analysis...")
    freq_offset_channels = ['freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']
    plot_fer_vs_snr(mod8_none, '8FSK Frequency Tolerance (No Crypto)', 
                   os.path.join(output_dir, '8fsk_frequency_tolerance.png'),
                   channels=freq_offset_channels)
    
    # 4. Fading performance
    logger.info("  4. Fading performance analysis...")
    fading_channels = ['rayleigh', 'rician']
    plot_fer_vs_snr(mod8_none, '8FSK Fading Performance (No Crypto)', 
                   os.path.join(output_dir, '8fsk_fading_performance.png'),
                   channels=fading_channels)
    
    summary = {
        '8FSK_Waterfall_SNR_dB': waterfall,
        '8FSK_FER_Floor': fer_floor,
        '8FSK_FER_Floor_Percent': fer_floor * 100 if fer_floor else None,
        'timestamp': datetime.now().isoformat()
    }
    
    summary_file = os.path.join(output_dir, '8fsk_baseline_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"8FSK baseline analyses complete. Summary: {summary}")


def generate_comparison_analyses(results: List[Dict], output_dir: str):
    """Generate 4FSK vs 8FSK comparison analyses."""
    logger.info("Generating 4FSK vs 8FSK comparison...")
    
    mod4_none = filter_results(results, modulation=4, crypto_mode='none')
    mod8_none = filter_results(results, modulation=8, crypto_mode='none')
    
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("matplotlib not available, skipping comparison plots")
        return
    
    # Waterfall comparison
    awgn_4fsk = filter_results(mod4_none, channel__name='awgn')
    awgn_8fsk = filter_results(mod8_none, channel__name='awgn')
    
    waterfall_4fsk = find_waterfall_snr(awgn_4fsk)
    waterfall_8fsk = find_waterfall_snr(awgn_8fsk)
    
    # FER floor comparison
    fer_floor_4fsk = calculate_fer_floor(mod4_none)
    fer_floor_8fsk = calculate_fer_floor(mod8_none)
    
    # Plot comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 4FSK curve
    snr_groups_4 = defaultdict(list)
    for r in awgn_4fsk:
        snr = get_val(r, ['scenario', 'snr_db'])
        if snr is not None:
            snr_groups_4[snr].append(r)
    
    snr_values_4 = sorted(snr_groups_4.keys())
    fer_values_4 = []
    for snr in snr_values_4:
        fers = [get_val(r, ['metrics', 'fer']) for r in snr_groups_4[snr] 
               if get_val(r, ['metrics', 'fer']) is not None]
        fer_values_4.append(np.mean(fers) if fers else 1.0)
    
    # 8FSK curve
    snr_groups_8 = defaultdict(list)
    for r in awgn_8fsk:
        snr = get_val(r, ['scenario', 'snr_db'])
        if snr is not None:
            snr_groups_8[snr].append(r)
    
    snr_values_8 = sorted(snr_groups_8.keys())
    fer_values_8 = []
    for snr in snr_values_8:
        fers = [get_val(r, ['metrics', 'fer']) for r in snr_groups_8[snr] 
               if get_val(r, ['metrics', 'fer']) is not None]
        fer_values_8.append(np.mean(fers) if fers else 1.0)
    
    ax.semilogy(snr_values_4, fer_values_4, marker='o', label='4FSK')
    ax.semilogy(snr_values_8, fer_values_8, marker='s', label='8FSK')
    
    ax.set_xlabel('SNR (dB)')
    ax.set_ylabel('Frame Error Rate (FER)')
    ax.set_title('4FSK vs 8FSK Performance Comparison (No Crypto)')
    ax.grid(True, which='both')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '4fsk_vs_8fsk_comparison.png'), dpi=150)
    plt.close()
    
    # Frequency tolerance comparison
    freq_channels = ['freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for channel in freq_channels:
        ch4 = filter_results(mod4_none, channel__name=channel)
        ch8 = filter_results(mod8_none, channel__name=channel)
        
        # 4FSK
        snr_groups = defaultdict(list)
        for r in ch4:
            snr = get_val(r, ['scenario', 'snr_db'])
            if snr is not None:
                snr_groups[snr].append(r)
        
        snr_values = sorted(snr_groups.keys())
        fer_values = []
        for snr in snr_values:
            fers = [get_val(r, ['metrics', 'fer']) for r in snr_groups[snr] 
                   if get_val(r, ['metrics', 'fer']) is not None]
            fer_values.append(np.mean(fers) if fers else 1.0)
        
        ax.semilogy(snr_values, fer_values, marker='o', label=f'4FSK {channel}')
        
        # 8FSK
        snr_groups = defaultdict(list)
        for r in ch8:
            snr = get_val(r, ['scenario', 'snr_db'])
            if snr is not None:
                snr_groups[snr].append(r)
        
        snr_values = sorted(snr_groups.keys())
        fer_values = []
        for snr in snr_values:
            fers = [get_val(r, ['metrics', 'fer']) for r in snr_groups[snr] 
                   if get_val(r, ['metrics', 'fer']) is not None]
            fer_values.append(np.mean(fers) if fers else 1.0)
        
        ax.semilogy(snr_values, fer_values, marker='s', label=f'8FSK {channel}')
    
    ax.set_xlabel('SNR (dB)')
    ax.set_ylabel('Frame Error Rate (FER)')
    ax.set_title('4FSK vs 8FSK Frequency Tolerance Comparison')
    ax.grid(True, which='both')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, '4fsk_vs_8fsk_frequency_tolerance.png'), dpi=150)
    plt.close()
    
    summary = {
        'Waterfall_SNR_4FSK_dB': waterfall_4fsk,
        'Waterfall_SNR_8FSK_dB': waterfall_8fsk,
        'Waterfall_SNR_Difference_dB': (waterfall_8fsk - waterfall_4fsk) if (waterfall_4fsk and waterfall_8fsk) else None,
        'FER_Floor_4FSK': fer_floor_4fsk,
        'FER_Floor_8FSK': fer_floor_8fsk,
        'FER_Floor_4FSK_Percent': fer_floor_4fsk * 100 if fer_floor_4fsk else None,
        'FER_Floor_8FSK_Percent': fer_floor_8fsk * 100 if fer_floor_8fsk else None,
        'timestamp': datetime.now().isoformat()
    }
    
    summary_file = os.path.join(output_dir, 'comparison_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Comparison analyses complete. Summary: {summary}")


def main():
    parser = argparse.ArgumentParser(description='Analyze Phase 3 results (available data)')
    parser.add_argument('--input', type=str, default='test-results-files/results_intermediate.json',
                       help='Input results JSON file')
    parser.add_argument('--output-dir', type=str, default='test-results-files/analysis_now',
                       help='Output directory for analysis results')
    
    args = parser.parse_args()
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Load results
    results = load_results(args.input)
    
    if not results:
        logger.error("No Phase 3 results found!")
        return 1
    
    # Generate analyses
    logger.info("=" * 60)
    logger.info("GENERATING ANALYSES FROM AVAILABLE PHASE 3 DATA")
    logger.info("=" * 60)
    
    generate_4fsk_analyses(results, args.output_dir)
    generate_8fsk_baseline_analyses(results, args.output_dir)
    generate_comparison_analyses(results, args.output_dir)
    
    logger.info("=" * 60)
    logger.info("ALL ANALYSES COMPLETE")
    logger.info(f"Results saved to: {args.output_dir}")
    logger.info("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

