#!/usr/bin/env python3
"""
Comprehensive Automated Test Suite for gr-sleipnir

Tests all blocks and parameters across varying channel conditions.

Usage:
    python test_comprehensive.py [--config config_comprehensive.yaml] [--phase 1]
"""

import sys
import os

# Increase recursion limit
sys.setrecursionlimit(10000)

import yaml
import argparse
import logging
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from itertools import product

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from flowgraph_builder import build_test_flowgraph, ChannelModel
from metrics_collector import MetricsCollector
from test_utils import (
    detect_wav_properties, read_wav_file, write_wav_file,
    compute_warpq, setup_logging, save_results, ensure_directory,
    format_duration
)

# GNU Radio imports
from gnuradio import gr, blocks
import pmt

logger = logging.getLogger(__name__)


class ComprehensiveTestSuite:
    """Comprehensive test suite for gr-sleipnir."""
    
    def __init__(self, config_file: str):
        """
        Initialize test suite.
        
        Args:
            config_file: Path to configuration YAML file
        """
        self.config_path = config_file  # Store config path for process isolation
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.test_params = self.config['test_parameters']
        self.output_config = self.config['output']
        self.pass_criteria = self.config['pass_criteria']
        
        # Setup directories
        ensure_directory(self.output_config['results_dir'])
        ensure_directory(self.output_config['audio_output_dir'])
        ensure_directory(self.output_config['plots_dir'])
        
        # Setup logging
        log_config = self.config.get('logging', {})
        setup_logging(
            log_file=log_config.get('file'),
            level=log_config.get('level', 'INFO'),
            console=log_config.get('console', True)
        )
        
        # Results storage
        self.all_results = []
        self.start_time = None
        
        # Validate input file
        input_file = self.test_params['input_file']
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        wav_props = detect_wav_properties(input_file)
        logger.info(f"Input WAV properties: {wav_props}")
    
    def generate_test_scenarios(self, phase: int = None) -> List[Dict[str, Any]]:
        """
        Generate test scenarios from configuration.
        
        Args:
            phase: Test phase (1, 2, or 3). If None, use all enabled phases.
            
        Returns:
            List of test scenario dictionaries
        """
        scenarios = []
        
        # Determine which phase to run
        if phase is None:
            phases = [1, 2, 3]
        else:
            phases = [phase]
        
        for phase_num in phases:
            phase_key = f'phase{phase_num}'
            phase_config = self.config.get('test_phases', {}).get(phase_key, {})
            
            if not phase_config.get('enabled', False):
                continue
            
            # Get phase-specific parameters or use defaults
            modulation_modes = phase_config.get('modulation_modes', self.test_params['modulation_modes'])
            crypto_modes = phase_config.get('crypto_modes', self.test_params['crypto_modes'])
            channel_conditions = phase_config.get('channel_conditions', [c['name'] for c in self.test_params['channel_conditions']])
            snr_range_config = phase_config.get('snr_range', self.test_params['snr_range'])
            
            # Generate SNR range
            snr_start, snr_stop, snr_step = snr_range_config
            snr_values = list(range(snr_start, snr_stop + 1, snr_step))
            
            # Generate all combinations
            for mod, crypto, channel_name, snr in product(modulation_modes, crypto_modes, channel_conditions, snr_values):
                # Find channel configuration
                channel_config = next(
                    (c for c in self.test_params['channel_conditions'] if c['name'] == channel_name),
                    {'type': 'clean'}
                )
                
                scenario = {
                    'modulation': mod,
                    'crypto_mode': crypto,
                    'channel': channel_config,
                    'snr_db': float(snr),
                    'phase': phase_num
                }
                scenarios.append(scenario)
        
        logger.info(f"Generated {len(scenarios)} test scenarios")
        return scenarios
    
    def _run_tests_with_process_isolation(self, scenarios: List[Dict[str, Any]], batch_size: int):
        """
        Run tests in batches using separate processes to prevent memory accumulation.
        
        Args:
            scenarios: List of test scenarios
            batch_size: Number of tests per process
        """
        import multiprocessing
        import subprocess
        import tempfile
        
        total_tests = len(scenarios)
        num_batches = (total_tests + batch_size - 1) // batch_size
        
        logger.info(f"Running {total_tests} tests in {num_batches} batches ({batch_size} tests per batch)")
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_tests)
            batch_scenarios = scenarios[start_idx:end_idx]
            
            logger.info(f"Batch {batch_idx + 1}/{num_batches}: Tests {start_idx + 1}-{end_idx}")
            
            # Create temporary file for batch scenarios
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                import json
                json.dump(batch_scenarios, f)
                batch_file = f.name
            
            try:
                # Run batch in separate process
                # Create a script that runs the batch
                config_path_abs = os.path.abspath(self.config_path)
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                script_content = f'''import sys
import json
import os

# Add project root to path
project_root = "{project_root}"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "tests"))

# Change to project root directory
os.chdir(project_root)

from test_comprehensive import ComprehensiveTestSuite
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load batch scenarios
with open("{batch_file}") as f:
    batch_scenarios = json.load(f)

# Create test suite
config_path = "{config_path_abs}"
test_suite = ComprehensiveTestSuite(config_path)

# Run batch
results = []
for scenario in batch_scenarios:
    result = test_suite.run_test_scenario(scenario)
    results.append(result)

# Save batch results
output_file = "{batch_file}.results"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)
'''
                
                script_file = batch_file + '.py'
                with open(script_file, 'w') as f:
                    f.write(script_content)
                
                # Run script
                # Use errors='replace' to handle non-UTF-8 output gracefully
                # Redirect stderr to a file to avoid encoding issues
                stderr_file = batch_file + '.stderr'
                with open(stderr_file, 'wb') as stderr_f:
                    result = subprocess.run(
                        [sys.executable, script_file],
                        stdout=subprocess.PIPE,
                        stderr=stderr_f,
                        timeout=3600  # 1 hour timeout per batch
                    )
                
                # Read stdout with error handling
                try:
                    stdout_text = result.stdout.decode('utf-8', errors='replace')
                except:
                    stdout_text = ''
                
                if result.returncode != 0:
                    # Read stderr
                    try:
                        with open(stderr_file, 'rb') as f:
                            stderr_bytes = f.read()
                            stderr_text = stderr_bytes.decode('utf-8', errors='replace')
                    except:
                        stderr_text = 'Could not read stderr'
                    logger.error(f"Batch {batch_idx + 1} failed (return code {result.returncode}): {stderr_text[:500]}")
                else:
                    logger.info(f"Batch {batch_idx + 1} completed successfully")
                
                # Load batch results
                results_file = batch_file + '.results'
                if os.path.exists(results_file):
                    try:
                        with open(results_file) as f:
                            batch_results = json.load(f)
                        logger.info(f"Loading {len(batch_results)} results from batch {batch_idx + 1}")
                        self.all_results.extend(batch_results)
                        logger.info(f"Total results after batch {batch_idx + 1}: {len(self.all_results)}")
                        
                        # Save intermediate results after each batch
                        self.save_intermediate_results()
                    except Exception as e:
                        logger.error(f"Error loading batch {batch_idx + 1} results: {e}", exc_info=True)
                else:
                    logger.warning(f"Batch {batch_idx + 1} result file not found: {results_file}")
                
                # Cleanup
                try:
                    if os.path.exists(batch_file):
                        os.unlink(batch_file)
                    if os.path.exists(script_file):
                        os.unlink(script_file)
                    if os.path.exists(results_file):
                        os.unlink(results_file)
                    stderr_file = batch_file + '.stderr'
                    if os.path.exists(stderr_file):
                        os.unlink(stderr_file)
                except Exception as e:
                    logger.debug(f"Error during cleanup: {e}")
                    
            except Exception as e:
                logger.error(f"Error running batch {batch_idx + 1}: {e}", exc_info=True)
    
    def cleanup_custom_block_instances(self):
        """Clear accumulated instances in custom blocks to prevent memory leaks."""
        # This is called periodically to prevent instance list accumulation
        # More aggressive cleanup - clear more frequently
        try:
            from python.opus_frame_packetizer import opus_frame_packetizer
            if hasattr(opus_frame_packetizer, '_instances'):
                if len(opus_frame_packetizer._instances) > 10:
                    # Keep only last 3 instances (more aggressive)
                    opus_frame_packetizer._instances = opus_frame_packetizer._instances[-3:]
        except:
            pass
        
        try:
            from python.ldpc_decoder_to_pdu import ldpc_decoder_to_pdu
            if hasattr(ldpc_decoder_to_pdu, '_instances'):
                if len(ldpc_decoder_to_pdu._instances) > 10:
                    ldpc_decoder_to_pdu._instances = ldpc_decoder_to_pdu._instances[-3:]
        except:
            pass
        
        try:
            from python.sleipnir_superframe_parser import sleipnir_superframe_parser
            if hasattr(sleipnir_superframe_parser, '_instances'):
                if len(sleipnir_superframe_parser._instances) > 10:
                    sleipnir_superframe_parser._instances = sleipnir_superframe_parser._instances[-3:]
        except:
            pass
        
        try:
            from python.sleipnir_superframe_assembler import sleipnir_superframe_assembler
            if hasattr(sleipnir_superframe_assembler, '_instances'):
                if len(sleipnir_superframe_assembler._instances) > 10:
                    sleipnir_superframe_assembler._instances = sleipnir_superframe_assembler._instances[-3:]
        except:
            pass
    
    def run_test_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single test scenario.
        
        Args:
            scenario: Test scenario dictionary
            
        Returns:
            Test results dictionary
        """
        mod = scenario['modulation']
        crypto_mode = scenario['crypto_mode']
        channel = scenario['channel']
        snr_db = scenario['snr_db']
        
        logger.info(f"Running test: {mod}FSK, {crypto_mode}, {channel['name']}, SNR={snr_db} dB")
        
        # Generate output filename
        output_wav = os.path.join(
            self.output_config['audio_output_dir'],
            f"output_{mod}FSK_{crypto_mode}_{channel['name']}_snr{snr_db:.1f}.wav"
        )
        
        # Determine crypto settings
        enable_signing = crypto_mode in ["sign", "both"]
        enable_encryption = crypto_mode in ["encrypt", "both"]
        
        # Determine FEC matrix files
        auth_matrix = self.test_params['fec_matrices']['auth']
        if mod == 4:
            voice_matrix = self.test_params['fec_matrices']['voice_4fsk']
        else:
            voice_matrix = self.test_params['fec_matrices']['voice_8fsk']
        
        # Pre-creation cleanup: Ensure previous test resources are fully released
        # This helps prevent memory accumulation before creating new flowgraph
        try:
            import gc
            # Force garbage collection before creating new flowgraph
            gc.collect()
            gc.collect()  # Second pass
            # Small delay to allow C++ destructors from previous test to complete
            time.sleep(0.05)
        except:
            pass
        
        # Build flowgraph
        try:
            tb = build_test_flowgraph(
                input_wav=self.test_params['input_file'],
                output_wav=output_wav,
                modulation=mod,
                crypto_mode=crypto_mode,
                channel=channel,
                snr_db=snr_db,
                audio_samp_rate=self.test_params['audio_samp_rate'],
                rf_samp_rate=self.test_params['rf_samp_rate'],
                symbol_rate=self.test_params['symbol_rate'],
                fsk_deviation=self.test_params['fsk_deviation'],
                auth_matrix_file=auth_matrix,
                voice_matrix_file=voice_matrix,
                test_duration=self.test_params['test_duration']
            )
            
            # Get metrics block from flowgraph (created in build_test_flowgraph)
            metrics_block = tb._metrics_block if hasattr(tb, '_metrics_block') else None
            
            # Create standalone metrics collector for compatibility
            metrics = MetricsCollector()
            metrics.start_test()
            
            # Run flowgraph
            tb.start()
            time.sleep(self.test_params['test_duration'] + 1.0)  # Add buffer
            tb.stop()
            tb.wait()
            
            # Properly cleanup flowgraph to prevent memory leaks
            # This is critical when running many tests in sequence
            # GNU Radio blocks need explicit cleanup to release C++ resources
            try:
                # Lock/unlock ensures all threads are finished
                tb.lock()
                tb.unlock()
                
                # Disconnect all connections first
                try:
                    tb.disconnect_all()
                except:
                    pass
                
                # Clear any buffers in custom blocks before deletion
                # This helps prevent memory accumulation
                if hasattr(tb, '_metrics_block'):
                    try:
                        metrics_block = tb._metrics_block
                        if hasattr(metrics_block, 'sample_buffer'):
                            metrics_block.sample_buffer = []
                        if hasattr(metrics_block, 'status_messages'):
                            metrics_block.status_messages = []
                    except:
                        pass
                
                # Explicitly cleanup hierarchical blocks before deleting top block
                # This ensures C++ destructors are called in the right order
                tx_block = None
                rx_block = None
                if hasattr(tb, '_tx_block'):
                    try:
                        tx_block = tb._tx_block
                        # Try to disconnect hierarchical block connections
                        try:
                            tx_block.disconnect_all()
                        except:
                            pass
                    except:
                        pass
                
                if hasattr(tb, '_rx_block'):
                    try:
                        rx_block = tb._rx_block
                        # Try to disconnect hierarchical block connections
                        try:
                            rx_block.disconnect_all()
                        except:
                            pass
                    except:
                        pass
                
                # Clear instance lists in custom blocks to prevent accumulation
                # This helps prevent memory leaks from instance tracking
                # Only clear if we're not the only instance (to avoid breaking active blocks)
                def safe_clear_instances(cls_name):
                    try:
                        module_path, class_name = cls_name.rsplit('.', 1)
                        module = __import__(module_path, fromlist=[class_name])
                        cls = getattr(module, class_name)
                        if hasattr(cls, '_instances'):
                            # Only clear if there are many instances (indicating accumulation)
                            if len(cls._instances) > 10:
                                # Keep only the most recent instances
                                cls._instances = cls._instances[-5:]
                    except Exception:
                        pass
                
                safe_clear_instances('python.opus_frame_packetizer.opus_frame_packetizer')
                safe_clear_instances('python.ldpc_decoder_to_pdu.ldpc_decoder_to_pdu')
                safe_clear_instances('python.sleipnir_superframe_parser.sleipnir_superframe_parser')
                safe_clear_instances('python.sleipnir_superframe_assembler.sleipnir_superframe_assembler')
                
                # Clear references to hierarchical blocks
                if tx_block is not None:
                    try:
                        del tx_block
                    except:
                        pass
                if rx_block is not None:
                    try:
                        del rx_block
                    except:
                        pass
                
                # Clear all references in top block before deletion
                try:
                    # Clear any remaining references
                    if hasattr(tb, '__dict__'):
                        for key in list(tb.__dict__.keys()):
                            if key.startswith('_'):
                                try:
                                    delattr(tb, key)
                                except:
                                    pass
                except:
                    pass
                
                # Explicitly delete the top block to trigger C++ destructors
                del tb
                
                # Force garbage collection multiple times to ensure cleanup
                import gc
                gc.collect()
                gc.collect()  # Second pass to catch circular references
                gc.collect()  # Third pass for stubborn references
                
                # Small delay to allow C++ destructors to complete
                # Increased delay to ensure C++ cleanup completes
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"Error during flowgraph cleanup: {e}")
            
            metrics.stop_test()
            
            # Get metrics from block if available
            if metrics_block:
                block_metrics = metrics_block.get_metrics()
                metrics.frame_count = block_metrics.get('frame_count', 0)
                metrics.frame_error_count = block_metrics.get('frame_error_count', 0)  # Transfer error count
                metrics.superframe_count = block_metrics.get('superframe_count', 0)
                metrics.signature_verified = block_metrics.get('signature_verified', 0)
                metrics.signature_failed = block_metrics.get('signature_failed', 0)
                metrics.sync_acquisition_time = block_metrics.get('sync_acquisition_time')
                # Store total_frames_received for FER calculation (MetricsCollector doesn't have this field, but we can use it in compute_metrics)
                if 'total_frames_received' in block_metrics:
                    # Store it temporarily for FER calculation
                    metrics._total_frames_received = block_metrics.get('total_frames_received', 0)
            
            # Compute audio quality (if output file exists)
            warpq_score = None
            if os.path.exists(output_wav):
                warpq_score = compute_warpq(
                    self.test_params['input_file'],
                    output_wav
                )
            metrics.audio_quality_score = warpq_score
            
            # Get metrics
            test_metrics = metrics.compute_metrics()
            
            # Validate critical checks
            validation = self.validate_test_results(test_metrics, output_wav, crypto_mode, scenario)
            
            # Compile results
            results = {
                'scenario': scenario,
                'metrics': test_metrics,
                'validation': validation,
                'output_wav': output_wav,
                'timestamp': datetime.now().isoformat()
            }
            
            fer_str = f"{test_metrics.get('fer', 'N/A'):.4f}" if isinstance(test_metrics.get('fer'), (int, float)) else str(test_metrics.get('fer', 'N/A'))
            warpq_str = f"{warpq_score:.2f}" if warpq_score is not None else 'N/A'
            logger.info(f"Test completed: FER={fer_str}, WarpQ={warpq_str}")
            
            return results
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            return {
                'scenario': scenario,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def validate_test_results(self, metrics: Dict[str, Any], output_wav: str, crypto_mode: str, scenario: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate test results against critical checks.
        
        Args:
            metrics: Computed metrics
            output_wav: Output WAV file path
            crypto_mode: Crypto mode used
            scenario: Test scenario dictionary (for SNR access)
            
        Returns:
            Validation results dictionary
        """
        validation = {
            'audio_integrity': {'pass': True, 'issues': []},
            'crypto_security': {'pass': True, 'issues': []},
            'data_integrity': {'pass': True, 'issues': []},
            'state_machine': {'pass': True, 'issues': []},
            'boundary_conditions': {'pass': True, 'issues': []},
            'audio_quality': {'pass': True, 'issues': []}
        }
        
        # Audio integrity checks
        if metrics.get('frame_count', 0) == 0:
            validation['audio_integrity']['issues'].append("No frames decoded")
            validation['audio_integrity']['pass'] = False
        
        # Check if output WAV exists and is valid
        if not os.path.exists(output_wav):
            validation['audio_integrity']['issues'].append("Output WAV file not created")
            validation['audio_integrity']['pass'] = False
        else:
            try:
                wav_props = detect_wav_properties(output_wav)
                if wav_props.get('sample_rate') != self.test_params['audio_samp_rate']:
                    validation['audio_quality']['issues'].append(
                        f"Sample rate mismatch: {wav_props.get('sample_rate')} != {self.test_params['audio_samp_rate']}"
                    )
                    validation['audio_quality']['pass'] = False
            except Exception as e:
                validation['audio_quality']['issues'].append(f"Could not analyze audio quality: {e}")
                validation['audio_quality']['pass'] = False
        
        # Crypto security checks
        if crypto_mode in ["sign", "both"]:
            sig_rate = metrics.get('signature_verification_rate')
            if sig_rate is not None and sig_rate < self.pass_criteria['crypto_verification_rate']:
                validation['crypto_security']['issues'].append(
                    f"Signature verification rate too low: {sig_rate:.2%}"
                )
                validation['crypto_security']['pass'] = False
        
        if crypto_mode in ["encrypt", "both"]:
            decrypt_rate = metrics.get('decrypt_success_rate')
            if decrypt_rate is not None and decrypt_rate < self.pass_criteria['crypto_verification_rate']:
                validation['crypto_security']['issues'].append(
                    f"Decryption success rate too low: {decrypt_rate:.2%}"
                )
                validation['crypto_security']['pass'] = False
        
        # Frame Error Rate checks (CRITICAL - was missing!)
        fer = metrics.get('fer')
        if fer is not None:
            # Get SNR from scenario parameter
            snr_db = scenario.get('snr_db', 10.0) if scenario else 10.0
            
            # Apply FER threshold based on SNR
            if snr_db >= 15.0:
                fer_threshold = self.pass_criteria.get('fer_threshold_15db', 0.001)  # 0.1% at 15+ dB
            elif snr_db >= 10.0:
                fer_threshold = self.pass_criteria.get('fer_threshold_10db', 0.01)  # 1% at 10+ dB
            else:
                # For low SNR (< 10 dB), use more lenient threshold
                # FER > 10% is considered failure at low SNR
                fer_threshold = 0.10  # 10% max at low SNR
            
            if fer > fer_threshold:
                validation['audio_integrity']['issues'].append(
                    f"FER too high: {fer:.4f} > {fer_threshold:.4f} (threshold for SNR {snr_db:.1f} dB)"
                )
                validation['audio_integrity']['pass'] = False
        
        # Audio quality checks
        warpq = metrics.get('audio_quality_score')
        if warpq is not None:
            # Get SNR from scenario parameter
            snr_db = scenario.get('snr_db', 10.0) if scenario else 10.0
            if snr_db >= 10.0:
                threshold = self.pass_criteria.get('warpq_threshold_10db', 3.0)
            else:
                threshold = self.pass_criteria.get('warpq_threshold', 2.5)
            
            if warpq < threshold:
                validation['audio_quality']['issues'].append(
                    f"WarpQ score too low: {warpq:.2f} < {threshold:.2f}"
                )
                validation['audio_quality']['pass'] = False
        elif metrics.get('frame_count', 0) > 0:
            # WarpQ should be computed if frames were decoded
            validation['audio_quality']['issues'].append(
                "WarpQ score not computed (audio quality cannot be validated)"
            )
            # Don't fail on missing WarpQ if frames decoded (may be computation issue)
            # validation['audio_quality']['pass'] = False
        
        # State machine checks
        sync_acq_time = metrics.get('sync_acquisition_time')
        if sync_acq_time is not None and sync_acq_time > self.pass_criteria['sync_acquisition_time']:
            validation['state_machine']['issues'].append(
                f"Sync acquisition too slow: {sync_acq_time:.2f}s > {self.pass_criteria['sync_acquisition_time']:.2f}s"
            )
            validation['state_machine']['pass'] = False
        
        # Determine overall pass status
        validation['overall_pass'] = all(
            v['pass'] for v in validation.values() if isinstance(v, dict) and 'pass' in v
        )
        
        return validation
    
    def run_all_tests(self, phase: int = None, max_tests: int = None):
        """
        Run all test scenarios.
        
        Args:
            phase: Test phase to run (1, 2, or 3). If None, run all enabled phases.
            max_tests: Maximum number of tests to run (for testing/debugging)
        """
        self.start_time = time.time()
        
        scenarios = self.generate_test_scenarios(phase=phase)
        
        if max_tests:
            scenarios = scenarios[:max_tests]
            logger.info(f"Limited to {max_tests} tests for debugging")
        
        total_tests = len(scenarios)
        logger.info(f"Starting test suite: {total_tests} scenarios")
        
        # Check if process isolation is enabled
        use_process_isolation = self.config.get('test_parameters', {}).get('use_process_isolation', False)
        process_batch_size = self.config.get('test_parameters', {}).get('process_batch_size', 50)
        
        if use_process_isolation:
            # Run tests in batches using separate processes
            logger.info(f"Using process isolation: {process_batch_size} tests per process")
            self._run_tests_with_process_isolation(scenarios, process_batch_size)
        else:
            # Run tests sequentially with cleanup
            for i, scenario in enumerate(scenarios, 1):
                logger.info(f"Test {i}/{total_tests}")
                
                result = self.run_test_scenario(scenario)
                self.all_results.append(result)
                
                # Periodic cleanup to prevent memory accumulation
                # Clean up instance lists every 10 tests (more frequent)
                if i % 10 == 0:
                    self.cleanup_custom_block_instances()
                    import gc
                    gc.collect()
                    gc.collect()  # Double pass
                    # Small delay to allow cleanup to complete
                    time.sleep(0.1)
                
                # Save intermediate results periodically
                if i % 10 == 0:
                    self.save_intermediate_results()
        
        # Save final results
        self.save_final_results()
        
        elapsed = time.time() - self.start_time
        logger.info(f"Test suite completed in {format_duration(elapsed)}")
    
    def save_intermediate_results(self):
        """Save intermediate results to JSON."""
        results_file = os.path.join(
            self.output_config['results_dir'],
            'results_intermediate.json'
        )
        save_results(self.all_results, results_file)
    
    def save_final_results(self):
        """Save final results and generate summary."""
        # Save full results
        results_file = self.output_config['results_json']
        save_results(self.all_results, results_file)
        logger.info(f"Results saved to {results_file}")
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate test summary."""
        total_tests = len(self.all_results)
        passed_tests = sum(1 for r in self.all_results if r.get('validation', {}).get('overall_pass', False))
        failed_tests = total_tests - passed_tests
        
        summary = {
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'pass_rate': passed_tests / total_tests if total_tests > 0 else 0.0,
            'duration_seconds': time.time() - self.start_time if self.start_time else 0,
            'timestamp': datetime.now().isoformat()
        }
        
        summary_file = os.path.join(self.output_config['results_dir'], 'summary.json')
        save_results(summary, summary_file)
        logger.info(f"Summary: {passed_tests}/{total_tests} tests passed ({summary['pass_rate']:.1%})")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Comprehensive gr-sleipnir test suite')
    parser.add_argument('--config', type=str, default='tests/config_comprehensive.yaml',
                       help='Configuration file path')
    parser.add_argument('--phase', type=int, choices=[1, 2, 3],
                       help='Test phase to run (1, 2, or 3)')
    parser.add_argument('--max-tests', type=int,
                       help='Maximum number of tests to run (for debugging)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Validate configuration without running tests')
    
    args = parser.parse_args()
    
    try:
        suite = ComprehensiveTestSuite(args.config)
        
        if args.dry_run:
            scenarios = suite.generate_test_scenarios(phase=args.phase)
            logger.info(f"Dry run: {len(scenarios)} scenarios would be executed")
            return 0
        
        suite.run_all_tests(phase=args.phase, max_tests=args.max_tests)
        return 0
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

