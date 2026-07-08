"""Reusable Canvas+Scrollbar+inner-Frame scrolling idiom.

Extracted so new call sites don't hand-duplicate the pattern; sheet_grid.py
and suggestion_dialog.py still hand-roll their own independent copy (left
as-is), but every other Canvas+Scrollbar call site in this package,
including game_review_screen.py, has been migrated to this shared helper.
"""
from __future__ import annotations

import tkinter as tk


def build_scrollable_frame(parent, theme) -> tuple[tk.Frame, tk.Frame]:
    """Returns (outer, inner). Pack/grid `outer` in the caller's layout;
    pack content into `inner` exactly as if it were a plain Frame -- it
    scrolls automatically once its content overflows the visible area.
    `inner`'s width is kept in sync with the canvas's visible width, so
    `fill="x"` children span the full scrollable width rather than
    shrink-wrapping to their natural size.

    Scrolling works via mouse wheel, touchpad (Windows reports touchpad
    scrolling through the same <MouseWheel> message as a mouse, so no
    separate handling is needed), Linux Button-4/-5, and keyboard
    (Up/Down/PageUp/PageDown/Home/End) once something inside `inner` has
    focus. The scrollbar auto-hides when content fits the visible area.
    """
    outer = tk.Frame(parent, bg=theme.bg)

    canvas = tk.Canvas(outer, bg=theme.bg, highlightthickness=0, takefocus=1)
    scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    # scrollbar is packed/unpacked on demand by _update_scrollbar_visibility,
    # not packed unconditionally here -- it should only appear once content
    # actually overflows the visible area.

    inner = tk.Frame(canvas, bg=theme.bg)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _update_scrollbar_visibility():
        bbox = canvas.bbox("all")
        content_height = (bbox[3] - bbox[1]) if bbox else 0
        if content_height > canvas.winfo_height():
            if scrollbar.winfo_manager() != "pack":
                # `before=canvas` matters: canvas is packed with fill="both",
                # expand=True, so re-adding the scrollbar with a plain
                # trailing pack() (appending it after canvas in the packer's
                # slave order) starves it of any real width -- inserting it
                # back before canvas in that order is what actually gives it
                # space again.
                scrollbar.pack(side="right", fill="y", before=canvas)
        elif scrollbar.winfo_manager() == "pack":
            scrollbar.pack_forget()

    def _on_inner_configure(_event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        _update_scrollbar_visibility()

    def _on_canvas_configure(event):
        canvas.itemconfig(window_id, width=event.width)
        _update_scrollbar_visibility()

    inner.bind("<Configure>", _on_inner_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    # ------------------------------------------------------------- wheel
    def _widget_is_within(widget, ancestor) -> bool:
        while widget is not None:
            if widget is ancestor:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _scroll_units(event) -> int:
        num = getattr(event, "num", None)
        if num == 4:
            return -1
        if num == 5:
            return 1
        return -1 if event.delta > 0 else 1

    def _on_mousewheel(event):
        # `bind_all` (rather than a plain `bind` toggled on <Enter>/<Leave>)
        # is required here: `inner` and its descendants are separate
        # sub-windows fully covering the canvas, so canvas-level crossing
        # events don't fire while hovering over actual content -- instead
        # we listen globally and use ancestry to scope the scroll to
        # whichever scrollable panel the pointer is actually over, so this
        # doesn't hijack wheel events meant for other scrollable areas
        # (e.g. the detective-sheet grid) in the same window.
        if not outer.winfo_exists():
            return
        if not _widget_is_within(event.widget, canvas):
            return
        if canvas.bbox("all") is None:
            return
        canvas.yview_scroll(_scroll_units(event), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
    canvas.bind_all("<Button-4>", _on_mousewheel, add="+")
    canvas.bind_all("<Button-5>", _on_mousewheel, add="+")

    # ----------------------------------------------------------- keyboard
    canvas.bind("<Button-1>", lambda _event: canvas.focus_set())

    def _on_key_scroll(amount, unit):
        def _handler(_event):
            if not outer.winfo_exists():
                return
            if not _widget_is_within(outer.focus_get(), canvas):
                return
            if unit == "moveto":
                canvas.yview_moveto(amount)
            else:
                canvas.yview_scroll(amount, unit)

        return _handler

    canvas.bind_all("<Up>", _on_key_scroll(-1, "units"), add="+")
    canvas.bind_all("<Down>", _on_key_scroll(1, "units"), add="+")
    canvas.bind_all("<Prior>", _on_key_scroll(-1, "pages"), add="+")
    canvas.bind_all("<Next>", _on_key_scroll(1, "pages"), add="+")
    canvas.bind_all("<Home>", _on_key_scroll(0, "moveto"), add="+")
    canvas.bind_all("<End>", _on_key_scroll(1, "moveto"), add="+")

    return outer, inner
