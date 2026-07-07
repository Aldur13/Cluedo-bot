"""Theme: a swappable bundle of colors/fonts so every screen looks consistent
and can be re-skinned live (Light/Dark/High-Contrast/Custom) without each
screen hardcoding its own palette."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    panel_bg: str
    text: str
    muted_text: str
    accent: str
    accent_dark: str
    confirmed: str
    impossible: str
    possible: str
    unknown: str
    solved_bg: str
    solved_text: str
    font_family: str = "Segoe UI"

    def heading_font(self, size: int = 16, weight: str = "bold"):
        return (self.font_family, size, weight)

    def body_font(self, size: int = 10, weight: str = "normal"):
        return (self.font_family, size, weight)


# Exact values carried over from the pre-v2.0 single fixed palette, so the
# app renders pixel-identical to v1.0.0 under LIGHT.
LIGHT = Theme(
    name="light",
    bg="#f5f6fa",
    panel_bg="#ffffff",
    text="#2b2d42",
    muted_text="#6c757d",
    accent="#4361ee",
    accent_dark="#3a0ca3",
    confirmed="#2ecc71",
    impossible="#e76f51",
    possible="#f4c542",
    unknown="#dee2e6",
    solved_bg="#d1f7dc",
    solved_text="#1b5e20",
)

DARK = Theme(
    name="dark",
    bg="#1e1e2a",
    panel_bg="#292a38",
    text="#e6e6f0",
    muted_text="#9a9ab5",
    accent="#7c8cff",
    accent_dark="#5b6eff",
    confirmed="#3ddc84",
    impossible="#ff6b6b",
    possible="#ffd166",
    unknown="#3f4054",
    solved_bg="#1f3d2c",
    solved_text="#7be8a0",
)

HIGH_CONTRAST = Theme(
    name="high_contrast",
    bg="#000000",
    panel_bg="#000000",
    text="#ffffff",
    muted_text="#e0e0e0",
    accent="#ffff00",
    accent_dark="#ffcc00",
    confirmed="#00ff00",
    impossible="#ff0000",
    possible="#00ffff",
    unknown="#808080",
    solved_bg="#003300",
    solved_text="#00ff00",
)

BUILTIN_THEMES: dict[str, Theme] = {t.name: t for t in (LIGHT, DARK, HIGH_CONTRAST)}


def custom_theme(base: Theme, **overrides) -> Theme:
    """Builds a user-customized theme by overriding fields on a builtin base
    (e.g. custom_theme(LIGHT, accent="#ff00aa"))."""
    return replace(base, name="custom", **overrides)


class ThemeManager:
    """Owns the single live Theme and notifies subscribers on change. Screens
    read `theme_manager.current` at build time; App re-invokes whatever
    screen was last shown after a theme swap (see App._current_screen_show)
    rather than trying to live-recolor existing widgets."""

    def __init__(self, initial: Theme = LIGHT):
        self._current = initial
        self._subscribers: list[Callable[[Theme], None]] = []

    @property
    def current(self) -> Theme:
        return self._current

    def set_theme(self, theme: Theme) -> None:
        self._current = theme
        for callback in list(self._subscribers):
            callback(theme)

    def subscribe(self, callback: Callable[[Theme], None]) -> None:
        self._subscribers.append(callback)
