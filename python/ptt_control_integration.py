#!/usr/bin/env python3
"""
PTT Control Integration Helper

Helper functions to integrate PTT blocks with TX/RX modules.
"""

import pmt


def connect_ptt_to_tx(ptt_block, tx_block):
    """
    Connect PTT block to TX block.

    Args:
        ptt_block: PTT control block (any PTT type)
        tx_block: TX block (sleipnir_tx_hier or similar)
    """
    # Connect PTT state messages to TX control
    ptt_block.message_port_register_out("ptt")
    tx_block.message_port_register_hier_in("ptt")

    # Connect message ports
    # In GRC, this would be done via message port connections
    # In Python, use msg_connect:
    # ptt_block.msg_connect(ptt_block, "ptt", tx_block, "ptt")


def create_ptt_handler(ptt_type: str, **kwargs) -> object:
    """
    Create PTT block based on type.

    Args:
        ptt_type: Type of PTT ('gpio', 'serial', 'vox', 'network', 'zmq')
        **kwargs: Arguments for specific PTT type

    Returns:
        PTT block instance
    """
    if ptt_type.lower() == 'gpio':
        from python.ptt_gpio import make_ptt_gpio
        return make_ptt_gpio(**kwargs)

    elif ptt_type.lower() == 'serial':
        from python.ptt_serial import make_ptt_serial
        return make_ptt_serial(**kwargs)

    elif ptt_type.lower() == 'vox':
        from python.ptt_vox import make_ptt_vox
        return make_ptt_vox(**kwargs)

    elif ptt_type.lower() == 'network':
        from python.ptt_network import make_ptt_network
        return make_ptt_network(**kwargs)

    elif ptt_type.lower() == 'zmq':
        # ZMQ PTT uses existing ZMQ control infrastructure
        from python.zmq_control_helper import SleipnirControlClient
        return SleipnirControlClient(**kwargs)

    else:
        raise ValueError(f"Unknown PTT type: {ptt_type}")


def ptt_state_to_control_msg(ptt_state: bool):
    """
    Convert PTT state to control message for TX block.

    Args:
        ptt_state: True for PTT on, False for PTT off

    Returns:
        PMT dictionary with PTT control
    """
    ctrl_msg = pmt.make_dict()
    ctrl_msg = pmt.dict_add(ctrl_msg, pmt.intern("ptt"), pmt.from_bool(ptt_state))
    return ctrl_msg

