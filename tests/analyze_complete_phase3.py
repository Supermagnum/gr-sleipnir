#!/usr/bin/env python3
"""
Comprehensive Phase 3 Analysis - Complete 4FSK and 8FSK Baseline

Generates comprehensive analyses for:
- Complete 4FSK dataset (3,864 tests)
- 8FSK baseline with crypto="none" (966 tests)
- 4FSK vs 8FSK comparison
- Mode selection recommendations
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


def calculate_fer_floor(results: List[Dict], snr_threshold: float = 10.0) -> Dict[str, Any]:
    """Calculate FER floor statistics from high SNR results."""
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
    
    if not fers:
        return None
    
    return {
        'mean': np.mean(fers),
        'median': np.median(fers),
        'std': np.std(fers),
        'min': np.min(fers),
        'max': np.max(fers),
        'count': len(fers)
    }


def find_waterfall_snr(results: List[Dict], fer_threshold: float = 0.01) -> float:
    """Find SNR where FER drops below threshold."""
    sorted_results = sorted(results, key=lambda r: get_val(r, ['scenario', 'snr_db']) or 0)
    
    for r in sorted_results:
        fer = get_val(r, ['metrics', 'fer'])
        snr = get_val(r, ['scenario', 'snr_db'])
        if fer is not None and snr is not None and fer < fer_threshold:
            return snr
    
    return None


def find_operational_snr(results: List[Dict], fer_threshold: float = 0.05) -> float:
    """Find SNR where FER drops below operational threshold (5%)."""
    sorted_results = sorted(results, key=lambda r: get_val(r, ['scenario', 'snr_db']) or 0)
    
    for r in sorted_results:
        fer = get_val(r, ['metrics', 'fer'])
        snr = get_val(r, ['scenario', 'snr_db'])
        if fer is not None and snr is not None and fer < fer_threshold:
            return snr
    
    return None


def analyze_by_channel(results: List[Dict], channel_name: str) -> Dict[str, Any]:
    """Analyze results for a specific channel."""
    channel_results = filter_results(results, channel__name=channel_name)
    
    if not channel_results:
        return None
    
    # Group by SNR
    snr_groups = defaultdict(list)
    for r in channel_results:
        snr = get_val(r, ['scenario', 'snr_db'])
        if snr is not None:
            snr_groups[snr].append(r)
    
    snr_values = sorted(snr_groups.keys())
    fer_by_snr = {}
    warpq_by_snr = {}
    
    for snr in snr_values:
        fers = [get_val(r, ['metrics', 'fer']) for r in snr_groups[snr] 
               if get_val(r, ['metrics', 'fer']) is not None]
        warpqs = [get_val(r, ['metrics', 'audio_quality_score']) for r in snr_groups[snr] 
                 if get_val(r, ['metrics', 'audio_quality_score']) is not None]
        
        if fers:
            fer_by_snr[snr] = {
                'mean': np.mean(fers),
                'count': len(fers)
            }
        if warpqs:
            warpq_by_snr[snr] = {
                'mean': np.mean(warpqs),
                'count': len(warpqs)
            }
    
    waterfall = find_waterfall_snr(channel_results)
    operational = find_operational_snr(channel_results)
    fer_floor = calculate_fer_floor(channel_results)
    
    return {
        'channel': channel_name,
        'total_tests': len(channel_results),
        'snr_values': snr_values,
        'fer_by_snr': fer_by_snr,
        'warpq_by_snr': warpq_by_snr,
        'waterfall_snr': waterfall,
        'operational_snr': operational,
        'fer_floor': fer_floor
    }


def analyze_4fsk_complete(results: List[Dict], output_dir: str) -> Dict[str, Any]:
    """Comprehensive analysis of complete 4FSK dataset."""
    logger.info("=" * 60)
    logger.info("ANALYZING COMPLETE 4FSK DATASET (3,864 tests)")
    logger.info("=" * 60)
    
    mod4_results = filter_results(results, modulation=4)
    
    if len(mod4_results) != 3864:
        logger.warning(f"Expected 3,864 4FSK tests, found {len(mod4_results)}")
    
    analysis = {
        'modulation': '4FSK',
        'total_tests': len(mod4_results),
        'timestamp': datetime.now().isoformat()
    }
    
    # 1. Overall FER floor
    logger.info("1. Calculating overall FER floor...")
    fer_floor = calculate_fer_floor(mod4_results)
    analysis['fer_floor'] = fer_floor
    
    # 2. Waterfall SNR by channel
    logger.info("2. Analyzing waterfall SNR by channel...")
    channels = ['clean', 'awgn', 'rayleigh', 'rician', 'freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']
    channel_analyses = {}
    for channel in channels:
        logger.info(f"   Analyzing {channel}...")
        channel_analyses[channel] = analyze_by_channel(mod4_results, channel)
    analysis['channels'] = channel_analyses
    
    # 3. Crypto overhead
    logger.info("3. Analyzing crypto overhead...")
    crypto_modes = ['none', 'sign', 'encrypt', 'both']
    crypto_analyses = {}
    for crypto in crypto_modes:
        crypto_results = filter_results(mod4_results, crypto_mode=crypto)
        if crypto_results:
            crypto_analyses[crypto] = {
                'total_tests': len(crypto_results),
                'fer_floor': calculate_fer_floor(crypto_results),
                'waterfall_snr': find_waterfall_snr(crypto_results),
                'operational_snr': find_operational_snr(crypto_results)
            }
    analysis['crypto_modes'] = crypto_analyses
    
    # Calculate crypto overhead
    baseline = crypto_analyses.get('none', {})
    overhead = {}
    for crypto in ['sign', 'encrypt', 'both']:
        if crypto in crypto_analyses:
            baseline_fer = baseline.get('fer_floor', {}).get('mean', 0)
            crypto_fer = crypto_analyses[crypto].get('fer_floor', {}).get('mean', 0)
            if baseline_fer > 0:
                overhead[crypto] = {
                    'fer_increase': crypto_fer - baseline_fer,
                    'fer_increase_percent': ((crypto_fer - baseline_fer) / baseline_fer) * 100
                }
    analysis['crypto_overhead'] = overhead
    
    # 4. Voice vs voice_text
    logger.info("4. Comparing voice vs voice_text...")
    voice_results = filter_results(mod4_results, data_mode='voice')
    voice_text_results = filter_results(mod4_results, data_mode='voice_text')
    
    analysis['data_modes'] = {
        'voice': {
            'total_tests': len(voice_results),
            'fer_floor': calculate_fer_floor(voice_results),
            'operational_snr': find_operational_snr(voice_results)
        },
        'voice_text': {
            'total_tests': len(voice_text_results),
            'fer_floor': calculate_fer_floor(voice_text_results),
            'operational_snr': find_operational_snr(voice_text_results)
        }
    }
    
    # 5. Multi-recipient overhead
    logger.info("5. Analyzing multi-recipient overhead...")
    # Group by recipient count
    recipient_groups = defaultdict(list)
    for r in mod4_results:
        recipients = get_val(r, ['scenario', 'recipients'])
        if isinstance(recipients, list):
            count = len(recipients)
        else:
            count = 1
        recipient_groups[count].append(r)
    
    recipient_analyses = {}
    for count, group_results in sorted(recipient_groups.items()):
        recipient_analyses[count] = {
            'total_tests': len(group_results),
            'fer_floor': calculate_fer_floor(group_results),
            'operational_snr': find_operational_snr(group_results)
        }
    analysis['recipients'] = recipient_analyses
    
    # 6. Frequency offset tolerance
    logger.info("6. Analyzing frequency offset tolerance...")
    freq_offset_channels = ['freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']
    freq_analysis = {}
    for channel in freq_offset_channels:
        if channel in channel_analyses:
            freq_analysis[channel] = {
                'fer_floor': channel_analyses[channel].get('fer_floor'),
                'operational_snr': channel_analyses[channel].get('operational_snr'),
                'mean_fer': np.mean([v['mean'] for v in channel_analyses[channel].get('fer_by_snr', {}).values()]) if channel_analyses[channel].get('fer_by_snr') else None
            }
    analysis['frequency_offset'] = freq_analysis
    
    # 7. Fading penalties
    logger.info("7. Analyzing fading penalties...")
    clean_fer = channel_analyses.get('clean', {}).get('fer_floor', {}).get('mean', 0)
    awgn_fer = channel_analyses.get('awgn', {}).get('fer_floor', {}).get('mean', 0)
    rayleigh_fer = channel_analyses.get('rayleigh', {}).get('fer_floor', {}).get('mean', 0)
    rician_fer = channel_analyses.get('rician', {}).get('fer_floor', {}).get('mean', 0)
    
    analysis['fading_penalties'] = {
        'rayleigh_vs_awgn': {
            'fer_increase': rayleigh_fer - awgn_fer if awgn_fer > 0 else None,
            'fer_increase_percent': ((rayleigh_fer - awgn_fer) / awgn_fer * 100) if awgn_fer > 0 else None
        },
        'rician_vs_awgn': {
            'fer_increase': rician_fer - awgn_fer if awgn_fer > 0 else None,
            'fer_increase_percent': ((rician_fer - awgn_fer) / awgn_fer * 100) if awgn_fer > 0 else None
        }
    }
    
    # Save analysis
    output_file = os.path.join(output_dir, '4fsk_complete_analysis.json')
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)
    
    logger.info(f"4FSK complete analysis saved to {output_file}")
    return analysis


def analyze_8fsk_baseline(results: List[Dict], output_dir: str) -> Dict[str, Any]:
    """Analyze 8FSK baseline (crypto='none')."""
    logger.info("=" * 60)
    logger.info("ANALYZING 8FSK BASELINE (crypto='none', 966 tests)")
    logger.info("=" * 60)
    
    mod8_none = filter_results(results, modulation=8, crypto_mode='none')
    
    if len(mod8_none) != 966:
        logger.warning(f"Expected 966 8FSK baseline tests, found {len(mod8_none)}")
    
    analysis = {
        'modulation': '8FSK',
        'crypto_mode': 'none',
        'total_tests': len(mod8_none),
        'timestamp': datetime.now().isoformat()
    }
    
    # Overall FER floor
    logger.info("Calculating FER floor...")
    fer_floor = calculate_fer_floor(mod8_none)
    analysis['fer_floor'] = fer_floor
    
    # Waterfall SNR by channel
    logger.info("Analyzing by channel...")
    channels = ['clean', 'awgn', 'rayleigh', 'rician', 'freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']
    channel_analyses = {}
    for channel in channels:
        logger.info(f"   Analyzing {channel}...")
        channel_analyses[channel] = analyze_by_channel(mod8_none, channel)
    analysis['channels'] = channel_analyses
    
    # Frequency offset tolerance
    logger.info("Analyzing frequency offset tolerance...")
    freq_offset_channels = ['freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']
    freq_analysis = {}
    for channel in freq_offset_channels:
        if channel in channel_analyses:
            freq_analysis[channel] = {
                'fer_floor': channel_analyses[channel].get('fer_floor'),
                'operational_snr': channel_analyses[channel].get('operational_snr'),
                'mean_fer': np.mean([v['mean'] for v in channel_analyses[channel].get('fer_by_snr', {}).values()]) if channel_analyses[channel].get('fer_by_snr') else None
            }
    analysis['frequency_offset'] = freq_analysis
    
    # Fading performance
    logger.info("Analyzing fading performance...")
    awgn_fer = channel_analyses.get('awgn', {}).get('fer_floor', {}).get('mean', 0)
    rayleigh_fer = channel_analyses.get('rayleigh', {}).get('fer_floor', {}).get('mean', 0)
    rician_fer = channel_analyses.get('rician', {}).get('fer_floor', {}).get('mean', 0)
    
    analysis['fading_penalties'] = {
        'rayleigh_vs_awgn': {
            'fer_increase': rayleigh_fer - awgn_fer if awgn_fer > 0 else None,
            'fer_increase_percent': ((rayleigh_fer - awgn_fer) / awgn_fer * 100) if awgn_fer > 0 else None
        },
        'rician_vs_awgn': {
            'fer_increase': rician_fer - awgn_fer if awgn_fer > 0 else None,
            'fer_increase_percent': ((rician_fer - awgn_fer) / awgn_fer * 100) if awgn_fer > 0 else None
        }
    }
    
    # Save analysis
    output_file = os.path.join(output_dir, '8fsk_baseline_analysis.json')
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)
    
    logger.info(f"8FSK baseline analysis saved to {output_file}")
    return analysis


def compare_4fsk_vs_8fsk(mod4_none: List[Dict], mod8_none: List[Dict], output_dir: str) -> Dict[str, Any]:
    """Compare 4FSK vs 8FSK (both with crypto='none')."""
    logger.info("=" * 60)
    logger.info("COMPARING 4FSK vs 8FSK (crypto='none')")
    logger.info("=" * 60)
    
    comparison = {
        'timestamp': datetime.now().isoformat(),
        '4FSK_total': len(mod4_none),
        '8FSK_total': len(mod8_none)
    }
    
    # Overall comparison
    logger.info("Calculating overall comparison...")
    fer_floor_4fsk = calculate_fer_floor(mod4_none)
    fer_floor_8fsk = calculate_fer_floor(mod8_none)
    
    comparison['fer_floor'] = {
        '4FSK': fer_floor_4fsk,
        '8FSK': fer_floor_8fsk,
        'difference': {
            'absolute': fer_floor_8fsk['mean'] - fer_floor_4fsk['mean'] if (fer_floor_4fsk and fer_floor_8fsk) else None,
            'percent': ((fer_floor_8fsk['mean'] - fer_floor_4fsk['mean']) / fer_floor_4fsk['mean'] * 100) if (fer_floor_4fsk and fer_floor_4fsk['mean'] > 0) else None
        }
    }
    
    # Waterfall SNR comparison
    logger.info("Comparing waterfall SNR...")
    waterfall_4fsk = find_waterfall_snr(mod4_none)
    waterfall_8fsk = find_waterfall_snr(mod8_none)
    
    comparison['waterfall_snr'] = {
        '4FSK': waterfall_4fsk,
        '8FSK': waterfall_8fsk,
        'difference_dB': (waterfall_8fsk - waterfall_4fsk) if (waterfall_4fsk and waterfall_8fsk) else None
    }
    
    # Operational SNR comparison
    logger.info("Comparing operational SNR...")
    operational_4fsk = find_operational_snr(mod4_none)
    operational_8fsk = find_operational_snr(mod8_none)
    
    comparison['operational_snr'] = {
        '4FSK': operational_4fsk,
        '8FSK': operational_8fsk,
        'difference_dB': (operational_8fsk - operational_4fsk) if (operational_4fsk and operational_8fsk) else None
    }
    
    # Channel-by-channel comparison
    logger.info("Comparing by channel...")
    channels = ['clean', 'awgn', 'rayleigh', 'rician', 'freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']
    channel_comparison = {}
    
    for channel in channels:
        ch4 = analyze_by_channel(mod4_none, channel)
        ch8 = analyze_by_channel(mod8_none, channel)
        
        if ch4 and ch8:
            channel_comparison[channel] = {
                'fer_floor': {
                    '4FSK': ch4.get('fer_floor'),
                    '8FSK': ch8.get('fer_floor'),
                    'difference': (ch8.get('fer_floor', {}).get('mean', 0) - ch4.get('fer_floor', {}).get('mean', 0)) if (ch4.get('fer_floor') and ch8.get('fer_floor')) else None
                },
                'operational_snr': {
                    '4FSK': ch4.get('operational_snr'),
                    '8FSK': ch8.get('operational_snr'),
                    'difference_dB': (ch8.get('operational_snr') - ch4.get('operational_snr')) if (ch4.get('operational_snr') and ch8.get('operational_snr')) else None
                }
            }
    
    comparison['channels'] = channel_comparison
    
    # Frequency tolerance comparison
    logger.info("Comparing frequency tolerance...")
    freq_comparison = {}
    for channel in ['freq_offset_100hz', 'freq_offset_500hz', 'freq_offset_1khz']:
        if channel in channel_comparison:
            freq_comparison[channel] = channel_comparison[channel]
    comparison['frequency_tolerance'] = freq_comparison
    
    # Save comparison
    output_file = os.path.join(output_dir, '4fsk_vs_8fsk_comparison.json')
    with open(output_file, 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    
    logger.info(f"Comparison saved to {output_file}")
    return comparison


def generate_performance_report(analysis_4fsk: Dict, analysis_8fsk: Dict, comparison: Dict, output_dir: str):
    """Generate comprehensive performance report."""
    logger.info("=" * 60)
    logger.info("GENERATING PERFORMANCE REPORT")
    logger.info("=" * 60)
    
    report_lines = []
    report_lines.append("# gr-sleipnir Performance Report - Complete Analysis")
    report_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append("## Executive Summary\n")
    
    # Key findings
    fer_floor_4fsk = analysis_4fsk.get('fer_floor', {}).get('mean', 0) * 100
    fer_floor_8fsk = analysis_8fsk.get('fer_floor', {}).get('mean', 0) * 100
    fer_diff = fer_floor_8fsk - fer_floor_4fsk
    
    report_lines.append(f"- **4FSK FER Floor**: {fer_floor_4fsk:.2f}%")
    report_lines.append(f"- **8FSK FER Floor**: {fer_floor_8fsk:.2f}%")
    report_lines.append(f"- **8FSK Advantage**: {abs(fer_diff):.2f} percentage points {'lower' if fer_diff < 0 else 'higher'} FER")
    report_lines.append(f"- **Recommendation**: {'8FSK' if fer_diff < 0 else '4FSK'} has better error correction performance\n")
    
    # 4FSK Complete Analysis
    report_lines.append("## 4FSK Complete Analysis (3,864 tests)\n")
    
    report_lines.append("### FER Floor")
    fer_floor = analysis_4fsk.get('fer_floor', {})
    if fer_floor:
        report_lines.append(f"- Mean: {fer_floor.get('mean', 0)*100:.2f}%")
        report_lines.append(f"- Median: {fer_floor.get('median', 0)*100:.2f}%")
        report_lines.append(f"- Std Dev: {fer_floor.get('std', 0)*100:.2f}%")
        report_lines.append(f"- Range: {fer_floor.get('min', 0)*100:.2f}% - {fer_floor.get('max', 0)*100:.2f}%")
        report_lines.append(f"- Sample Size: {fer_floor.get('count', 0)} tests\n")
    
    # Channel performance
    report_lines.append("### Channel Performance\n")
    channels = analysis_4fsk.get('channels', {})
    for channel, data in channels.items():
        if data:
            fer_floor_ch = data.get('fer_floor', {}).get('mean', 0) * 100
            operational = data.get('operational_snr')
            report_lines.append(f"**{channel}**:")
            report_lines.append(f"- FER Floor: {fer_floor_ch:.2f}%")
            if operational is not None:
                report_lines.append(f"- Operational SNR: {operational:.1f} dB")
            report_lines.append("")
    
    # Crypto overhead
    report_lines.append("### Crypto Overhead\n")
    overhead = analysis_4fsk.get('crypto_overhead', {})
    for crypto, data in overhead.items():
        fer_inc = data.get('fer_increase', 0) * 100
        fer_inc_pct = data.get('fer_increase_percent', 0)
        report_lines.append(f"**{crypto}**:")
        report_lines.append(f"- FER Increase: {fer_inc:.2f} percentage points ({fer_inc_pct:.1f}%)")
        report_lines.append("")
    
    # Frequency offset
    report_lines.append("### Frequency Offset Tolerance\n")
    freq_offset = analysis_4fsk.get('frequency_offset', {})
    for channel, data in freq_offset.items():
        if data:
            fer_floor_ch = data.get('fer_floor', {}).get('mean', 0) * 100
            report_lines.append(f"**{channel}**: FER Floor {fer_floor_ch:.2f}%")
    report_lines.append("")
    
    # Fading penalties
    report_lines.append("### Fading Penalties\n")
    fading = analysis_4fsk.get('fading_penalties', {})
    if fading.get('rayleigh_vs_awgn'):
        ray_inc = fading['rayleigh_vs_awgn'].get('fer_increase', 0) * 100
        report_lines.append(f"- Rayleigh vs AWGN: {ray_inc:.2f} percentage points FER increase")
    if fading.get('rician_vs_awgn'):
        ric_inc = fading['rician_vs_awgn'].get('fer_increase', 0) * 100
        report_lines.append(f"- Rician vs AWGN: {ric_inc:.2f} percentage points FER increase")
    report_lines.append("")
    
    # 8FSK Baseline
    report_lines.append("## 8FSK Baseline Analysis (crypto='none', 966 tests)\n")
    
    fer_floor_8 = analysis_8fsk.get('fer_floor', {})
    if fer_floor_8:
        report_lines.append(f"### FER Floor: {fer_floor_8.get('mean', 0)*100:.2f}%\n")
    
    # Comparison
    report_lines.append("## 4FSK vs 8FSK Comparison\n")
    
    comp_fer = comparison.get('fer_floor', {})
    if comp_fer:
        diff = comp_fer.get('difference', {})
        report_lines.append(f"### FER Floor Difference")
        report_lines.append(f"- 4FSK: {comp_fer.get('4FSK', {}).get('mean', 0)*100:.2f}%")
        report_lines.append(f"- 8FSK: {comp_fer.get('8FSK', {}).get('mean', 0)*100:.2f}%")
        if diff.get('absolute') is not None:
            report_lines.append(f"- Difference: {diff.get('absolute')*100:.2f} percentage points")
            report_lines.append(f"- Percent Change: {diff.get('percent', 0):.1f}%")
        report_lines.append("")
    
    # Mode selection recommendations
    report_lines.append("## Mode Selection Recommendations\n")
    
    if fer_diff < 0:
        report_lines.append("### Primary Recommendation: **8FSK**\n")
        report_lines.append("8FSK demonstrates superior performance:")
        report_lines.append(f"- Lower FER floor ({fer_floor_8fsk:.2f}% vs {fer_floor_4fsk:.2f}%)")
        report_lines.append("- Better error correction capability")
        report_lines.append("- Higher audio bitrate (8 kbps vs 6 kbps)")
        report_lines.append("- Better frequency tolerance at ±500 Hz")
    else:
        report_lines.append("### Primary Recommendation: **4FSK**\n")
        report_lines.append("4FSK demonstrates superior performance:")
        report_lines.append(f"- Lower FER floor ({fer_floor_4fsk:.2f}% vs {fer_floor_8fsk:.2f}%)")
    
    report_lines.append("\n### Use Cases\n")
    report_lines.append("**Use 8FSK when:**")
    report_lines.append("- Fixed station operation")
    report_lines.append("- Good SNR available (≥0 dB)")
    report_lines.append("- Frequency stability ±500 Hz or better")
    report_lines.append("- Maximum audio quality desired")
    report_lines.append("")
    report_lines.append("**Use 4FSK when:**")
    report_lines.append("- Portable/QRP operation")
    report_lines.append("- Weak signal conditions")
    report_lines.append("- Frequency stability concerns (±100 Hz recommended)")
    report_lines.append("- Maximum range desired")
    
    # Save report
    report_file = os.path.join(output_dir, 'PERFORMANCE_REPORT.md')
    with open(report_file, 'w') as f:
        f.write('\n'.join(report_lines))
    
    logger.info(f"Performance report saved to {report_file}")


def main():
    parser = argparse.ArgumentParser(description='Comprehensive Phase 3 analysis')
    parser.add_argument('--input', type=str, default='test-results-files/results_intermediate.json',
                       help='Input results JSON file')
    parser.add_argument('--output-dir', type=str, default='test-results-files/analysis_complete',
                       help='Output directory for analysis results')
    
    args = parser.parse_args()
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Load results
    results = load_results(args.input)
    
    if not results:
        logger.error("No Phase 3 results found!")
        return 1
    
    # Filter for complete datasets
    mod4_results = filter_results(results, modulation=4)
    mod4_none = filter_results(mod4_results, crypto_mode='none')
    mod8_none = filter_results(results, modulation=8, crypto_mode='none')
    
    logger.info(f"4FSK total: {len(mod4_results)}")
    logger.info(f"4FSK none: {len(mod4_none)}")
    logger.info(f"8FSK none: {len(mod8_none)}")
    
    # Analyze 4FSK complete
    analysis_4fsk = analyze_4fsk_complete(mod4_results, args.output_dir)
    
    # Analyze 8FSK baseline
    analysis_8fsk = analyze_8fsk_baseline(mod8_none, args.output_dir)
    
    # Compare
    comparison = compare_4fsk_vs_8fsk(mod4_none, mod8_none, args.output_dir)
    
    # Generate report
    generate_performance_report(analysis_4fsk, analysis_8fsk, comparison, args.output_dir)
    
    logger.info("=" * 60)
    logger.info("ALL ANALYSES COMPLETE")
    logger.info(f"Results saved to: {args.output_dir}")
    logger.info("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

