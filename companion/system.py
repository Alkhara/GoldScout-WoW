"""System integration on Windows and macOS: where settings live, starting at
login, keeping one copy running, telling whether World of Warcraft is open,
and the one update notification.

Windows: the Run registry key, a named mutex, Toolhelp32, the tray icon.
macOS: a LaunchAgent in ~/Library/LaunchAgents, a lock file, `ps`, and a
Notification Center message via osascript. There's no tray icon on macOS; the
companion keeps running in the Dock when its window is closed.
"""
import os
import plistlib
import subprocess
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "GoldScout Companion"
AGENT_LABEL = "com.wowgoldscout.companion"
APP_NAME = "GoldScout Companion"   # the macOS app bundle's name, without .app

# Every WoW client's process (Forever and retail are Wow.exe): the companion
# never shows a notification while any of them is running. On macOS every
# client's process name starts with "World of Warcraft".
GAME_PROCESSES = frozenset({"wow.exe", "wowt.exe", "wowb.exe", "wow-64.exe",
                            "wowclassic.exe", "wowclassict.exe", "wowclassicb.exe"})
MAC_GAME_PREFIX = "world of warcraft"

STARTUP_LABEL = "Open at login" if MAC else "Start with Windows"


def config_dir():
    """Where the companion keeps its settings."""
    if MAC:
        return Path.home() / "Library" / "Application Support" / "GoldScout Companion"
    return Path(os.environ.get("APPDATA", Path.home())) / "GoldScout Companion"


def packaged():
    """True for the released app (PyInstaller), False when run from source."""
    return bool(getattr(sys, "frozen", False)) and (WINDOWS or MAC)


def installed_path(executable=None):
    """What an update replaces: the exe on Windows, the .app bundle on macOS
    (its program is GoldScout Companion.app/Contents/MacOS/GoldScout Companion)."""
    exe = Path(executable or sys.executable)
    if MAC and len(exe.parents) >= 3 and exe.parents[2].suffix == ".app":
        return exe.parents[2]
    return exe


# ---------------------------------------------------------------------------
# Is World of Warcraft running?
# ---------------------------------------------------------------------------
def _windows_process_names():
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessEntry)]
    kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessEntry)]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return set()
    names = set()
    entry = ProcessEntry()
    entry.dwSize = ctypes.sizeof(ProcessEntry)
    try:
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            names.add(entry.szExeFile.lower())
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return names


def parse_ps(text):
    """Lower-case program names from `ps -axo comm=` (one path per line)."""
    return {line.strip().rsplit("/", 1)[-1].lower() for line in text.splitlines() if line.strip()}


def _ps_process_names(run=subprocess.run):
    try:
        result = run(["ps", "-axo", "comm="], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return set()
    return parse_ps(result.stdout or "")


def running_process_names():
    """Lower-case program names of every running process (empty on error)."""
    if WINDOWS:
        return _windows_process_names()
    return _ps_process_names()


def game_running(names=None):
    """True while any World of Warcraft client is running."""
    names = running_process_names() if names is None else names
    return bool(names & GAME_PROCESSES) or any(name.startswith(MAC_GAME_PREFIX) for name in names)


# ---------------------------------------------------------------------------
# Starting at login
# ---------------------------------------------------------------------------
def can_start_at_login():
    """Only the packaged app can register itself; running from source can't."""
    return packaged()


def startup_command():
    return '"%s" --tray' % sys.executable


def agent_path(home=None):
    return Path(home or Path.home()) / "Library" / "LaunchAgents" / (AGENT_LABEL + ".plist")


def agent_plist(bundle):
    """The LaunchAgent: at login, open the app in the background (-g) with its window hidden."""
    return {"Label": AGENT_LABEL,
            "ProgramArguments": ["/usr/bin/open", "-g", "-a", str(bundle), "--args", "--tray"],
            "RunAtLoad": True}


def mac_agent_enabled(bundle, home=None):
    try:
        with open(agent_path(home), "rb") as handle:
            return plistlib.load(handle) == agent_plist(bundle)
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False


def set_mac_agent(enabled, bundle, home=None):
    path = agent_path(home)
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        with open(temp, "wb") as handle:
            plistlib.dump(agent_plist(bundle), handle)
        os.replace(temp, path)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def start_at_login_enabled():
    if not can_start_at_login():
        return False
    if MAC:
        return mac_agent_enabled(installed_path())
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value = winreg.QueryValueEx(key, RUN_NAME)[0]
        return value == startup_command()
    except OSError:
        return False


def set_start_at_login(enabled):
    """Adds or removes the companion from this user's login items."""
    if not can_start_at_login():
        return False
    if MAC:
        set_mac_agent(enabled, installed_path())
        return True
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass
    return True


# ---------------------------------------------------------------------------
# The update notification (macOS; Windows uses the tray icon's)
# ---------------------------------------------------------------------------
def applescript_string(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def notify(title, message, run=subprocess.run):
    """A Notification Center message on macOS. Returns True if it was shown."""
    if not MAC:
        return False
    script = "display notification %s with title %s" % (applescript_string(message), applescript_string(title))
    try:
        return run(["osascript", "-e", script], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------------------
# One copy at a time
# ---------------------------------------------------------------------------
class SingleInstance:
    """Keeps one copy running. The first copy holds a named Windows mutex (or,
    on macOS, a lock on a file next to the settings). A later copy can't take
    it, so it leaves a "show" request file for the first copy (which checks
    every second) and exits."""

    MUTEX_NAME = r"Local\GoldScoutCompanion"

    def __init__(self, signal_path):
        self.signal_path = Path(signal_path)
        self.lock_path = self.signal_path.with_name("instance.lock")
        self.handle = None

    def _take(self):
        """Takes the mutex or lock; True if this copy now holds it."""
        if WINDOWS:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            handle = kernel32.CreateMutexW(None, False, self.MUTEX_NAME)
            if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                if handle:
                    kernel32.CloseHandle(ctypes.c_void_p(handle))  # don't keep the other copy's mutex alive
                return False
            self.handle = handle
            return True
        import fcntl
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.lock_path, "a+")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def claim(self, signal=True):
        """True if this copy now holds the mutex. Otherwise, with signal, asks the
        running copy to show its window."""
        if not (WINDOWS or MAC):
            return True
        if self.handle:
            return True
        if self._take():
            return True
        if signal:
            try:
                self.signal_path.parent.mkdir(parents=True, exist_ok=True)
                self.signal_path.write_text("show", encoding="utf-8")
            except OSError:
                pass
        return False

    def claim_when_free(self, seconds):
        """For a copy started by an update: waits for the old copy to let go."""
        import time
        deadline = time.time() + seconds
        while not self.claim(signal=False):
            if time.time() > deadline:
                return False
            time.sleep(0.25)
        return True

    def other_running(self):
        """True when some other copy holds the mutex or lock (checked without keeping it)."""
        if WINDOWS:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenMutexW.restype = ctypes.c_void_p
            handle = kernel32.OpenMutexW(0x00100000, False, self.MUTEX_NAME)  # SYNCHRONIZE
            if not handle:
                return False
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            return True
        if not MAC or self.handle:
            return False
        import fcntl
        try:
            handle = open(self.lock_path, "a+")
        except OSError:
            return False
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        finally:
            handle.close()   # closing also releases a lock we just took
        return False

    def show_requested(self):
        """True once for each request a later launch left."""
        try:
            self.signal_path.unlink()
            return True
        except OSError:
            return False

    def close(self):
        if not self.handle:
            return
        if WINDOWS:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.handle))
        else:
            self.handle.close()
        self.handle = None
