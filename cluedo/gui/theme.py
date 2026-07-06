"""Shared visual constants so every screen looks consistent."""

FONT_FAMILY = "Segoe UI"

BG = "#f5f6fa"
PANEL_BG = "#ffffff"
TEXT = "#2b2d42"
MUTED_TEXT = "#6c757d"
ACCENT = "#4361ee"
ACCENT_DARK = "#3a0ca3"

CONFIRMED = "#2ecc71"
IMPOSSIBLE = "#e76f51"
POSSIBLE = "#f4c542"
UNKNOWN = "#dee2e6"
SOLVED_BG = "#d1f7dc"
SOLVED_TEXT = "#1b5e20"


def heading_font(size: int = 16, weight: str = "bold"):
    return (FONT_FAMILY, size, weight)


def body_font(size: int = 10, weight: str = "normal"):
    return (FONT_FAMILY, size, weight)
