"""Light and dark colors for GoldScout Companion's windows.

On Windows the window follows Windows' app mode (Settings > Personalization >
Colors > Choose your default app mode) and switches when you change it, title
bar included. Light keeps Windows' own "vista" look; dark draws the same
widgets with the "clam" theme in dark colors, since the vista theme can't be
recolored. On a Mac, Tk follows the Mac's appearance by itself; the muted,
faint and link text use macOS's own colors so they show in both.
"""
import ctypes
import tkinter as tk
from tkinter import ttk

import system

CHECK_MS = 3000  # how often to look at Windows' app mode

# Named label styles for secondary text, so a change of theme recolors them.
MUTED, FAINT, LINK = "Muted.TLabel", "Faint.TLabel", "Link.TLabel"
INK_STYLES = {"muted": MUTED, "faint": FAINT, "link": LINK}
MAC_INKS = {"muted": "systemSecondaryLabelColor", "faint": "systemTertiaryLabelColor", "link": "systemLinkColor"}
LIGHT_INKS = {"muted": "#555", "faint": "#777", "link": "#1a5fb4"}

# Windows 11's dark app colors, roughly.
DARK = {
    "bg": "#202020", "fg": "#e8e8e8", "field": "#2b2b2b", "button": "#333333", "active": "#3d3d3d",
    "pressed": "#474747", "border": "#4d4d4d", "disabled": "#7d7d7d", "select": "#2f6fb3",
    "muted": "#b0b0b0", "faint": "#8c8c8c", "link": "#6cb6ff",
}

_current = None


def windows_dark():
    """True when Windows' default app mode is Dark."""
    if not system.WINDOWS:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except (OSError, ImportError):
        return False


def title_bar(window, dark):
    """Windows 10 (20H1+) and 11: a dark or light title bar for one window."""
    if not system.WINDOWS:
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, and its number before Windows 10 20H1
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value),
                                                         ctypes.sizeof(value)) == 0:
                break
        # Redraw the frame now rather than at the next resize.
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
    except (AttributeError, OSError, tk.TclError):
        pass


class Theme:
    def __init__(self, root, watch=True):
        self.root = root
        self.style = ttk.Style(root)
        self.light_bg = root.cget("background")
        self.windows, self.texts, self.combos = [root], [], []
        self.dark = None
        self.apply()
        if watch and system.WINDOWS:
            root.after(CHECK_MS, self.check)

    # -- what follows the theme ----------------------------------------------
    def window(self, window):
        """A Toplevel: its background and title bar follow the theme."""
        self.windows.append(window)
        self.paint_window(window)

    def text(self, widget):
        """A tk.Text: drawn like the window's background, with the theme's text color."""
        self.texts.append(widget)
        self.paint_text(widget)

    def combo(self, widget):
        """A ttk.Combobox: its drop-down list follows the theme."""
        self.combos.append(widget)
        self.paint_combo(widget)

    # -- switching -----------------------------------------------------------
    def check(self):
        self.apply()
        self.root.after(CHECK_MS, self.check)

    def apply(self, dark=None):
        dark = windows_dark() if dark is None else dark
        if dark == self.dark:
            return
        self.dark = dark
        if system.WINDOWS:
            self.dark_styles() if dark else self.light_styles()
        else:
            self.ink_styles(MAC_INKS if system.MAC else LIGHT_INKS)
        self.windows = [w for w in self.windows if self.alive(w)]
        self.texts = [t for t in self.texts if self.alive(t)]
        self.combos = [c for c in self.combos if self.alive(c)]
        for window in self.windows:
            self.paint_window(window)
        for widget in self.texts:
            self.paint_text(widget)
        for widget in self.combos:
            self.paint_combo(widget)

    @staticmethod
    def alive(widget):
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def ink_styles(self, inks):
        for name, style in INK_STYLES.items():
            color = inks[name]
            try:
                self.root.winfo_rgb(color)  # older Tk lacks some of macOS's colors
            except tk.TclError:
                color = LIGHT_INKS[name]
            self.style.configure(style, foreground=color)

    def light_styles(self):
        try:
            self.style.theme_use("vista")
        except tk.TclError:
            pass
        self.ink_styles(LIGHT_INKS)
        self.root.option_add("*TCombobox*Listbox.background", "SystemWindow")
        self.root.option_add("*TCombobox*Listbox.foreground", "SystemWindowText")
        self.root.option_add("*TCombobox*Listbox.selectBackground", "SystemHighlight")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "SystemHighlightText")

    def dark_styles(self):
        c, s = DARK, self.style
        s.theme_use("clam")
        s.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["field"],
                    bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"], troughcolor=c["field"],
                    selectbackground=c["select"], selectforeground="#ffffff", insertcolor=c["fg"],
                    focuscolor=c["border"])
        s.map(".", foreground=[("disabled", c["disabled"])])
        s.configure("TButton", background=c["button"], lightcolor=c["button"], darkcolor=c["button"],
                    bordercolor=c["border"], padding=(10, 3))
        s.map("TButton", background=[("pressed", c["pressed"]), ("active", c["active"])],
              lightcolor=[("pressed", c["pressed"]), ("active", c["active"])],
              darkcolor=[("pressed", c["pressed"]), ("active", c["active"])],
              foreground=[("disabled", c["disabled"])])
        s.configure("TCheckbutton", indicatorbackground=c["field"], indicatorforeground=c["fg"],
                    upperbordercolor=c["border"], lowerbordercolor=c["border"])
        s.map("TCheckbutton", background=[("active", c["bg"])],
              indicatorbackground=[("pressed", c["active"]), ("disabled", c["bg"])],
              foreground=[("disabled", c["disabled"])])
        s.configure("TCombobox", background=c["button"], arrowcolor=c["fg"], foreground=c["fg"],
                    fieldbackground=c["field"])
        s.map("TCombobox", fieldbackground=[("readonly", c["field"])], foreground=[("readonly", c["fg"])],
              selectbackground=[("readonly", c["field"])], selectforeground=[("readonly", c["fg"])],
              background=[("active", c["active"])])
        s.configure("TEntry", fieldbackground=c["field"], foreground=c["fg"])
        s.map("TEntry", fieldbackground=[("disabled", c["bg"])])
        s.configure("TLabelframe", background=c["bg"], bordercolor=c["border"])
        s.configure("TLabelframe.Label", background=c["bg"], foreground=c["fg"])
        self.ink_styles(DARK)
        self.root.option_add("*TCombobox*Listbox.background", c["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["select"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    # -- painting one widget -------------------------------------------------
    def colors(self):
        if self.dark:
            return DARK["bg"], DARK["fg"], DARK["field"], DARK["select"]
        return self.light_bg, "SystemWindowText" if system.WINDOWS else "black", "SystemWindow", "SystemHighlight"

    def paint_window(self, window):
        bg = self.colors()[0]
        try:
            window.configure(background=bg)
        except tk.TclError:
            pass
        title_bar(window, bool(self.dark))

    def paint_text(self, widget):
        bg, fg, _, select = self.colors()
        try:
            widget.configure(background=bg, foreground=fg, insertbackground=fg, selectbackground=select,
                             highlightthickness=0, borderwidth=0)
        except tk.TclError:
            pass

    def paint_combo(self, widget):
        _, fg, field, select = self.colors()
        try:  # the drop-down list, once Tk has made it
            popdown = widget.tk.call("ttk::combobox::PopdownWindow", widget)
            widget.tk.call("%s.f.l" % popdown, "configure", "-background", field, "-foreground", fg,
                           "-selectbackground", select)
        except tk.TclError:
            pass


def install(root, watch=True):
    """Sets up the theme for the companion's main window; window(), text() and combo() use it."""
    global _current
    _current = Theme(root, watch)
    return _current


def window(toplevel):
    if _current:
        _current.window(toplevel)


def text(widget):
    if _current:
        _current.text(widget)


def combo(widget):
    if _current:
        _current.combo(widget)
