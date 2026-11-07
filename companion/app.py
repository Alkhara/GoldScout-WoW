"""GoldScout Companion: shares your GoldScout drop data without copy and paste.

It finds WoW Forever, reads the export GoldScout saved, checks it with the
same validator the GoldScout data bot uses, and opens the Share drop data form
with your export filled in. It only reads game files and never changes them.

Run:  python companion/app.py
"""
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

VERSION = "0.3.0"
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


def file_stamp(forever):
    files = savedvars.saved_variables_files(forever) if forever else []
    return tuple((str(f), f.stat().st_mtime) for f in files)


class App:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.accounts = []
        self.account = None
        self.result = None
        self.stamp = None
        root.title("GoldScout Companion")
        root.minsize(540, 400)

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="GoldScout Companion", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Share the drop rates GoldScout learned from your loot.",
                  foreground="#555").grid(row=1, column=0, sticky="w", pady=(0, 12))

        folder = ttk.LabelFrame(frame, text="WoW Forever folder", padding=8)
        folder.grid(row=2, column=0, sticky="ew")
        folder.columnconfigure(0, weight=1)
        self.folder_label = ttk.Label(folder, text="", wraplength=400)
        self.folder_label.grid(row=0, column=0, sticky="w")
        ttk.Button(folder, text="Change...", command=self.choose_folder).grid(row=0, column=1, padx=(8, 0))

        data = ttk.LabelFrame(frame, text="Your data", padding=8)
        data.grid(row=3, column=0, sticky="nsew", pady=12)
        data.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)
        self.account_label = ttk.Label(data, text="WoW account:")
        self.account_choice = ttk.Combobox(data, state="readonly", width=24)
        self.account_choice.bind("<<ComboboxSelected>>", lambda _: self.show_account())
        self.stats_label = ttk.Label(data, text="", font=("Segoe UI", 10, "bold"))
        self.stats_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.since_label = ttk.Label(data, text="")
        self.since_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 6))
        self.notes = tk.Text(data, height=7, wrap="word", relief="flat", background=root.cget("background"),
                             font=("Segoe UI", 9))
        self.notes.grid(row=3, column=0, columnspan=2, sticky="nsew")
        data.rowconfigure(3, weight=1)

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, sticky="ew")
        self.share_button = ttk.Button(buttons, text="Share on GitHub", command=self.share)
        self.share_button.pack(side="left")
        self.copy_button = ttk.Button(buttons, text="Copy export", command=self.copy)
        self.copy_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left")

        ttk.Label(frame, foreground="#777", wraplength=500, font=("Segoe UI", 8),
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
        if self.forever and file_stamp(self.forever) != self.stamp:
            self.refresh()
        self.root.after(POLL_MS, self.poll)

    def set_notes(self, lines):
        self.notes.configure(state="normal")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", "\n".join(lines))
        self.notes.configure(state="disabled")

    def set_status(self, stats, since="", notes=(), can_share=False):
        self.stats_label.configure(text=stats)
        self.since_label.configure(text=since)
        self.set_notes(list(notes))
        state = "normal" if can_share else "disabled"
        self.share_button.configure(state=state)
        self.copy_button.configure(state=state)

    def refresh(self):
        self.folder_label.configure(text=str(self.forever) if self.forever else
                                    "Not found. Click Change... and choose your World of Warcraft folder.")
        self.stamp = file_stamp(self.forever)
        self.accounts, error = [], None
        if self.forever:
            try:
                self.accounts = savedvars.read_accounts(self.forever)
            except (OSError, savedvars.LuaError) as problem:
                error = "Couldn't read GoldScout's saved data: %s" % problem
        names = [account.name for account in self.accounts]
        if len(names) > 1:
            previous = self.account_choice.get()
            self.account_choice.configure(values=names)
            self.account_choice.set(previous if previous in names else names[0])
            self.account_label.grid(row=0, column=0, sticky="w", pady=(0, 6))
            self.account_choice.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=(0, 6))
        else:
            self.account_label.grid_remove()
            self.account_choice.grid_remove()
        if not self.forever:
            self.set_status("No WoW Forever folder yet")
        elif error:
            self.set_status("Saved data couldn't be read", notes=[error])
        elif not self.accounts:
            self.set_status("No GoldScout data yet",
                            notes=["Install GoldScout, loot some mobs, then log out or type /reload."])
        else:
            self.show_account()

    def show_account(self):
        chosen = self.account_choice.get() if len(self.accounts) > 1 else self.accounts[0].name
        self.account = next(a for a in self.accounts if a.name == chosen)
        account, self.result = self.account, None
        if not account.export:
            notes = ["Loot some mobs with GoldScout installed, then log out or type /reload."]
            if account.has_loot:
                notes = ["GoldScout has loot data, but no export saved yet. Update GoldScout to the latest "
                         "version, log in, then log out or type /reload once."]
            self.set_status("Nothing to share yet", notes=notes)
            return
        self.result = submission.parse(account.export)
        if self.result.errors:
            self.set_status("This export can't be shared as it is",
                            notes=["The GoldScout data bot would reject it:"] +
                                  ["  " + error for error in self.result.errors])
            return
        kills = sum(mob.k for mob in self.result.mobs)
        picks = sum(mob.p for mob in self.result.mobs)
        drops = sum(d for mob in self.result.mobs for d, _ in list(mob.i.values()) + list(mob.pi.values()))
        self.set_status(
            "%d mobs   ·   %d kills   ·   %d pickpockets   ·   %d item drops" % (
                len(self.result.mobs), kills, picks, drops),
            since=self.since_text(kills + picks),
            notes=["Ready to share. Your export passed every check the GoldScout data bot runs."],
            can_share=True)

    def since_text(self, attempts):
        last = self.config.get("shared", {}).get(self.account.install_id or "")
        if not last:
            return "You haven't shared this data from this PC yet."
        when = time.strftime("%b %d, %H:%M", time.localtime(last["time"]))
        if last.get("seq") == self.account.seq:
            return "Shared %s; nothing new since." % when
        more = attempts - last.get("attempts", 0)
        if more > 0:
            return "%d more kills and pickpockets since you last shared. Share again!" % more
        return "Your data changed since you last shared on %s." % when

    # -- sharing --------------------------------------------------------------
    def copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.account.export)
        self.root.update()

    def share(self):
        self.copy()
        url = share_url(self.account.export)
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
        attempts = sum(mob.k + mob.p for mob in self.result.mobs)
        self.config.setdefault("shared", {})[self.account.install_id or ""] = {
            "time": time.time(), "seq": self.account.seq, "attempts": attempts}
        save_config(self.config)
        self.since_label.configure(text=self.since_text(attempts))


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
