# SPDX-License-Identifier: GPL-3.0-or-later
"""Re-export offline TextMessageParser (see text_message_parser.py)."""

from __future__ import annotations

from .text_message_parser import ParsedTextMessage, TextMessageParser

__all__: list[str] = ["TextMessageParser", "ParsedTextMessage"]
