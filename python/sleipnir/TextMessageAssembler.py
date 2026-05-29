# SPDX-License-Identifier: GPL-3.0-or-later
"""Re-export offline TextMessageAssembler (see text_message_assembler.py)."""

from __future__ import annotations

from .text_message_assembler import TextMessageAssembler

__all__: list[str] = ["TextMessageAssembler"]
