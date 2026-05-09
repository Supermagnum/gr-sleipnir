# SPDX-License-Identifier: GPL-3.0-or-later
"""Contact and public-key lookup helpers for sleipnir text messaging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_linux_crypto_module() -> Any:
    for name in ("gnuradio.linux_crypto", "linux_crypto", "gr_linux_crypto"):
        try:
            return __import__(name, fromlist=["*"])
        except ImportError:
            continue
    return None


class ContactStore:
    """
    Manages contacts and public keys for text message addressing.

    When gr-linux-crypto is available, :class:`CallsignKeyStore` is used so
    kernel keyring-backed entries and JSON file groups match that module.

    For ``key_source="galdralag"``, an :class:`EphemeralKeyStore` is consulted
    when importable (session-oriented material; may return no key for a bare
    callsign).

    Without gr-linux-crypto, a minimal JSON file shim (same top-level object
    layout as CallsignKeyStore) handles ``add_contact``, ``get_group_members``,
    and ``list_contacts`` for static keys and groups only.
    """

    def __init__(self, key_source: str = "auto", json_path: Optional[str] = None) -> None:
        self.key_source = key_source.lower().strip()
        self.json_path = json_path
        self._lc = _load_linux_crypto_module()
        self._cks: Any = None
        self._ephemeral_store: Any = None
        self._json_shim: Dict[str, Any] = {}
        self._json_file: Optional[Path] = None

        use_keyring = self.key_source in ("auto", "gnupg")

        if self._lc is not None:
            CallsignKeyStore = getattr(self._lc, "CallsignKeyStore", None)
            if CallsignKeyStore is not None:
                try:
                    self._cks = CallsignKeyStore(store_path=json_path, use_keyring=use_keyring)
                except Exception:
                    self._cks = None

            EphemeralKeyStore = getattr(self._lc, "EphemeralKeyStore", None)
            if EphemeralKeyStore is not None and self.key_source in ("auto", "galdralag"):
                try:
                    self._ephemeral_store = EphemeralKeyStore()
                except Exception:
                    self._ephemeral_store = None
        else:
            base = Path.home() / ".gnuradio"
            base.mkdir(parents=True, exist_ok=True)
            self._json_file = Path(json_path) if json_path else base / "callsign_keys.json"
            self._load_json_shim()

    def _load_json_shim(self) -> None:
        if self._json_file is None or not self._json_file.exists():
            self._json_shim = {}
            return
        try:
            raw = json.loads(self._json_file.read_text(encoding="utf-8"))
            self._json_shim = raw if isinstance(raw, dict) else {}
        except Exception:
            self._json_shim = {}

    def _save_json_shim(self) -> None:
        if self._json_file is None:
            return
        try:
            self._json_file.parent.mkdir(parents=True, exist_ok=True)
            self._json_file.write_text(json.dumps(self._json_shim, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_public_key(self, callsign: str) -> Optional[str]:
        cs = callsign.upper().strip()

        if self.key_source in ("auto", "galdralag") and self._ephemeral_store is not None:
            for attr in ("get_public_key_pem", "export_peer_public_pem", "get_peer_public_key"):
                fn = getattr(self._ephemeral_store, attr, None)
                if callable(fn):
                    try:
                        pk = fn(cs)
                        if pk:
                            return str(pk)
                    except Exception:
                        pass

        if self._cks is not None:
            try:
                return self._cks.get_public_key(cs)
            except Exception:
                pass

        if self._lc is None and cs in self._json_shim and isinstance(self._json_shim[cs], str):
            return str(self._json_shim[cs])
        return None

    def list_contacts(self) -> List[str]:
        if self._cks is not None:
            fn = getattr(self._cks, "list_callsigns", None)
            if callable(fn):
                try:
                    return [str(x) for x in fn()]
                except Exception:
                    pass

        keys = []
        for k, v in self._json_shim.items():
            if isinstance(v, str):
                keys.append(str(k).upper().strip())
        return sorted(keys)

    def add_contact(self, callsign: str, public_key_pem: str) -> None:
        cs = callsign.upper().strip()
        if self._cks is not None:
            fn = getattr(self._cks, "add_public_key", None)
            if callable(fn):
                try:
                    fn(cs, public_key_pem)
                except Exception:
                    pass
                return

        self._json_shim[cs] = public_key_pem
        self._save_json_shim()

    def get_group_members(self, group: str) -> List[str]:
        if self._cks is not None:
            fn = getattr(self._cks, "get_group", None)
            if callable(fn):
                try:
                    g = fn(group)
                    if g:
                        return [str(x).upper().strip() for x in g]
                except Exception:
                    pass

        raw = self._json_shim.get(group)
        if isinstance(raw, list):
            return [str(x).upper().strip() for x in raw]
        return []

    def resolve_destination(self, dst: str) -> List[str]:
        d = dst.strip()
        if d.upper() == "ALL":
            return []
        if d.upper().startswith("GROUP:"):
            name = d.split(":", 1)[1].strip()
            return self.get_group_members(name)
        return [d.upper().strip()]
