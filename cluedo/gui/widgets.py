"""Small reusable Tkinter helpers."""
import tkinter as tk

from cluedo.gui import sidebar_state
from cluedo.gui.theme import LIGHT


class ChoiceGrid:
    """A grid of single-click buttons bound to one tk.StringVar -- replaces a
    dropdown (which always costs two clicks and hides the other options) with
    every option visible and selectable in one click. The selected button is
    highlighted; clicking updates the variable, which triggers any trace_add
    callbacks exactly like a dropdown would."""

    def __init__(self, parent, options, variable, theme=LIGHT, columns=3, bg=None):
        self.variable = variable
        self.theme = theme
        self.buttons = {}
        self.frame = tk.Frame(parent, bg=bg or theme.bg)
        for i, name in enumerate(options):
            btn = tk.Button(
                self.frame, text=name, font=theme.body_font(9), width=15,
                anchor="w", padx=6, pady=5, relief="raised", bd=1,
                command=lambda n=name: self._select(n),
            )
            btn.grid(row=i // columns, column=i % columns, padx=2, pady=2, sticky="nsew")
            self.buttons[name] = btn
        for c in range(columns):
            self.frame.grid_columnconfigure(c, weight=1)
        self._refresh()

    def _select(self, name):
        self.variable.set(name)
        self._refresh()

    def _refresh(self):
        current = self.variable.get()
        for name, btn in self.buttons.items():
            if name == current:
                btn.config(bg=self.theme.accent, fg="white", relief="sunken")
            else:
                btn.config(bg=self.theme.panel_bg, fg=self.theme.text, relief="raised")

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)


class Tooltip:
    """Hover tooltip. `text_fn` may be a plain string or a zero-arg callable
    evaluated fresh on every hover, so it can reflect current game state.
    Deliberately kept a fixed pale-yellow bubble regardless of the active
    Theme -- like OS-native tooltips, it reads better as a consistent
    overlay than as a re-skinned panel, in light or dark mode alike."""

    def __init__(self, widget, text_fn, theme=LIGHT):
        self.widget = widget
        self.text_fn = text_fn
        self.theme = theme
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        text = self.text_fn() if callable(self.text_fn) else self.text_fn
        if not text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip, text=text, background="#ffffe0", relief="solid", borderwidth=1,
            font=self.theme.body_font(9), justify="left", wraplength=320, padx=6, pady=4,
        )
        label.pack()

    def hide(self, event=None):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class CollapsibleCard:
    """A titled card with a clickable header that shows/hides its body.
    Expand/collapse state is remembered per `key` for the process session
    (see cluedo.gui.sidebar_state) -- collapsing a card and then refreshing
    the dashboard (e.g. after logging a suggestion) does not silently
    re-expand it.

    `.frame` is the outer `tk.Frame` a caller packs/grids like any other
    widget; `.body` is where the card's own content goes. The header
    `tk.Label` carries a `card_title_text` attribute (the exact `title`
    string) so structural tests can find real card headers without relying
    on text matching against arbitrary body content.
    """

    def __init__(self, parent, theme, title: str, key: str, *, fg=None, disclaimer: str | None = None):
        self.key = key
        self.theme = theme

        self.frame = tk.Frame(parent, bg=theme.panel_bg, highlightbackground=theme.unknown, highlightthickness=1)

        header = tk.Frame(self.frame, bg=theme.panel_bg, cursor="hand2")
        header.pack(fill="x")

        self._toggle_label = tk.Label(
            header, text="", bg=theme.panel_bg, fg=fg or theme.text, font=theme.body_font(11, "bold"), width=2,
        )
        self._toggle_label.pack(side="left", padx=(6, 0), pady=6)

        self.title_label = tk.Label(
            header, text=title, bg=theme.panel_bg, fg=fg or theme.text, font=theme.body_font(11, "bold"),
            anchor="w",
        )
        self.title_label.card_title_text = title
        self.title_label.pack(side="left", fill="x", expand=True, padx=(2, 6), pady=6)

        for widget in (header, self._toggle_label, self.title_label):
            widget.bind("<Button-1>", lambda _e: self.toggle())

        self.body = tk.Frame(self.frame, bg=theme.panel_bg)
        if disclaimer:
            tk.Label(
                self.body, text=disclaimer, bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(8),
                wraplength=280, justify="left",
            ).pack(anchor="w", padx=8, pady=(0, 4))

        self._expanded = True
        self._apply_expanded(sidebar_state.get_expanded(key, True))

    def toggle(self) -> None:
        self._apply_expanded(not self._expanded)
        sidebar_state.set_expanded(self.key, self._expanded)

    def _apply_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        if expanded:
            self.body.pack(fill="x", padx=8, pady=(0, 8))
            self._toggle_label.config(text="▾")  # ▾
        else:
            self.body.pack_forget()
            self._toggle_label.config(text="▸")  # ▸

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
