"""Reusable dashboard side-panels.

Each module exposes a single `build(parent, theme) -> tk.Frame` factory. The
returned frame has a `.refresh(game_state)` callable attached as an instance
attribute -- call it whenever the game state changes to redraw the panel's
contents in place (the frame itself is created once and reused).
"""
