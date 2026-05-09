#!/usr/bin/env python3
"""
Network PTT Control Block

PTT control via network (TCP/IP or UDP).

Alternative to ZMQ for PTT control.
"""

import numpy as np
from gnuradio import gr
import pmt
import socket
import threading
import json
from typing import Optional


class ptt_network(gr.sync_block):
    """
    Network-based PTT control block.

    Controls PTT via TCP/IP or UDP network commands.

    Inputs:
    - Port 0: Audio samples (passed through when PTT active)

    Outputs:
    - Port 0: Audio samples (passed through when PTT active)
    - Message Port 'ptt': PTT state messages (PMT bool)
    """

    def __init__(
        self,
        listen_address: str = "0.0.0.0",
        listen_port: int = 5558,
        protocol: str = "TCP",
        sample_rate: float = 8000.0
    ):
        """
        Initialize network PTT block.

        Args:
            listen_address: Address to listen on ("0.0.0.0" for all interfaces)
            listen_port: Port to listen on
            protocol: "TCP" or "UDP"
            sample_rate: Audio sample rate
        """
        gr.sync_block.__init__(
            self,
            name="ptt_network",
            in_sig=[np.float32],
            out_sig=[np.float32]
        )

        self.listen_address = listen_address
        self.listen_port = listen_port
        self.protocol = protocol.upper()
        self.sample_rate = sample_rate

        # State
        self.ptt_state = False
        self.socket = None
        self.running = False
        self.server_thread = None

        # Lock for thread safety
        self.lock = threading.Lock()

        # Initialize network server
        try:
            if self.protocol == "TCP":
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.bind((listen_address, listen_port))
                self.socket.listen(5)
            else:  # UDP
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket.bind((listen_address, listen_port))

            self.network_available = True
            self.running = True

            # Start server thread
            self.server_thread = threading.Thread(target=self.server_loop, daemon=True)
            self.server_thread.start()

        except Exception as e:
            print(f"Warning: Could not start network server: {e}")
            self.network_available = False

        # Message port
        self.message_port_register_out(pmt.intern("ptt"))

        # Control port for local PTT commands
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
        """Set PTT state."""
        with self.lock:
            if state != self.ptt_state:
                self.ptt_state = state

                # Emit PTT state message
                ptt_pmt = pmt.from_bool(self.ptt_state)
                self.message_port_pub(pmt.intern("ptt"), ptt_pmt)

    def server_loop(self):
        """Network server loop (runs in separate thread)."""
        if not self.network_available:
            return

        if self.protocol == "TCP":
            self.tcp_server_loop()
        else:
            self.udp_server_loop()

    def tcp_server_loop(self):
        """TCP server loop."""
        while self.running:
            try:
                client_socket, address = self.socket.accept()
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self.handle_tcp_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                if self.running:
                    print(f"Error accepting TCP connection: {e}")

    def handle_tcp_client(self, client_socket, address):
        """Handle TCP client connection."""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break

                self.process_command(data.decode('utf-8', errors='ignore'))
        except Exception as e:
            if self.running:
                print(f"Error handling TCP client: {e}")
        finally:
            client_socket.close()

    def udp_server_loop(self):
        """UDP server loop."""
        while self.running:
            try:
                data, address = self.socket.recvfrom(1024)
                self.process_command(data.decode('utf-8', errors='ignore'))
            except Exception as e:
                if self.running:
                    print(f"Error receiving UDP packet: {e}")

    def process_command(self, command: str):
        """Process network command."""
        try:
            # Try JSON format
            cmd_dict = json.loads(command)
            if 'ptt' in cmd_dict:
                self.set_ptt(bool(cmd_dict['ptt']))
            elif 'command' in cmd_dict:
                cmd = cmd_dict['command'].upper()
                if cmd == 'PTT_ON' or cmd == 'TX_ON':
                    self.set_ptt(True)
                elif cmd == 'PTT_OFF' or cmd == 'TX_OFF':
                    self.set_ptt(False)
        except json.JSONDecodeError:
            # Try plain text format
            command = command.strip().upper()
            if command == 'PTT ON' or command == 'TX ON':
                self.set_ptt(True)
            elif command == 'PTT OFF' or command == 'TX OFF':
                self.set_ptt(False)

    def work(self, input_items, output_items):
        """Process samples."""
        noutput_items = len(output_items[0])

        # Pass through audio when PTT is active
        with self.lock:
            ptt_active = self.ptt_state

        if ptt_active:
            output_items[0][:noutput_items] = input_items[0][:noutput_items]
        else:
            # Output silence when PTT inactive
            output_items[0][:noutput_items] = 0.0

        return noutput_items

    def __del__(self):
        """Cleanup network server."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass


def make_ptt_network(
    listen_address: str = "0.0.0.0",
    listen_port: int = 5558,
    protocol: str = "TCP",
    sample_rate: float = 8000.0
):
    """Factory function for GRC."""
    return ptt_network(
        listen_address=listen_address,
        listen_port=listen_port,
        protocol=protocol,
        sample_rate=sample_rate
    )

