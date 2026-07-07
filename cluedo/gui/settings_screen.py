"""Settings screen: theme picker (wires the already-built ThemeManager, which
previously had no UI ever calling `set_theme`) plus the cross-game learning
opt-out checkbox for `cluedo.persistence.player_store` (its own settings
table already supports this; this is just the first UI that surfaces it).
"""
import tkinter as tk

from cluedo.gui.theme import BUILTIN_THEMES


def open_settings(app):
    theme = app.theme_manager.current
    win = tk.Toplevel(app.root)
    win.title("Settings")
    win.geometry("360x320")
    win.configure(bg=theme.bg)

    tk.Label(win, text="Theme", font=theme.heading_font(13), bg=theme.bg, fg=theme.text).pack(
        anchor="w", padx=14, pady=(14, 6)
    )

    theme_var = tk.StringVar(value=theme.name)

    def on_theme_pick():
        chosen = BUILTIN_THEMES.get(theme_var.get())
        if chosen is not None:
            app.theme_manager.set_theme(chosen)
            # This Toplevel's own colors won't live-update (matches every
            # other dialog in the app -- only the swapped main screen
            # re-renders on a theme change, per ThemeManager's docstring);
            # closing and reopening Settings picks up the new theme.
            win.destroy()
            open_settings(app)

    for name, label in (("light", "Light"), ("dark", "Dark"), ("high_contrast", "High Contrast")):
        tk.Radiobutton(
            win, text=label, variable=theme_var, value=name, command=on_theme_pick,
            bg=theme.bg, fg=theme.text, selectcolor=theme.panel_bg, font=theme.body_font(10),
        ).pack(anchor="w", padx=20, pady=2)

    tk.Frame(win, bg=theme.muted_text, height=1).pack(fill="x", padx=14, pady=12)

    tk.Label(
        win, text="Cross-Game Learning", font=theme.heading_font(13), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", padx=14, pady=(0, 6))
    tk.Label(
        win,
        text="Records player names, suggestion history, and outcomes locally\n"
             "(on this device only) to power the AI Insights panel across games.",
        font=theme.body_font(9), fg=theme.muted_text, bg=theme.bg, justify="left", wraplength=320,
    ).pack(anchor="w", padx=14, pady=(0, 6))

    learning_var = tk.BooleanVar(value=app.player_store.is_learning_enabled())

    def on_learning_toggle():
        app.player_store.set_learning_enabled(learning_var.get())

    tk.Checkbutton(
        win, text="Enable cross-game learning", variable=learning_var, command=on_learning_toggle,
        bg=theme.bg, fg=theme.text, selectcolor=theme.panel_bg, font=theme.body_font(10),
    ).pack(anchor="w", padx=20, pady=(0, 6))

    reset_button = tk.Button(
        win, text="Reset all recorded player data", font=theme.body_font(9),
        command=lambda: app.player_store.reset_all_data(),
    )
    reset_button.pack(anchor="w", padx=20, pady=(4, 14))

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
