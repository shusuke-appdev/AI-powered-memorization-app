from styles.theme import CONTRAST_PAIRS, THEME_TOKENS, render_theme_tokens_css


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_custom_theme_tokens_meet_wcag_contrast_targets() -> None:
    for theme_name, tokens in THEME_TOKENS.items():
        for background, foreground, minimum in CONTRAST_PAIRS:
            ratio = _contrast_ratio(tokens[background], tokens[foreground])
            assert ratio >= minimum, (
                f"{theme_name}: {foreground} on {background} is {ratio:.2f}:1"
            )


def test_theme_automatically_follows_device_color_scheme() -> None:
    css = render_theme_tokens_css()
    assert "prefers-color-scheme: dark" in css
    assert "[data-theme" not in css
