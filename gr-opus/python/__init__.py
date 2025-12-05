"""
GNU Radio Out-of-Tree Module: gr-opus
Opus audio codec wrapper module
"""

try:
    from .opus_encoder import opus_encoder
    from .opus_decoder import opus_decoder
except ImportError:
    import sys
    import os
    dirname, filename = os.path.split(os.path.abspath(__file__))
    __path__.append(os.path.join(dirname, "bindings"))
    from .opus_encoder import opus_encoder
    from .opus_decoder import opus_decoder

__all__ = ['opus_encoder', 'opus_decoder']

