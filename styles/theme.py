"""端末テーマに追従するアプリ独自部品のカラートークン。"""

from __future__ import annotations

THEME_TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "surface": "#ffffff",
        "surface-muted": "#f8fafc",
        "text": "#1f2937",
        "text-muted": "#4b5563",
        "accent": "#047857",
        "accent-soft": "#d1fae5",
        "accent-text": "#065f46",
        "border": "#cbd5e1",
        "answer": "#047857",
        "highlight": "#b91c1c",
        "civil-bg": "#fef2f2",
        "civil-text": "#991b1b",
        "criminal-bg": "#eff6ff",
        "criminal-text": "#1e40af",
        "public-bg": "#f0fdf4",
        "public-text": "#166534",
        "other-bg": "#fefce8",
        "other-text": "#854d0e",
    },
    "dark": {
        "surface": "#172033",
        "surface-muted": "#111827",
        "text": "#f3f4f6",
        "text-muted": "#cbd5e1",
        "accent": "#34d399",
        "accent-soft": "#064e3b",
        "accent-text": "#d1fae5",
        "border": "#475569",
        "answer": "#6ee7b7",
        "highlight": "#fca5a5",
        "civil-bg": "#451a1a",
        "civil-text": "#fecaca",
        "criminal-bg": "#172554",
        "criminal-text": "#bfdbfe",
        "public-bg": "#052e16",
        "public-text": "#bbf7d0",
        "other-bg": "#422006",
        "other-text": "#fef08a",
    },
}

CONTRAST_PAIRS = (
    ("surface", "text", 4.5),
    ("surface", "text-muted", 4.5),
    ("surface-muted", "text", 4.5),
    ("accent-soft", "accent-text", 4.5),
    ("civil-bg", "civil-text", 4.5),
    ("criminal-bg", "criminal-text", 4.5),
    ("public-bg", "public-text", 4.5),
    ("other-bg", "other-text", 4.5),
)


def render_theme_tokens_css() -> str:
    """ライト／ダークのCSS変数をprefers-color-schemeで出力する。"""

    def declarations(theme: str) -> str:
        return "\n".join(
            f"    --app-{name}: {value};" for name, value in THEME_TOKENS[theme].items()
        )

    return (
        f":root {{\n{declarations('light')}\n}}\n"
        "@media (prefers-color-scheme: dark) {\n"
        f"  :root {{\n{declarations('dark')}\n  }}\n"
        "}"
    )
