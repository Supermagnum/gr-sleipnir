# SPDX-License-Identifier: GPL-3.0-or-later
"""
Legacy-style entry point matching the GNU Radio 4 header-only C++ block name.

The assembler implementation lives in ``superframe_assembler.py`` (this module re-exports it).
GNU Radio DSP blocks remain C++; this wrapper is offline/tooling/import compatibility only.
"""

from __future__ import annotations

from .superframe_assembler import SuperframeAssembler

__all__: list[str] = ["SuperframeAssembler"]
