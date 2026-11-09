"""Windows integration: starting with Windows, keeping one copy running, and
telling whether World of Warcraft is open."""
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "GoldScout Companion"
# Every WoW client's process (Forever and retail are Wow.exe): the companion
# never shows a notification while any of them is running.
GAME_PROCESSES = frozenset({"wow.exe", "wowt.exe", "wowb.exe", "wow-64.exe",
                            "wowclassic.exe", "wowclassict.exe", "wowclassicb.exe"})


def running_process_names():
    """Lower-case exe names of every running process (empty off Windows or on error)."""
    if sys.platform != "win32":
        return set()
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


def game_running(names=None):
    """True while any World of Warcraft client is running."""
    return bool((running_process_names() if names is None else names) & GAME_PROCESSES)


def can_start_with_windows():
    """Only the packaged exe can register itself; running from source can't."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)


def startup_command():
    return '"%s" --tray' % sys.executable


def start_with_windows_enabled():
    if not can_start_with_windows():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value = winreg.QueryValueEx(key, RUN_NAME)[0]
        return value == startup_command()
    except OSError:
        return False


def set_start_with_windows(enabled):
    """Adds or removes the companion from this user's startup programs."""
    if not can_start_with_windows():
        return False
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


class SingleInstance:
    """Keeps one copy running. The first copy holds a named Windows mutex. A
    later copy can't take it, so it leaves a "show" request file for the first
    copy (which checks every second) and exits."""

    MUTEX_NAME = r"Local\GoldScoutCompanion"

    def __init__(self, signal_path):
        self.signal_path = signal_path
        self.handle = None

    def claim(self, signal=True):
        """True if this copy now holds the mutex. Otherwise, with signal, asks the
        running copy to show its window."""
        if sys.platform != "win32":
            return True
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, self.MUTEX_NAME)
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            if handle:
                kernel32.CloseHandle(ctypes.c_void_p(handle))  # don't keep the other copy's mutex alive
            if signal:
                try:
                    self.signal_path.parent.mkdir(parents=True, exist_ok=True)
                    self.signal_path.write_text("show", encoding="utf-8")
                except OSError:
                    pass
            return False
        self.handle = handle
        return True

    def claim_when_free(self, seconds):
        """For a copy started by an update: waits for the old copy to let go."""
        import time
        deadline = time.time() + seconds
        while not self.claim(signal=False):
            if time.time() > deadline:
                return False
            time.sleep(0.25)
        return True

    @classmethod
    def other_running(cls):
        """True when some copy holds the mutex (opens it without creating it)."""
        if sys.platform != "win32":
            return False
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenMutexW.restype = ctypes.c_void_p
        handle = kernel32.OpenMutexW(0x00100000, False, cls.MUTEX_NAME)  # SYNCHRONIZE
        if not handle:
            return False
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return True

    def show_requested(self):
        """True once for each request a later launch left."""
        try:
            self.signal_path.unlink()
            return True
        except OSError:
            return False

    def close(self):
        if self.handle:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.handle))
            self.handle = None
