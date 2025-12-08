#!/usr/bin/env python3
"""
Serial PTT Control Block

PTT control via serial port (USB serial adapter, etc.).

Common for USB PTT adapters and serial-controlled radios.
"""

import numpy as np
from gnuradio import gr
import pmt
import serial
import time
from typing import Optional


class ptt_serial(gr.sync_block):
    """
    Serial-based PTT control block.
    
    Controls PTT via serial port commands.
    
    Inputs:
    - Port 0: Audio samples (passed through when PTT active)
    
    Outputs:
    - Port 0: Audio samples (passed through when PTT active)
    - Message Port 'ptt': PTT state messages (PMT bool)
    """
    
    def __init__(
        self,
        serial_port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        ptt_command_on: bytes = b"PTT ON\r\n",
        ptt_command_off: bytes = b"PTT OFF\r\n",
        ptt_delay_ms: int = 50,
        sample_rate: float = 8000.0
    ):
        """
        Initialize serial PTT block.
        
        Args:
            serial_port: Serial port device (e.g., "/dev/ttyUSB0")
            baudrate: Serial baud rate
            ptt_command_on: Command to enable PTT
            ptt_command_off: Command to disable PTT
            ptt_delay_ms: Delay after PTT command (ms)
            sample_rate: Audio sample rate
        """
        gr.sync_block.__init__(
            self,
            name="ptt_serial",
            in_sig=[np.float32],
            out_sig=[np.float32]
        )
        
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.ptt_command_on = ptt_command_on
        self.ptt_command_off = ptt_command_off
        self.ptt_delay_ms = ptt_delay_ms
        self.sample_rate = sample_rate
        
        # State
        self.ptt_state = False
        self.serial_conn = None
        
        # Initialize serial port
        try:
            self.serial_conn = serial.Serial(
                port=serial_port,
                baudrate=baudrate,
                timeout=0.1
            )
            self.serial_available = True
        except Exception as e:
            print(f"Warning: Could not open serial port {serial_port}: {e}")
            self.serial_available = False
        
        # Message port
        self.message_port_register_out(pmt.intern("ptt"))
        
        # Control port for external PTT commands
        self.message_port_register_in(pmt.intern("ctrl"))
        self.set_msg_handler(pmt.intern("ctrl"), self.handle_control)
    
    def handle_control(self, msg):
        """Handle control messages to set PTT state."""
        if pmt.is_bool(msg):
            ptt_state = pmt.to_bool(msg)
            self.set_ptt(ptt_state)
        elif pmt.is_dict(msg):
            if pmt.dict_has_key(msg, pmt.intern("ptt")):
                ptt_state = pmt.to_bool(
                    pmt.dict_ref(msg, pmt.intern("ptt"), pmt.PMT_F)
                )
                self.set_ptt(ptt_state)
    
    def set_ptt(self, state: bool):
        """Set PTT state via serial command."""
        if not self.serial_available or state == self.ptt_state:
            return
        
        self.ptt_state = state
        
        try:
            if state:
                self.serial_conn.write(self.ptt_command_on)
            else:
                self.serial_conn.write(self.ptt_command_off)
            
            # Wait for command to take effect
            time.sleep(self.ptt_delay_ms / 1000.0)
            
            # Emit PTT state message
            ptt_pmt = pmt.from_bool(self.ptt_state)
            self.message_port_pub(pmt.intern("ptt"), ptt_pmt)
            
        except Exception as e:
            print(f"Error sending PTT command: {e}")
    
    def work(self, input_items, output_items):
        """Process samples."""
        noutput_items = len(output_items[0])
        
        # Pass through audio when PTT is active
        if self.ptt_state:
            output_items[0][:noutput_items] = input_items[0][:noutput_items]
        else:
            # Output silence when PTT inactive
            output_items[0][:noutput_items] = 0.0
        
        return noutput_items
    
    def __del__(self):
        """Cleanup serial port."""
        if self.serial_conn:
            try:
                # Turn off PTT before closing
                if self.ptt_state:
                    self.serial_conn.write(self.ptt_command_off)
                self.serial_conn.close()
            except:
                pass


def make_ptt_serial(
    serial_port: str = "/dev/ttyUSB0",
    baudrate: int = 9600,
    ptt_command_on: bytes = b"PTT ON\r\n",
    ptt_command_off: bytes = b"PTT OFF\r\n",
    ptt_delay_ms: int = 50,
    sample_rate: float = 8000.0
):
    """Factory function for GRC."""
    return ptt_serial(
        serial_port=serial_port,
        baudrate=baudrate,
        ptt_command_on=ptt_command_on,
        ptt_command_off=ptt_command_off,
        ptt_delay_ms=ptt_delay_ms,
        sample_rate=sample_rate
    )

