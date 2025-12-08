#!/usr/bin/env python3
"""
VOX (Voice Operated Exchange) PTT Control Block

Automatic PTT activation based on audio level detection.

Activates PTT when voice is detected, deactivates after silence.
"""

import numpy as np
from gnuradio import gr
import pmt
import math
from typing import Optional


class ptt_vox(gr.sync_block):
    """
    VOX-based PTT control block.
    
    Automatically activates PTT when voice is detected.
    
    Inputs:
    - Port 0: Audio samples (monitored for voice activity)
    
    Outputs:
    - Port 0: Audio samples (passed through)
    - Message Port 'ptt': PTT state messages (PMT bool)
    """
    
    def __init__(
        self,
        threshold_db: float = -30.0,
        attack_ms: int = 50,
        release_ms: int = 500,
        sample_rate: float = 8000.0,
        hang_time_ms: int = 200
    ):
        """
        Initialize VOX PTT block.
        
        Args:
            threshold_db: Voice detection threshold in dB
            attack_ms: Attack time (PTT on delay) in milliseconds
            release_ms: Release time (PTT off delay) in milliseconds
            sample_rate: Audio sample rate
            hang_time_ms: Minimum PTT on time in milliseconds
        """
        gr.sync_block.__init__(
            self,
            name="ptt_vox",
            in_sig=[np.float32],
            out_sig=[np.float32]
        )
        
        self.threshold_db = threshold_db
        self.threshold_linear = 10.0 ** (threshold_db / 20.0)
        self.attack_ms = attack_ms
        self.release_ms = release_ms
        self.sample_rate = sample_rate
        self.hang_time_ms = hang_time_ms
        
        # Calculate samples for timing
        self.attack_samples = int(sample_rate * attack_ms / 1000.0)
        self.release_samples = int(sample_rate * release_ms / 1000.0)
        self.hang_samples = int(sample_rate * hang_time_ms / 1000.0)
        
        # State
        self.ptt_state = False
        self.voice_detected = False
        self.attack_counter = 0
        self.release_counter = 0
        self.hang_counter = 0
        
        # Energy calculation
        self.energy_window = []
        self.window_size = int(sample_rate * 0.02)  # 20ms window
        
        # Message port
        self.message_port_register_out(pmt.intern("ptt"))
    
    def calculate_energy(self, samples: np.ndarray) -> float:
        """Calculate RMS energy of audio samples."""
        if len(samples) == 0:
            return 0.0
        
        # RMS energy
        rms = np.sqrt(np.mean(samples ** 2))
        return rms
    
    def work(self, input_items, output_items):
        """Process samples and detect voice activity."""
        noutput_items = len(output_items[0])
        
        # Calculate energy over window
        self.energy_window.extend(input_items[0][:noutput_items])
        if len(self.energy_window) > self.window_size:
            self.energy_window = self.energy_window[-self.window_size:]
        
        # Calculate current energy
        current_energy = self.calculate_energy(np.array(self.energy_window))
        
        # Detect voice
        voice_active = current_energy > self.threshold_linear
        
        # State machine
        if voice_active:
            # Voice detected
            self.voice_detected = True
            self.release_counter = 0
            
            if not self.ptt_state:
                # Attack phase
                self.attack_counter += noutput_items
                if self.attack_counter >= self.attack_samples:
                    # Activate PTT
                    self.ptt_state = True
                    self.attack_counter = 0
                    self.hang_counter = 0
                    
                    # Emit PTT state message
                    ptt_pmt = pmt.from_bool(True)
                    self.message_port_pub(pmt.intern("ptt"), ptt_pmt)
        else:
            # No voice detected
            if self.ptt_state:
                # Release phase
                self.release_counter += noutput_items
                
                # Check hang time
                if self.hang_counter < self.hang_samples:
                    self.hang_counter += noutput_items
                    self.release_counter = 0  # Reset release counter during hang time
                
                if self.release_counter >= self.release_samples:
                    # Deactivate PTT
                    self.ptt_state = False
                    self.release_counter = 0
                    self.attack_counter = 0
                    self.voice_detected = False
                    
                    # Emit PTT state message
                    ptt_pmt = pmt.from_bool(False)
                    self.message_port_pub(pmt.intern("ptt"), ptt_pmt)
            else:
                # PTT already off
                self.attack_counter = 0
        
        # Pass through audio
        output_items[0][:noutput_items] = input_items[0][:noutput_items]
        
        return noutput_items


def make_ptt_vox(
    threshold_db: float = -30.0,
    attack_ms: int = 50,
    release_ms: int = 500,
    sample_rate: float = 8000.0,
    hang_time_ms: int = 200
):
    """Factory function for GRC."""
    return ptt_vox(
        threshold_db=threshold_db,
        attack_ms=attack_ms,
        release_ms=release_ms,
        sample_rate=sample_rate,
        hang_time_ms=hang_time_ms
    )

