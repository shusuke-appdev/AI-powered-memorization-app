"""ユーザー切替時のStreamlitセッション分離。"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

_PRESERVED_KEYS = frozenset({"cookie_controller", "dark_mode"})


def reset_user_session_state(
    session_state: MutableMapping[str, Any],
    *,
    preserve_keys: frozenset[str] = _PRESERVED_KEYS,
) -> None:
    """ユーザー依存状態を消去し、明示したアプリ共通状態だけを残す。"""
    preserved = {
        key: session_state[key] for key in preserve_keys if key in session_state
    }
    for key in list(session_state):
        del session_state[key]
    session_state.update(preserved)
