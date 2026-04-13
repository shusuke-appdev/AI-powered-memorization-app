"""
スタイル管理モジュール — CSSファイルの読み込みとStreamlitへの適用
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

_STYLES_DIR = Path(os.path.dirname(os.path.abspath(__file__)))


def _read_css(filename: str) -> str:
    """CSSファイルを読み込む"""
    css_path = _STYLES_DIR / filename
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def apply_base_styles() -> None:
    """ベーススタイルとモバイルレスポンシブCSSを適用"""
    base_css = _read_css("base.css")
    mobile_css = _read_css("mobile.css")
    st.markdown(f"<style>{base_css}\n{mobile_css}</style>", unsafe_allow_html=True)


def apply_dark_mode_styles() -> None:
    """ダークモード用CSSを適用"""
    dark_css = _read_css("dark_mode.css")
    st.markdown(f"<style>{dark_css}</style>", unsafe_allow_html=True)
