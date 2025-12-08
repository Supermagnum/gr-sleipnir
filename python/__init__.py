# gr-sleipnir Python module

# Export hierarchical blocks for GRC
try:
    from .sleipnir_tx_hier import sleipnir_tx_hier, make_sleipnir_tx_hier
except ImportError:
    # Fallback for direct import
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from python.sleipnir_tx_hier import sleipnir_tx_hier, make_sleipnir_tx_hier

try:
    from .sleipnir_rx_hier import sleipnir_rx_hier, make_sleipnir_rx_hier
except ImportError:
    from python.sleipnir_rx_hier import sleipnir_rx_hier, make_sleipnir_rx_hier

# Export main blocks
try:
    from .sleipnir_tx_block import sleipnir_tx_block, make_sleipnir_tx_block
    from .sleipnir_rx_block import sleipnir_rx_block, make_sleipnir_rx_block
except ImportError:
    from python.sleipnir_tx_block import sleipnir_tx_block, make_sleipnir_tx_block
    from python.sleipnir_rx_block import sleipnir_rx_block, make_sleipnir_rx_block

# Export PDU blocks
try:
    from .sleipnir_superframe_assembler import sleipnir_superframe_assembler, make_sleipnir_superframe_assembler
    from .sleipnir_superframe_parser import sleipnir_superframe_parser, make_sleipnir_superframe_parser
except ImportError:
    from python.sleipnir_superframe_assembler import sleipnir_superframe_assembler, make_sleipnir_superframe_assembler
    from python.sleipnir_superframe_parser import sleipnir_superframe_parser, make_sleipnir_superframe_parser

# Export PTT blocks
try:
    from .ptt_gpio import ptt_gpio, make_ptt_gpio
    from .ptt_serial import ptt_serial, make_ptt_serial
    from .ptt_vox import ptt_vox, make_ptt_vox
    from .ptt_network import ptt_network, make_ptt_network
except ImportError:
    from python.ptt_gpio import ptt_gpio, make_ptt_gpio
    from python.ptt_serial import ptt_serial, make_ptt_serial
    from python.ptt_vox import ptt_vox, make_ptt_vox
    from python.ptt_network import ptt_network, make_ptt_network

# Export ZMQ helpers
try:
    from .zmq_status_output import zmq_status_output, make_zmq_status_output
except ImportError:
    from python.zmq_status_output import zmq_status_output, make_zmq_status_output

# Export crypto modules (for direct access)
try:
    from . import crypto_integration
    from . import crypto_helpers
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from python import crypto_integration
    from python import crypto_helpers

__all__ = [
    # Hierarchical blocks
    'sleipnir_tx_hier',
    'make_sleipnir_tx_hier',
    'sleipnir_rx_hier',
    'make_sleipnir_rx_hier',
    # Main blocks
    'sleipnir_tx_block',
    'make_sleipnir_tx_block',
    'sleipnir_rx_block',
    'make_sleipnir_rx_block',
    # PDU blocks
    'sleipnir_superframe_assembler',
    'make_sleipnir_superframe_assembler',
    'sleipnir_superframe_parser',
    'make_sleipnir_superframe_parser',
    # PTT blocks
    'ptt_gpio',
    'make_ptt_gpio',
    'ptt_serial',
    'make_ptt_serial',
    'ptt_vox',
    'make_ptt_vox',
    'ptt_network',
    'make_ptt_network',
    # ZMQ helpers
    'zmq_status_output',
    'make_zmq_status_output',
    # Crypto modules
    'crypto_integration',
    'crypto_helpers',
]
