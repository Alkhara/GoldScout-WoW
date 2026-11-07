"""GoldScout Companion: shares your GoldScout drop data without copy and paste.

It finds WoW Forever, reads the drop data GoldScout saved, checks it with the
same validator the GoldScout data bot uses, and opens the Share drop data form
with your export filled in. It only reads game files and never changes them.

Run:  python companion/app.py
"""
import hashlib
import json
import os
import sys
import time
import tkinter as tk
import urllib.parse
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "tools"))
import savedvars  # noqa: E402
import submission  # noqa: E402

VERSION = "0.1.0"
FORM_URL = "https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml"
MAX_URL = 7500           # longer links get cut off; then the export goes via the clipboard
POLL_MS = 15000          # how often to look for newer saved data
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "GoldScout Companion"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def share_url(export):
    return FORM_URL + "&" + urllib.parse.urlencode({"export": export.strip()})


class Snapshot:
    """What's in the saved data right now."""

    def __init__(self, forever):
        self.forever = forever
        self.files = savedvars.saved_variables_files(forever) if forever else []
        self.stamp = tuple((str(f), f.stat().st_mtime) for f in self.files)
        self.error = None
        self.mobs = {}
        try:
            self.mobs = savedvars.combine_drops(savedvars.read_drops(f) for f in self.files)
        except (OSError, savedvars.LuaError) as error:
            self.error = "Couldn't read GoldScout's saved data: %s" % error
        self.export = savedvars.export_text(self.mobs)
        self.result = submission.parse(self.export) if self.mobs else None
        self.kills = sum(m["k"] for m in self.mobs.values())
        self.picks = sum(m["p"] for m in self.mobs.values())
        self.drops = sum(d for m in self.mobs.values() for d, _ in list(m["i"].values()) + list(m["pi"].values()))
        self.digest = hashlib.sha256(self.export.encode("utf-8")).hexdigest()


class App:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.snapshot = None
        root.title("GoldScout Companion")
        root.minsize(520, 380)

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="GoldScout Companion", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Share the drop rates GoldScout learned from your loot.",
                  foreground="#555").grid(row=1, column=0, sticky="w", pady=(0, 12))

        folder = ttk.LabelFrame(frame, text="WoW Forever folder", padding=8)
        folder.grid(row=2, column=0, sticky="ew")
        folder.columnconfigure(0, weight=1)
        self.folder_label = ttk.Label(folder, text="", wraplength=380)
        self.folder_label.grid(row=0, column=0, sticky="w")
        ttk.Button(folder, text="Change...", command=self.choose_folder).grid(row=0, column=1, padx=(8, 0))

        data = ttk.LabelFrame(frame, text="Your data", padding=8)
        data.grid(row=3, column=0, sticky="nsew", pady=12)
        data.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        self.stats_label = ttk.Label(data, text="", font=("Segoe UI", 10, "bold"))
        self.stats_label.grid(row=0, column=0, sticky="w")
        self.since_label = ttk.Label(data, text="")
        self.since_label.grid(row=1, column=0, sticky="w", pady=(2, 6))
        self.notes = tk.Text(data, height=7, wrap="word", relief="flat", background=root.cget("background"),
                             font=("Segoe UI", 9))
        self.notes.grid(row=2, column=0, sticky="nsew")
        data.rowconfigure(2, weight=1)

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, sticky="ew")
        self.share_button = ttk.Button(buttons, text="Share on GitHub", command=self.share)
        self.share_button.pack(side="left")
        self.copy_button = ttk.Button(buttons, text="Copy export", command=self.copy)
        self.copy_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left")

        ttk.Label(frame, foreground="#777", wraplength=480, font=("Segoe UI", 8),
                  text="GoldScout saves its data when you log out or type /reload, so new loot shows up "
                       "here after that. The companion only reads your saved data; it never changes game "
                       "files. Companion " + VERSION).grid(row=5, column=0, sticky="w", pady=(12, 0))

        self.forever = self.find_folder()
        self.refresh()
        self.root.after(POLL_MS, self.poll)

    # -- folder ---------------------------------------------------------------
    def find_folder(self):
        saved = self.config.get("forever")
        if saved and Path(saved).is_dir():
            return Path(saved)
        found = savedvars.find_forever_folders()
        if found:
            self.remember_folder(found[0])
            return found[0]
        return None

    def remember_folder(self, forever):
        self.config["forever"] = str(forever)
        save_config(self.config)

    def choose_folder(self):
        picked = filedialog.askdirectory(title="Choose your World of Warcraft folder")
        if not picked:
            return
        forever = savedvars.normalize_wow_folder(picked)
        if not forever:
            messagebox.showerror("GoldScout Companion",
                                 "That folder doesn't contain WoW Forever (a _forever_ folder). "
                                 "Choose your World of Warcraft folder.")
            return
        self.forever = forever
        self.remember_folder(forever)
        self.refresh()

    # -- data -----------------------------------------------------------------
    def poll(self):
        if self.forever:
            files = savedvars.saved_variables_files(self.forever)
            stamp = tuple((str(f), f.stat().st_mtime) for f in files)
            if not self.snapshot or stamp != self.snapshot.stamp:
                self.refresh()
        self.root.after(POLL_MS, self.poll)

    def set_notes(self, lines):
        self.notes.configure(state="normal")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", "\n".join(lines))
        self.notes.configure(state="disabled")

    def refresh(self):
        self.folder_label.configure(text=str(self.forever) if self.forever else
                                    "Not found. Click Change... and choose your World of Warcraft folder.")
        self.snapshot = snap = Snapshot(self.forever)
        can_share = False
        if not self.forever:
            self.stats_label.configure(text="No WoW Forever folder yet")
            self.since_label.configure(text="")
            self.set_notes([])
        elif snap.error:
            self.stats_label.configure(text="Saved data couldn't be read")
            self.since_label.configure(text="")
            self.set_notes([snap.error])
        elif not snap.files:
            self.stats_label.configure(text="No GoldScout data yet")
            self.since_label.configure(text="")
            self.set_notes(["Install GoldScout, loot some mobs, then log out or type /reload."])
        elif not snap.mobs:
            self.stats_label.configure(text="Nothing learned yet")
            self.since_label.configure(text="")
            self.set_notes(["Loot some mobs with GoldScout installed, then log out or type /reload."])
        else:
            self.stats_label.configure(text="%d mobs   ·   %d kills   ·   %d pickpockets   ·   %d item drops" % (
                len(snap.mobs), snap.kills, snap.picks, snap.drops))
            self.since_label.configure(text=self.since_text(snap))
            notes = []
            if snap.result.errors:
                notes.append("Some data can't be shared as it is:")
                notes += ["  " + error for error in snap.result.errors]
            else:
                can_share = True
                notes.append("Ready to share. Your export passed every check the GoldScout data bot runs.")
            if len(snap.files) > 1:
                notes.append("Combines %d WoW accounts on this PC." % len(snap.files))
            self.set_notes(notes)
        state = "normal" if can_share else "disabled"
        self.share_button.configure(state=state)
        self.copy_button.configure(state=state)

    def since_text(self, snap):
        last = self.config.get("last_shared")
        if not last:
            return "You haven't shared from this PC yet."
        if last.get("digest") == snap.digest:
            return "Shared %s; nothing new since." % time.strftime("%b %d, %H:%M", time.localtime(last["time"]))
        more = snap.kills + snap.picks - last.get("kills", 0) - last.get("picks", 0)
        if more > 0:
            return "%d more kills and pickpockets since you last shared. Share again!" % more
        return "Your data changed since you last shared."

    # -- sharing --------------------------------------------------------------
    def copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.snapshot.export)
        self.root.update()

    def share(self):
        snap = self.snapshot
        self.copy()
        url = share_url(snap.export)
        if len(url) <= MAX_URL:
            webbrowser.open(url)
            messagebox.showinfo("GoldScout Companion",
                                "The Share drop data form is opening in your browser with your export filled "
                                "in. Tick the two boxes and press Create to share it.")
        else:
            webbrowser.open(FORM_URL)
            messagebox.showinfo("GoldScout Companion",
                                "Your export is too long to fill in automatically, so it's on your clipboard. "
                                "In the form that's opening, click the export box, press Ctrl+V, tick the two "
                                "boxes and press Create.")
        self.config["last_shared"] = {"time": time.time(), "digest": snap.digest,
                                      "kills": snap.kills, "picks": snap.picks}
        save_config(self.config)
        self.since_label.configure(text=self.since_text(snap))


def main():
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
