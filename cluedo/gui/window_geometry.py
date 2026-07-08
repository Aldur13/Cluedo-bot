"""Screen/taskbar-aware window sizing.

Every screen/dialog in this app requests a fixed pixel size (e.g.
`win.geometry("820x760")`). On a small display -- a 1366x768 laptop with a
Windows taskbar eating ~40-50px of vertical space -- a naive fixed geometry
can render partially behind the taskbar, hiding action buttons at the
bottom of the window. `fit_geometry()` clamps the requested size to the
actual usable screen area (excluding the taskbar) and centers the window
within it, so windows always render fully on-screen regardless of display
size.
"""
from __future__ import annotations

import sys
import tkinter as tk

# Fallback allowance (px) for the taskbar when the platform-specific work
# area can't be queried (non-Windows, or the Win32 call fails for any
# reason) -- deliberately generous since overshooting means "a bit more
# margin than strictly needed", while undershooting means "buttons hidden
# behind the taskbar again", the exact bug this module exists to prevent.
_FALLBACK_TASKBAR_ALLOWANCE = 80


def _work_area(win: tk.Misc) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the usable screen area (monitor area
    minus taskbar/docked toolbars)."""
    win.update_idletasks()
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            spi_getworkarea = 0x0030
            ok = ctypes.windll.user32.SystemParametersInfoW(spi_getworkarea, 0, ctypes.byref(rect), 0)
            if ok:
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            pass
    return 0, 0, screen_w, screen_h - _FALLBACK_TASKBAR_ALLOWANCE


def fit_geometry(
    win: tk.Misc,
    width: int,
    height: int,
    min_width: "int | None" = None,
    min_height: "int | None" = None,
) -> None:
    """Clamp (width, height) to the usable screen work area, center the
    window within it, and apply both the geometry and a matching minsize
    (so resizing back up can't reintroduce the overflow)."""
    left, top, right, bottom = _work_area(win)
    usable_w = max(1, right - left)
    usable_h = max(1, bottom - top)
    w = min(width, usable_w)
    h = min(height, usable_h)
    x = left + max(0, (usable_w - w) // 2)
    y = top + max(0, (usable_h - h) // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")
    win.minsize(min(min_width or w, w), min(min_height or h, h))
