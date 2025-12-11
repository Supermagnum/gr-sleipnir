#!/usr/bin/env python3
"""
Metrics Collector for gr-sleipnir Test Suite

Collects and aggregates metrics from test runs.
"""

import logging
import time
import numpy as np
from typing import Dict, List, Optional, Any
import pmt
from collections import defaultdict
from gnuradio import gr

logger = logging.getLogger(__name__)


class MetricsCollectorBlock(gr.sync_block):
    """
    GNU Radio block that collects metrics from status messages.
    
    This block passes through audio while collecting metrics from status messages.
    """
    
    # Class-level storage to work around GNU Radio gateway issues
    _instances = {}  # Store metrics by instance ID
    
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="metrics_collector_block",
            in_sig=[np.float32],
            out_sig=[np.float32]
        )
        
        # Store instance ID for class-level storage
        self._instance_id = id(self)
        
        # Initialize metrics in class-level storage (work around GNU Radio gateway issues)
        MetricsCollectorBlock._instances[self._instance_id] = {
            'frame_count': 0,
            'frame_error_count': 0,
            'total_frames_received': 0,
            'superframe_count': 0,
            'signature_verified': 0,
            'signature_failed': 0,
            'decrypt_success': 0,
            'decrypt_failed': 0,
            'sync_acquisition_time': None,
            'sync_state': 'searching',
            'sync_start_time': time.time(),
            'status_messages': []
        }
        
        # Also set instance attributes for compatibility
        self.frame_count = 0
        self.frame_error_count = 0
        self.total_frames_received = 0
        self.superframe_count = 0
        self.signature_verified = 0
        self.signature_failed = 0
        self.decrypt_success = 0
        self.decrypt_failed = 0
        self.sync_acquisition_time = None
        self.sync_state = "searching"
        self.sync_start_time = time.time()
        self.status_messages = []
        
        # Register message input port for status messages
        self.message_port_register_in(pmt.intern("status"))
        self.set_msg_handler(pmt.intern("status"), self.handle_status_message)
    
    def handle_status_message(self, msg):
        """Handle status message from RX block."""
        # Track that we received a message
        instance_id = getattr(self, '_instance_id', id(self))
        if instance_id not in MetricsCollectorBlock._instances:
            MetricsCollectorBlock._instances[instance_id] = {
                'frame_count': 0,
                'frame_error_count': 0,
                'total_frames_received': 0,
                'superframe_count': 0,
                'signature_verified': 0,
                'signature_failed': 0,
                'decrypt_success': 0,
                'decrypt_failed': 0,
                'status_messages': []
            }
        MetricsCollectorBlock._instances[instance_id].setdefault('status_messages', []).append(msg)
        
        try:
            # GNU Radio messages from hierarchical blocks are wrapped as pairs (cons)
            # Convert to Python to extract the dict from the car (first element)
            try:
                msg_python = pmt.to_python(msg)
                
                # If it's a tuple, it's a pair - the dict is in the car (first element)
                if isinstance(msg_python, tuple) and len(msg_python) >= 1:
                    car_python = msg_python[0]
                    if isinstance(car_python, dict):
                        msg_dict = car_python
                    else:
                        # Try converting car back to PMT and then to Python dict
                        try:
                            car_pmt = pmt.to_pmt(car_python) if not isinstance(car_python, dict) else None
                            if car_pmt and pmt.is_dict(car_pmt):
                                msg_dict = pmt.to_python(car_pmt)
                            else:
                                msg_dict = None
                        except:
                            msg_dict = None
                elif isinstance(msg_python, dict):
                    msg_dict = msg_python
                else:
                    msg_dict = None
                
                if isinstance(msg_dict, dict):
                    # Get instance storage
                    instance_id = getattr(self, '_instance_id', id(self))
                    if instance_id not in MetricsCollectorBlock._instances:
                        # Initialize if not found
                        MetricsCollectorBlock._instances[instance_id] = {
                            'frame_count': 0,
                            'frame_error_count': 0,
                            'total_frames_received': 0,
                            'superframe_count': 0,
                            'signature_verified': 0,
                            'signature_failed': 0,
                            'decrypt_success': 0,
                            'decrypt_failed': 0,
                            'status_messages': []
                        }
                    storage = MetricsCollectorBlock._instances[instance_id]
                    
                    # Extract all metrics from dict
                    frame_counter = msg_dict.get('frame_counter', 0)
                    if frame_counter:
                        old_count = storage.get('frame_count', 0)
                        new_count = old_count + frame_counter
                        storage['frame_count'] = new_count
                        MetricsCollectorBlock._instances[instance_id] = storage
                    
                    total_frames_received = msg_dict.get('total_frames_received', 0)
                    if total_frames_received:
                        current_total = storage.get('total_frames_received', 0)
                        new_total = max(current_total, total_frames_received)
                        storage['total_frames_received'] = new_total
                        MetricsCollectorBlock._instances[instance_id] = storage
                    
                    frame_error_count = msg_dict.get('frame_error_count', 0)
                    if frame_error_count:
                        current_errors = storage.get('frame_error_count', 0)
                        storage['frame_error_count'] = max(current_errors, frame_error_count)
                        MetricsCollectorBlock._instances[instance_id] = storage
                    
                    superframe_counter = msg_dict.get('superframe_counter', 0)
                    if superframe_counter is not None:
                        current_superframe = storage.get('superframe_count', 0)
                        storage['superframe_count'] = max(current_superframe, superframe_counter + 1)
                        MetricsCollectorBlock._instances[instance_id] = storage
                    
                    # Also update instance attributes for compatibility
                    self.frame_count = storage.get('frame_count', 0)
                    self.total_frames_received = storage.get('total_frames_received', 0)
                    self.frame_error_count = storage.get('frame_error_count', 0)
                    self.superframe_count = storage.get('superframe_count', 0)
                    
                    # Extract signature validity (only if present in message)
                    if 'signature_valid' in msg_dict:
                        sig_valid = msg_dict.get('signature_valid', False)
                        if sig_valid:
                            storage['signature_verified'] = storage.get('signature_verified', 0) + 1
                        else:
                            storage['signature_failed'] = storage.get('signature_failed', 0) + 1
                        MetricsCollectorBlock._instances[instance_id] = storage
                    
                    # Extract sync state
                    sync_state = msg_dict.get('sync_state', '')
                    current_sync_state = storage.get('sync_state', 'searching')
                    if sync_state and sync_state != current_sync_state:
                        storage['sync_state'] = sync_state
                        if sync_state == "synced" and storage.get('sync_acquisition_time') is None:
                            sync_start = storage.get('sync_start_time', time.time())
                            storage['sync_acquisition_time'] = time.time() - sync_start
                    
                    # Update storage
                    MetricsCollectorBlock._instances[instance_id] = storage
                    
                    return  # Successfully extracted
            except Exception as e:
                logger.warning(f"Error converting message to Python: {e}")
            
            # Fallback: Try PMT dict access
            if pmt.is_pair(msg):
                msg = pmt.car(msg)
            
            # Try accessing dict keys directly - don't check is_dict() first
            # PMT dicts might not pass is_dict() but still support dict operations
            # Just try to access the keys we need
            
            # Try Python conversion first
            try:
                msg_python = pmt.to_python(msg)
                print(f"MetricsCollector: Python conversion successful, type: {type(msg_python)}")
                
                # If it's a tuple (pair), check all elements
                if isinstance(msg_python, tuple):
                    print(f"MetricsCollector: Tuple length: {len(msg_python)}, elements: {[type(x).__name__ for x in msg_python[:3]]}")
                    # Try each element to find the dict
                    msg_dict = None
                    for i, elem in enumerate(msg_python):
                        if isinstance(elem, dict):
                            msg_dict = elem
                            print(f"MetricsCollector: Found dict at index {i}")
                            break
                        elif hasattr(elem, 'keys') or hasattr(elem, 'get'):
                            # Might be a dict-like object
                            try:
                                test_keys = list(elem.keys())[:5] if hasattr(elem, 'keys') else []
                                if 'frame_counter' in test_keys or 'total_frames_received' in test_keys:
                                    msg_dict = elem
                                    print(f"MetricsCollector: Found dict-like at index {i}")
                                    break
                            except:
                                pass
                elif isinstance(msg_python, dict):
                    msg_dict = msg_python
                else:
                    msg_dict = None
                
                if isinstance(msg_dict, dict):
                    print(f"MetricsCollector: It's a dict! Keys: {list(msg_dict.keys())[:10]}")
                    frame_counter = msg_dict.get('frame_counter', 0)
                    if frame_counter:
                        self.frame_count += frame_counter
                        print(f"MetricsCollector: Extracted frame_counter={frame_counter}, total={self.frame_count}")
                    
                    total_frames_received = msg_dict.get('total_frames_received', 0)
                    if total_frames_received:
                        current_total = getattr(self, 'total_frames_received', 0)
                        self.total_frames_received = max(current_total, total_frames_received)
                        print(f"MetricsCollector: Extracted total_frames_received={total_frames_received}, total={self.total_frames_received}")
                    
                    frame_error_count = msg_dict.get('frame_error_count', 0)
                    if frame_error_count:
                        current_errors = getattr(self, 'frame_error_count', 0)
                        self.frame_error_count = max(current_errors, frame_error_count)
                        print(f"MetricsCollector: Extracted frame_error_count={frame_error_count}, total={self.frame_error_count}")
                    
                    superframe_counter = msg_dict.get('superframe_counter', 0)
                    if superframe_counter is not None:
                        self.superframe_count = max(self.superframe_count, superframe_counter + 1)
                    
                    return  # Successfully extracted
            except Exception as e:
                logger.warning(f"Error converting message to Python: {e}")
            
        except Exception as e:
            logger.warning(f"Error handling status message: {e}")
    
    def work(self, input_items, output_items):
        """Pass through audio samples."""
        noutput = len(output_items[0])
        output_items[0][:noutput] = input_items[0][:noutput]
        return noutput
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        # Get instance storage (work around GNU Radio gateway issues)
        instance_id = getattr(self, '_instance_id', id(self))
        
        storage = MetricsCollectorBlock._instances.get(instance_id, {})
        
        # If not found or empty, find the instance with the most metrics (likely the active one)
        # This handles the case where GNU Radio creates multiple instances
        if not storage or storage.get('frame_count', 0) == 0:
            # Find instance with highest frame_count
            best_instance_id = None
            best_frame_count = 0
            for inst_id, inst_storage in MetricsCollectorBlock._instances.items():
                frame_count = inst_storage.get('frame_count', 0)
                if frame_count > best_frame_count:
                    best_frame_count = frame_count
                    best_instance_id = inst_id
            
            if best_instance_id:
                storage = MetricsCollectorBlock._instances[best_instance_id]
                instance_id = best_instance_id
            elif MetricsCollectorBlock._instances:
                # Fallback: use first available
                first_instance_id = list(MetricsCollectorBlock._instances.keys())[0]
                storage = MetricsCollectorBlock._instances[first_instance_id]
                instance_id = first_instance_id
        
        # Extract metrics from storage
        frame_count = storage.get('frame_count', 0)
        frame_error_count = storage.get('frame_error_count', 0)
        superframe_count = storage.get('superframe_count', 0)
        total_frames_received = storage.get('total_frames_received', 0)
        
        # Return metrics from class-level storage
        return {
            'frame_count': frame_count,
            'frame_error_count': frame_error_count,
            'total_frames_received': total_frames_received,
            'superframe_count': superframe_count,
            'signature_verified': storage.get('signature_verified', 0),
            'signature_failed': storage.get('signature_failed', 0),
            'decrypt_success': storage.get('decrypt_success', 0),
            'decrypt_failed': storage.get('decrypt_failed', 0),
            'sync_acquisition_time': storage.get('sync_acquisition_time', None),
            'sync_state': storage.get('sync_state', 'searching')
        }
        


class MetricsCollector:
    """Collect metrics from test execution."""
    
    def __init__(self):
        """Initialize metrics collector."""
        # Protocol metrics
        self.frame_count = 0
        self.frame_error_count = 0
        self.bit_error_count = 0
        self.total_bits = 0
        self.superframe_count = 0
        self.superframe_error_count = 0
        
        # LDPC decoder metrics
        self.ldpc_iterations = []
        self.ldpc_converged = 0
        self.ldpc_failed = 0
        
        # Crypto metrics
        self.signature_verified = 0
        self.signature_failed = 0
        self.signature_rejected = 0
        self.decrypt_success = 0
        self.decrypt_failed = 0
        self.mac_verified = 0
        self.mac_failed = 0
        
        # Sync metrics
        self.sync_acquisition_time = None
        self.sync_state_transitions = []
        self.sync_loss_count = 0
        self.sync_recovery_times = []
        self.sync_state = "searching"
        self.sync_start_time = None
        
        # APRS/Text metrics
        self.aprs_packets_received = 0
        self.aprs_packets_corrupted = 0
        self.text_messages_received = 0
        self.text_messages_corrupted = 0
        
        # Processing metrics
        self.start_time = None
        self.end_time = None
        self.processing_times = []
        
        # Audio quality metrics (computed post-test)
        self.audio_quality_score = None
        self.audio_snr_db = None
        
        # Status message handler
        self.status_messages = []
    
    def start_test(self):
        """Mark test start."""
        self.start_time = time.time()
        self.sync_start_time = time.time()
    
    def stop_test(self):
        """Mark test end."""
        self.end_time = time.time()
    
    def handle_status_message(self, msg):
        """
        Handle status message from RX block.
        
        Args:
            msg: PMT message
        """
        try:
            if not pmt.is_dict(msg):
                return
            
            status = {}
            
            # Extract frame counter - try direct access without dict_has_key
            try:
                frame_counter_pmt = pmt.dict_ref(msg, pmt.intern("frame_counter"), pmt.PMT_NIL)
                if frame_counter_pmt != pmt.PMT_NIL:
                    frame_counter = pmt.to_long(frame_counter_pmt)
                    print(f"MetricsCollector: Extracted frame_counter={frame_counter}, current count={self.frame_count}")
                    self.frame_count += frame_counter
                    print(f"MetricsCollector: Updated frame_count={self.frame_count}")
            except Exception as e:
                print(f"MetricsCollector: Error extracting frame_counter: {e}")
                # Try alternative: convert to Python dict first
                try:
                    msg_dict = pmt.to_python(msg)
                    if isinstance(msg_dict, dict):
                        frame_counter = msg_dict.get('frame_counter', 0)
                        if frame_counter:
                            self.frame_count += frame_counter
                            print(f"MetricsCollector: Extracted from Python dict: frame_counter={frame_counter}")
                except:
                    pass
            
            # Extract signature validity
            if pmt.dict_has_key(msg, pmt.intern("signature_valid")):
                sig_valid = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("signature_valid"), pmt.PMT_F)
                )
                if sig_valid:
                    self.signature_verified += 1
                else:
                    self.signature_failed += 1
            
            # Extract decryption success
            if pmt.dict_has_key(msg, pmt.intern("decrypted_successfully")):
                decrypt_success = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("decrypted_successfully"), pmt.PMT_F)
                )
                if decrypt_success:
                    self.decrypt_success += 1
                else:
                    # Only count as failed if encryption was expected
                    # Check if encrypted flag is present and True
                    if pmt.dict_has_key(msg, pmt.intern("encrypted")):
                        encrypted = pmt.to_bool(
                            pmt.dict_ref(msg, pmt.intern("encrypted"), pmt.PMT_F)
                        )
                        if encrypted:
                            self.decrypt_failed += 1
            
            # Extract sync state
            if pmt.dict_has_key(msg, pmt.intern("sync_state")):
                sync_state = pmt.symbol_to_string(
                    pmt.dict_ref(msg, pmt.intern("sync_state"), pmt.PMT_NIL)
                )
                if sync_state != self.sync_state:
                    self.sync_state_transitions.append({
                        'from': self.sync_state,
                        'to': sync_state,
                        'time': time.time() - (self.sync_start_time or self.start_time)
                    })
                    self.sync_state = sync_state
                    
                    # Track sync acquisition
                    if sync_state == "synced" and self.sync_acquisition_time is None:
                        self.sync_acquisition_time = time.time() - (self.sync_start_time or self.start_time)
                    
                    # Track sync loss
                    if sync_state == "lost":
                        self.sync_loss_count += 1
            
            # Extract superframe counter
            if pmt.dict_has_key(msg, pmt.intern("superframe_counter")):
                superframe_counter = pmt.to_long(
                    pmt.dict_ref(msg, pmt.intern("superframe_counter"), pmt.PMT_NIL)
                )
                self.superframe_count = max(self.superframe_count, superframe_counter + 1)
            
            # Store status message
            self.status_messages.append(status)
            
        except Exception as e:
            logger.warning(f"Error handling status message: {e}")
    
    def compute_metrics(self) -> Dict[str, Any]:
        """
        Compute final metrics.
        
        Returns:
            Dictionary of computed metrics
        """
        metrics = {}
        
        # Frame Error Rate
        # FER = frame_error_count / total_frames_received
        # Use total_frames_received if available (more accurate), otherwise fall back to frame_count + frame_error_count
        total_frames_received = getattr(self, '_total_frames_received', None)
        if total_frames_received is not None and total_frames_received > 0:
            metrics['fer'] = self.frame_error_count / total_frames_received
            metrics['total_frames_received'] = total_frames_received
        elif total_frames_received == 0:
            # No frames received at all
            metrics['fer'] = 1.0  # 100% error (no frames decoded)
            metrics['total_frames_received'] = 0
        else:
            # Fallback: use frame_count + frame_error_count
            total_frames = self.frame_count + self.frame_error_count
            if total_frames > 0:
                metrics['fer'] = self.frame_error_count / total_frames
            else:
                metrics['fer'] = 1.0  # No frames received = 100% error
            # Set total_frames_received to the calculated value for consistency
            metrics['total_frames_received'] = total_frames if total_frames > 0 else 0
        
        # Bit Error Rate
        if self.total_bits > 0:
            metrics['ber'] = self.bit_error_count / self.total_bits
        else:
            metrics['ber'] = None
        
        # Superframe Error Rate
        if self.superframe_count > 0:
            metrics['superframe_fer'] = self.superframe_error_count / self.superframe_count
        else:
            metrics['superframe_fer'] = 1.0
        
        # LDPC decoder statistics
        if self.ldpc_iterations:
            metrics['ldpc_mean_iterations'] = np.mean(self.ldpc_iterations)
            metrics['ldpc_max_iterations'] = np.max(self.ldpc_iterations)
            metrics['ldpc_convergence_rate'] = self.ldpc_converged / (self.ldpc_converged + self.ldpc_failed) if (self.ldpc_converged + self.ldpc_failed) > 0 else 0.0
        else:
            metrics['ldpc_mean_iterations'] = None
            metrics['ldpc_max_iterations'] = None
            metrics['ldpc_convergence_rate'] = None
        
        # Crypto statistics
        total_signatures = self.signature_verified + self.signature_failed
        if total_signatures > 0:
            metrics['signature_verification_rate'] = self.signature_verified / total_signatures
        else:
            metrics['signature_verification_rate'] = None
        
        total_decrypts = self.decrypt_success + self.decrypt_failed
        if total_decrypts > 0:
            metrics['decrypt_success_rate'] = self.decrypt_success / total_decrypts
        else:
            metrics['decrypt_success_rate'] = None
        
        total_macs = self.mac_verified + self.mac_failed
        if total_macs > 0:
            metrics['mac_verification_rate'] = self.mac_verified / total_macs
        else:
            metrics['mac_verification_rate'] = None
        
        # Sync statistics
        metrics['sync_acquisition_time'] = self.sync_acquisition_time
        metrics['sync_loss_count'] = self.sync_loss_count
        if self.sync_recovery_times:
            metrics['sync_recovery_time_mean'] = np.mean(self.sync_recovery_times)
            metrics['sync_recovery_time_max'] = np.max(self.sync_recovery_times)
        else:
            metrics['sync_recovery_time_mean'] = None
            metrics['sync_recovery_time_max'] = None
        
        # APRS/Text statistics
        metrics['aprs_packets_received'] = self.aprs_packets_received
        metrics['aprs_packets_corrupted'] = self.aprs_packets_corrupted
        metrics['text_messages_received'] = self.text_messages_received
        metrics['text_messages_corrupted'] = self.text_messages_corrupted
        
        # Processing statistics
        if self.start_time and self.end_time:
            metrics['total_processing_time'] = self.end_time - self.start_time
        if self.processing_times:
            metrics['mean_processing_time_per_frame'] = np.mean(self.processing_times)
        
        # Audio quality (set externally)
        metrics['audio_quality_score'] = self.audio_quality_score
        metrics['audio_snr_db'] = self.audio_snr_db
        
        # Raw counts
        metrics['frame_count'] = self.frame_count
        metrics['frame_error_count'] = self.frame_error_count
        metrics['superframe_count'] = self.superframe_count
        metrics['superframe_error_count'] = self.superframe_error_count
        
        return metrics
    
    def reset(self):
        """Reset all metrics."""
        self.__init__()

