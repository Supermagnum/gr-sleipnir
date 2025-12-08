#!/usr/bin/env python3
"""
GPIO PTT Control Block

Hardware PTT control via GPIO pins (e.g., Raspberry Pi).

Controls TX enable/disable based on GPIO pin state.
"""

import numpy as np
from gnuradio import gr
import pmt
import time
from typing import Optional

# Try to import GPIO library
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    try:
        import gpiod
        GPIO_AVAILABLE = True
        GPIO_LIB = 'gpiod'
    except ImportError:
        GPIO_AVAILABLE = False
        GPIO_LIB = None


class ptt_gpio(gr.sync_block):
    """
    GPIO-based PTT control block.

    Monitors GPIO pin for PTT state and controls TX block accordingly.

    Inputs:
    - Port 0: Audio samples (passed through when PTT active)

    Outputs:
    - Port 0: Audio samples (passed through when PTT active)
    - Message Port 'ptt': PTT state messages (PMT bool)
    """

    def __init__(
        self,
        gpio_pin: int = 18,
        active_low: bool = True,
        sample_rate: float = 8000.0,
        debounce_ms: int = 50
    ):
        """
        Initialize GPIO PTT block.

        Args:
            gpio_pin: GPIO pin number (BCM numbering for RPi)
            active_low: True if PTT is active low (default)
            sample_rate: Audio sample rate (for timing)
            debounce_ms: Debounce time in milliseconds
        """
        gr.sync_block.__init__(
            self,
            name="ptt_gpio",
            in_sig=[np.float32],
            out_sig=[np.float32]
        )

        self.gpio_pin = gpio_pin
        self.active_low = active_low
        self.sample_rate = sample_rate
        self.debounce_ms = debounce_ms
        self.debounce_samples = int(sample_rate * debounce_ms / 1000.0)

        # State
        self.ptt_state = False
        self.last_state = False
        self.debounce_counter = 0

        # Initialize GPIO
        if GPIO_AVAILABLE:
            try:
                if GPIO_LIB == 'gpiod':
                    # Use libgpiod (newer method)
                    self.chip = gpiod.Chip('gpiochip0')
                    self.line = self.chip.get_line(gpio_pin)
                    self.line.request(consumer='gr-sleipnir', type=gpiod.LINE_REQ_DIR_IN)
                else:
                    # Use RPi.GPIO
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP if active_low else GPIO.PUD_DOWN)
            except Exception as e:
                print(f"Warning: Could not initialize GPIO: {e}")
                GPIO_AVAILABLE = False

        # Message port
        self.message_port_register_out(pmt.intern("ptt"))

        # PTT state tracking
        self.ptt_active = False

    def read_gpio(self) -> bool:
        """Read GPIO pin state."""
        if not GPIO_AVAILABLE:
            return False

        try:
            if GPIO_LIB == 'gpiod':
                value = self.line.get_value()
            else:
                value = GPIO.input(self.gpio_pin)

            # Invert if active low
            if self.active_low:
                return value == 0
            else:
                return value == 1
        except Exception as e:
            print(f"Error reading GPIO: {e}")
            return False

    def work(self, input_items, output_items):
        """Process samples and monitor PTT state."""
        noutput_items = len(output_items[0])

        # Read GPIO state
        current_state = self.read_gpio()

        # Debounce
        if current_state != self.last_state:
            self.debounce_counter = 0
        else:
            self.debounce_counter += noutput_items

        # Update state after debounce
        if self.debounce_counter >= self.debounce_samples:
            if current_state != self.ptt_state:
                self.ptt_state = current_state
                self.ptt_active = current_state

                # Emit PTT state message
                ptt_pmt = pmt.from_bool(self.ptt_state)
                self.message_port_pub(pmt.intern("ptt"), ptt_pmt)

        self.last_state = current_state

        # Pass through audio when PTT is active
        if self.ptt_state:
            output_items[0][:noutput_items] = input_items[0][:noutput_items]
        else:
            # Output silence when PTT inactive
            output_items[0][:noutput_items] = 0.0

        return noutput_items

    def __del__(self):
        """Cleanup GPIO on destruction."""
        if GPIO_AVAILABLE:
            try:
                if GPIO_LIB == 'gpiod':
                    self.line.release()
                    self.chip.close()
                else:
                    GPIO.cleanup(self.gpio_pin)
            except:
                pass


def make_ptt_gpio(
    gpio_pin: int = 18,
    active_low: bool = True,
    sample_rate: float = 8000.0,
    debounce_ms: int = 50
):
    """Factory function for GRC."""
    return ptt_gpio(
        gpio_pin=gpio_pin,
        active_low=active_low,
        sample_rate=sample_rate,
        debounce_ms=debounce_ms
    )

