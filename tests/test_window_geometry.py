"""Tests for cluedo/gui/window_geometry.py -- the taskbar-aware geometry
clamp used by the root window and every Toplevel dialog."""
import tkinter as tk

from cluedo.gui import window_geometry


def test_fit_geometry_uses_full_size_when_it_fits(root, monkeypatch):
    monkeypatch.setattr(window_geometry, "_work_area", lambda win: (0, 0, 1920, 1080))
    win = tk.Toplevel(root)
    try:
        window_geometry.fit_geometry(win, 800, 600)
        win.update_idletasks()
        assert win.winfo_width() == 800
        assert win.winfo_height() == 600
    finally:
        win.destroy()


def test_fit_geometry_clamps_to_usable_area(root, monkeypatch):
    # A 1366x768 display with a Windows taskbar eating ~40px -- the exact
    # scenario from the bug report ("Select Your Hand" buttons hidden behind
    # the taskbar).
    monkeypatch.setattr(window_geometry, "_work_area", lambda win: (0, 0, 1366, 728))
    win = tk.Toplevel(root)
    try:
        window_geometry.fit_geometry(win, 1150, 760)
        win.update_idletasks()
        assert win.winfo_width() <= 1366
        assert win.winfo_height() <= 728
    finally:
        win.destroy()


def test_fit_geometry_centers_within_work_area(root, monkeypatch):
    monkeypatch.setattr(window_geometry, "_work_area", lambda win: (0, 0, 1000, 800))
    win = tk.Toplevel(root)
    try:
        window_geometry.fit_geometry(win, 400, 300)
        win.update_idletasks()
        assert win.winfo_x() == (1000 - 400) // 2
        assert win.winfo_y() == (800 - 300) // 2
    finally:
        win.destroy()


def test_fit_geometry_respects_work_area_offset(root, monkeypatch):
    # A taskbar docked on the left/top shifts the work area's origin away
    # from (0, 0) -- the window should be positioned within *that* area,
    # not the raw screen origin.
    monkeypatch.setattr(window_geometry, "_work_area", lambda win: (50, 30, 1050, 830))
    win = tk.Toplevel(root)
    try:
        window_geometry.fit_geometry(win, 400, 300)
        win.update_idletasks()
        assert win.winfo_x() == 50 + (1000 - 400) // 2
        assert win.winfo_y() == 30 + (800 - 300) // 2
    finally:
        win.destroy()


def test_fit_geometry_minsize_never_exceeds_clamped_size(root, monkeypatch):
    monkeypatch.setattr(window_geometry, "_work_area", lambda win: (0, 0, 500, 400))
    win = tk.Toplevel(root)
    try:
        window_geometry.fit_geometry(win, 1150, 760, min_width=950, min_height=620)
        assert win.minsize() == (500, 400)
    finally:
        win.destroy()


def test_fit_geometry_minsize_uses_caller_value_when_it_fits(root, monkeypatch):
    monkeypatch.setattr(window_geometry, "_work_area", lambda win: (0, 0, 1920, 1080))
    win = tk.Toplevel(root)
    try:
        window_geometry.fit_geometry(win, 1150, 760, min_width=950, min_height=620)
        assert win.minsize() == (950, 620)
    finally:
        win.destroy()
