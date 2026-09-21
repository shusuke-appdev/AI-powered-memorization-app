"""ユーザー切替時のStreamlitセッション分離とCookie更新キュー。"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

_PRESERVED_KEYS = frozenset({"cookie_controller"})
_PENDING_COOKIE_ACTION_KEY = "_pending_cookie_action"


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


def queue_cookie_set(
    session_state: MutableMapping[str, Any],
    name: str,
    value: str,
    *,
    max_age: int,
) -> None:
    """次のスクリプト実行冒頭でCookieを1回だけ書き込む。"""
    session_state[_PENDING_COOKIE_ACTION_KEY] = {
        "action": "set",
        "name": name,
        "value": value,
        "max_age": max_age,
    }


def queue_cookie_remove(session_state: MutableMapping[str, Any], name: str) -> None:
    """次のスクリプト実行冒頭でCookieを1回だけ削除する。"""
    session_state[_PENDING_COOKIE_ACTION_KEY] = {
        "action": "remove",
        "name": name,
    }


def flush_pending_cookie_action(
    session_state: MutableMapping[str, Any], cookie_controller: Any
) -> bool:
    """保留中のCookie操作を取り出して実行し、二重実行を防ぐ。"""
    action = session_state.pop(_PENDING_COOKIE_ACTION_KEY, None)
    if not action:
        return False

    if action["action"] == "set":
        cookie_controller.set(
            action["name"], action["value"], max_age=action["max_age"]
        )
    elif action["action"] == "remove":
        cookie_controller.remove(action["name"])
    else:
        raise ValueError("Unsupported cookie action")
    return True
