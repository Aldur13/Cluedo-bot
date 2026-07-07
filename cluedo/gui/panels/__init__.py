"""Reusable dashboard side-panels ("cards").

Each module exposes a single `build(parent, theme, app) -> tk.Frame`
factory. `app` is captured via closure for any callback a card needs (e.g.
jumping into Replay, reading a cached analysis result) -- it is not passed
again on refresh. The returned frame has a `.refresh(game_state)` callable
attached as an instance attribute -- call it whenever the game state
changes to redraw the card's contents in place (the frame itself is
created once and reused). Every card wraps its content in
`cluedo.gui.widgets.CollapsibleCard` for consistent chrome (title bar,
expand/collapse, remembered state) instead of a bare `tk.LabelFrame`.
"""
