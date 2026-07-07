"""Small reusable Tkinter helpers."""
import tkinter as tk

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
