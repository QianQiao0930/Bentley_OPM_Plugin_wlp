"""Reusable Tkinter/ttk UI toolkit for Bentley MicroStation Python plug-ins.

Everything in this module is host-agnostic: it only depends on ``tkinter`` and
``pywin32``.  The MicroStation host API is imported lazily inside
:meth:`BentleyTk.run_bentley_loop`, so the module can be imported (and its pure
helpers tested) even outside a Bentley-hosted Python process.

Typical use::

    from bentley_ui import GlassDialog, RoundButton

    class MyDialog(GlassDialog):
        STATE_KEY = "MyPlugin"
        def __init__(self):
            GlassDialog.__init__(self, title="我的工具")
            form = self.build_shell("我的工具", "副标题")
            ...build widgets...
            self.restore_position()
        def restore_state(self):
            ...
        def persist_state(self, state):
            state["some_option"] = self._option.get()

    MyDialog().run_bentley_loop()
"""

from __future__ import division

import json
import os
import tempfile
import tkinter as tk
from tkinter import ttk

import win32con
import win32gui


# ---------------------------------------------------------------------------
# Palette and fonts ("glass card" theme)
# ---------------------------------------------------------------------------

BG = "#EEF2F7"
CARD = "#FFFFFF"
CARD_SOFT = "#F4F7FB"
BORDER = "#E3E9F1"
INK = "#1F2A3D"
MUTED = "#8C97A8"
ACCENT = "#E0A800"
FIELD = "#FBFCFE"

UI_FONT = ("Microsoft YaHei UI", 10)
UI_FONT_SMALL = ("Microsoft YaHei UI", 9)
UI_FONT_BOLD = ("Microsoft YaHei UI", 10, "bold")
UI_FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")

_STATE_FILENAME = "ui_state.json"


def mix_color(source, target, ratio):
    """Linear blend between two ``'#RRGGBB'`` colours (ratio 0 -> source)."""
    source = source.lstrip("#")
    target = target.lstrip("#")
    blended = []
    for offset in (0, 2, 4):
        first = int(source[offset:offset + 2], 16)
        second = int(target[offset:offset + 2], 16)
        blended.append(max(0, min(255, int(round(first + (second - first) * ratio)))))
    return "#%02X%02X%02X" % tuple(blended)


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def state_root():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = tempfile.gettempdir()
    return os.path.join(base, "BentleyPythonPlugins")


def state_path(app_key):
    directory = os.path.join(state_root(), app_key)
    try:
        if not os.path.isdir(directory):
            os.makedirs(directory)
    except OSError:
        return None
    return os.path.join(directory, _STATE_FILENAME)


def load_ui_state(app_key):
    path = state_path(app_key)
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_ui_state(app_key, state):
    path = state_path(app_key)
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Custom widgets
# ---------------------------------------------------------------------------

class RoundButton(tk.Canvas):
    """Rounded canvas button with a hover fade; can be enabled / disabled."""

    def __init__(self, parent, text, command, primary=False, bg=CARD,
                 font=UI_FONT, font_bold=None):
        self._command = command
        self._enabled = True
        self._ratio = 0.0
        self._target = 0.0
        self._job = None
        self._primary = primary
        self._text = text
        self._font = font_bold if (primary and font_bold) else font
        text_width = sum(14 if ord(char) > 127 else 7 for char in text)
        self._width = text_width + 44
        self._height = 36
        self._radius = 10
        self._idle = (
            "#2A3644" if primary else bg,
            "#2A3644" if primary else "#D8E0EA",
            "#FFFFFF" if primary else "#33415C",
        )
        self._hover = (
            "#3D4C5E" if primary else "#F0F5FA",
            "#3D4C5E" if primary else "#B9C6D6",
            "#FFFFFF" if primary else "#33415C",
        )
        tk.Canvas.__init__(self, parent, width=self._width, height=self._height,
                           bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.bind("<Enter>", lambda event: self._set_target(1.0))
        self.bind("<Leave>", lambda event: self._set_target(0.0))
        self.bind("<Button-1>", self._on_click)
        self._paint()

    def _palette(self):
        if not self._enabled:
            return "#E7EBF1", "#E7EBF1", "#A9B3C2"
        return (
            mix_color(self._idle[0], self._hover[0], self._ratio),
            mix_color(self._idle[1], self._hover[1], self._ratio),
            mix_color(self._idle[2], self._hover[2], self._ratio),
        )

    def _paint(self):
        self.delete("all")
        fill, edge, text_fill = self._palette()
        width, height, radius = self._width, self._height, self._radius
        x1, y1, x2, y2 = 1, 1, width - 1, height - 1
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        self.create_polygon(points, smooth=True, fill=fill, outline=edge)
        self.create_text(width / 2.0, height / 2.0, text=self._text,
                         fill=text_fill, font=self._font)

    def _step(self):
        if abs(self._target - self._ratio) < 0.04:
            self._ratio = self._target
            self._job = None
        else:
            self._ratio += (self._target - self._ratio) * 0.32
            self._job = self.after(16, self._step)
        self._paint()

    def _set_target(self, target):
        if not self._enabled:
            return
        self._target = target
        if self._job is None:
            self._step()

    def _on_click(self, event):
        if self._enabled and self._command is not None:
            self._command()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        if not self._enabled:
            self._target = 0.0
            self._ratio = 0.0
            self._job = None
        self.configure(cursor="hand2" if self._enabled else "arrow")
        self._paint()

    def set_text(self, text):
        self._text = text
        text_width = sum(14 if ord(char) > 127 else 7 for char in text)
        self._width = text_width + 44
        self.configure(width=self._width)
        self._paint()

    def set_command(self, command):
        self._command = command


class SlimScrollbar(tk.Canvas):
    """Flat canvas scrollbar: one rounded thumb, no arrows or 3-D bevels.

    It stays invisible while everything fits, so a list looks clean until it
    actually needs to scroll.  Wire it with ``tree.configure(yscrollcommand=bar.set)``
    and ``bar = SlimScrollbar(parent, command=tree.yview)``.
    """

    def __init__(self, parent, command, width=10, thumb="#C7D2E0",
                 thumb_active="#9FB0C6", trough=CARD):
        tk.Canvas.__init__(self, parent, width=width, height=1, bg=trough,
                           highlightthickness=0, bd=0)
        self._command = command
        self._width = width
        self._thumb = thumb
        self._thumb_active = thumb_active
        self._first = 0.0
        self._last = 1.0
        self._drag_offset = None
        self._hover = False
        self.bind("<Configure>", lambda event: self._paint())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def set(self, first, last):
        self._first = max(0.0, min(1.0, float(first)))
        self._last = max(0.0, min(1.0, float(last)))
        self._paint()

    def _thumb_bounds(self):
        height = max(1, self.winfo_height())
        top = self._first * height
        bottom = self._last * height
        minimum = 26.0
        if bottom - top < minimum:
            top = max(0.0, min(top, height - minimum))
            bottom = min(float(height), top + minimum)
        return top, bottom

    def _paint(self):
        self.delete("all")
        if self._last - self._first >= 0.999:
            return
        top, bottom = self._thumb_bounds()
        margin = 2
        radius = (self._width - 2 * margin) / 2.0
        fill = self._thumb_active if (
            self._hover or self._drag_offset is not None) else self._thumb
        x1, x2 = margin, self._width - margin
        y1, y2 = top + margin, bottom - margin
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        self.create_polygon(points, smooth=True, fill=fill, outline="")

    def _on_enter(self, event):
        self._hover = True
        self._paint()

    def _on_leave(self, event):
        self._hover = False
        self._paint()

    def _on_press(self, event):
        top, bottom = self._thumb_bounds()
        if top <= event.y <= bottom:
            self._drag_offset = event.y - top
        else:
            self._drag_offset = (bottom - top) / 2.0
            self._scroll_to(event.y - self._drag_offset)
        self._paint()

    def _on_drag(self, event):
        if self._drag_offset is None:
            return
        self._scroll_to(event.y - self._drag_offset)

    def _on_release(self, event):
        self._drag_offset = None
        self._paint()

    def _scroll_to(self, thumb_top):
        height = max(1, self.winfo_height())
        span = self._last - self._first
        if span >= 1.0:
            return
        first = max(0.0, min(1.0 - span, thumb_top / float(height)))
        self._command("moveto", first)


def attach_wheel(tree, units=1):
    """Make a ``ttk.Treeview`` scroll with the mouse wheel."""
    def handler(event):
        tree.yview_scroll(-units if event.delta > 0 else units, "units")
        return "break"
    tree.bind("<MouseWheel>", handler)
    return handler


class ScrollFrame(tk.Frame):
    """A vertically scrollable container with a slim scrollbar.

    Add children to :attr:`body` (a plain ``tk.Frame``).  Unlike a ``Treeview``
    it wraps content, so long labels stay readable.  Give it a fixed *height*
    and ``pack(fill="both", expand=True)``.
    """

    def __init__(self, parent, bg=CARD, height=320):
        tk.Frame.__init__(self, parent, bg=bg)
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0,
                                 height=height)
        self._bar = SlimScrollbar(self, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._bar.set)
        self.body = tk.Frame(self._canvas, bg=bg)
        self._window = self._canvas.create_window((0, 0), window=self.body,
                                                  anchor="nw")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._bar.pack(side="right", fill="y")
        self.body.bind("<Configure>", self._on_body)
        self._canvas.bind("<Configure>", self._on_canvas)
        # Mouse wheel: bind on the toplevel and only react when the pointer is
        # actually over this frame (works even when it is over a child widget).
        try:
            self.winfo_toplevel().bind("<MouseWheel>", self._on_wheel, add="+")
        except tk.TclError:
            pass

    def _on_body(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas(self, event):
        self._canvas.itemconfigure(self._window, width=event.width)
        self._on_body()

    def _on_wheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, KeyError):
            widget = None
        node = widget
        while node is not None:
            if node is self:
                self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            node = getattr(node, "master", None)
        return None

    def scroll_units(self, units):
        """Scroll the content by *units* (positive scrolls down)."""
        self._canvas.yview_scroll(units, "units")

    def scroll_to_top(self):
        self._canvas.yview_moveto(0.0)


# ---------------------------------------------------------------------------
# Bentley-integrated dialog base classes
# ---------------------------------------------------------------------------

class BentleyTk(tk.Tk):
    """Tk toplevel driven by MicroStation's persistent Python loop.

    ``ATTACH_TO_HOST`` controls whether the window is registered as
    MicroStation's tool-settings window via ``AttachTkinterToolSetting``.  That
    call reparents the Tk window into the tool-settings container, which then
    owns its position (breaking "remember last position"), so it defaults to
    off: the dialog stays a normal top-level window.

    ``ALWAYS_ON_TOP`` keeps the palette above the model.  Minimising it is never
    undone, so the user can always tuck it away.
    """

    ATTACH_TO_HOST = False
    ALWAYS_ON_TOP = True

    def __init__(self):
        tk.Tk.__init__(self)
        self._applying_position = False
        self._position_jobs = []
        if self.ALWAYS_ON_TOP:
            try:
                self.attributes("-topmost", True)
            except tk.TclError:
                pass

    def on_attached_to_bentley(self):
        """Hook run once the dialog is attached to the MicroStation host."""

    def run_bentley_loop(self):
        from MSPyMstnPlatform import PyCadInputQueue
        attached = False
        while tk._default_root is not None:
            try:
                self.update_idletasks()
                self.update()
            except tk.TclError:
                break
            try:
                if not win32gui.IsWindow(self.winfo_id()):
                    break
                if not attached:
                    host_frame = win32gui.GetParent(self.winfo_id())
                    if host_frame:
                        if self.ATTACH_TO_HOST:
                            PyCadInputQueue.AttachTkinterToolSetting(host_frame)
                        attached = True
                        try:
                            self.on_attached_to_bentley()
                        except Exception:
                            pass
            except tk.TclError:
                break
            PyCadInputQueue.PythonMainLoop()


class GlassDialog(BentleyTk):
    """A styled dialog that remembers its window position and user state.

    Subclasses set :attr:`STATE_KEY`, call :meth:`build_shell`, and override
    :meth:`restore_state` / :meth:`persist_state`.  Window position and all keys
    of :attr:`ui_state` are written to ``ui_state.json`` under
    ``%LOCALAPPDATA%/BentleyPythonPlugins/<STATE_KEY>/``.
    """

    STATE_KEY = "glass_dialog"

    def __init__(self, title="", state_key=None):
        BentleyTk.__init__(self)
        if state_key:
            self.STATE_KEY = state_key
        self.ui_state = load_ui_state(self.STATE_KEY)
        self.title(title)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.configure(bg=BG)
        self.apply_glass_style()

    # -- styling ------------------------------------------------------------
    def apply_glass_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Card.TFrame", background=CARD)
        style.configure("Glass.TLabel", background=CARD, foreground=INK, font=UI_FONT)
        style.configure("GlassMuted.TLabel", background=CARD, foreground=MUTED,
                        font=UI_FONT)
        style.configure("Section.TLabel", background=CARD, foreground=MUTED,
                        font=UI_FONT_SMALL)
        style.configure("TSeparator", background=BORDER)
        style.configure("Glass.TCombobox", font=UI_FONT, padding=(8, 5),
                        fieldbackground=FIELD, background=CARD,
                        foreground=INK, bordercolor=BORDER, lightcolor=FIELD,
                        darkcolor="#CBD5E1", arrowsize=15)
        style.map("Glass.TCombobox",
                  fieldbackground=[("readonly", FIELD), ("active", CARD)],
                  bordercolor=[("active", "#9FB4CC"), ("focus", "#9FB4CC")],
                  lightcolor=[("active", "#9FB4CC")],
                  arrowcolor=[("active", INK), ("!active", "#93A1B5")],
                  selectbackground=[("readonly", "#F0F5FA")],
                  selectforeground=[("readonly", INK)])
        style.configure("Glass.Treeview", background=CARD, fieldbackground=CARD,
                        foreground=INK, borderwidth=0, rowheight=24, font=UI_FONT)
        style.configure("Glass.Treeview.Heading", background=CARD_SOFT,
                        foreground=MUTED, relief="flat", font=UI_FONT_SMALL)
        style.map("Glass.Treeview",
                  background=[("selected", "#E8F0F9")],
                  foreground=[("selected", INK)])
        style.map("Glass.Treeview.Heading",
                  background=[("active", CARD_SOFT)])

    def build_shell(self, title, subtitle=""):
        """Build the header + white card and return the inner ttk form frame."""
        shell = tk.Frame(self, bg=BG, padx=14, pady=14)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=BG)
        header.pack(fill="x", pady=(0, 12))
        title_row = tk.Frame(header, bg=BG)
        title_row.pack(anchor="w")
        dot = tk.Canvas(title_row, width=10, height=10, bg=BG,
                        highlightthickness=0, bd=0)
        dot.create_oval(1, 1, 9, 9, fill=ACCENT, outline="")
        dot.pack(side="left", pady=(8, 0), padx=(0, 8))
        tk.Label(title_row, text=title, bg=BG, fg=INK,
                 font=UI_FONT_TITLE).pack(side="left")
        if subtitle:
            tk.Label(header, text=subtitle, bg=BG, fg=MUTED,
                     font=UI_FONT_SMALL).pack(anchor="w", pady=(4, 0), padx=(18, 0))

        card_frame = tk.Frame(shell, bg=CARD, highlightbackground=BORDER,
                              highlightthickness=1)
        card_frame.pack(fill="both", expand=True)
        form = ttk.Frame(card_frame, style="Card.TFrame", padding=14)
        form.pack(fill="both", expand=True)
        return form

    def make_status_chip(self, parent, textvariable, wraplength=290):
        chip = tk.Frame(parent, bg=CARD_SOFT, highlightbackground=BORDER,
                        highlightthickness=1)
        tk.Label(chip, textvariable=textvariable, bg=CARD_SOFT, fg="#1f5f99",
                 font=UI_FONT_SMALL, wraplength=wraplength,
                 justify="left").pack(anchor="w", padx=12, pady=8)
        return chip

    # -- window position memory --------------------------------------------
    def restore_position(self):
        self._apply_saved_position()

    def on_attached_to_bentley(self):
        # Position once at startup and stop.  A user move raises <Configure>,
        # which cancels the remaining startup passes so we never fight the
        # pointer.
        for delay in (0, 150, 400):
            self._position_jobs.append(
                self.after(delay, self._apply_saved_position)
            )
        self.bind("<Configure>", self._on_configure, add="+")

    def _apply_saved_position(self):
        x = self.ui_state.get("window_x")
        y = self.ui_state.get("window_y")
        if not isinstance(x, int) or not isinstance(y, int):
            return
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, min(x, max(0, screen_w - 80)))
        y = max(0, min(y, max(0, screen_h - 80)))
        self._applying_position = True
        try:
            self.update_idletasks()
            self.geometry("+%d+%d" % (x, y))
            # If MicroStation handed our window to a native parent, nudge it
            # there too so the position holds for either window kind.
            try:
                handle = self.winfo_id()
                parent = win32gui.GetParent(handle)
                if parent and (
                    win32gui.GetWindowLong(handle, win32con.GWL_STYLE)
                    & win32con.WS_CHILD
                ):
                    client = win32gui.ScreenToClient(parent, (x, y))
                    win32gui.SetWindowPos(
                        handle, 0, client[0], client[1], 0, 0,
                        win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                        | win32con.SWP_NOACTIVATE,
                    )
            except Exception:
                pass
            try:
                self.update_idletasks()
            except tk.TclError:
                pass
        except tk.TclError:
            pass
        finally:
            self._applying_position = False

    def _cancel_position_jobs(self):
        for job in self._position_jobs:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._position_jobs = []

    def _on_configure(self, event):
        if event.widget is not self or self._applying_position:
            return
        self._cancel_position_jobs()

    def _persist_position(self):
        try:
            self.update_idletasks()
            self.ui_state["window_x"] = int(self.winfo_rootx())
            self.ui_state["window_y"] = int(self.winfo_rooty())
        except tk.TclError:
            pass

    # -- state hooks / lifecycle -------------------------------------------
    def restore_state(self):
        """Subclass hook: read :attr:`ui_state` after the widgets exist."""

    def persist_state(self, state):
        """Subclass hook: add custom keys to *state* before it is written."""

    def destroy(self):
        self._persist_position()
        try:
            self.persist_state(self.ui_state)
            save_ui_state(self.STATE_KEY, self.ui_state)
        except Exception:
            pass
        BentleyTk.destroy(self)
