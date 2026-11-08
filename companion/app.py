"""GoldScout Companion: shares your GoldScout drop data automatically.

It lives in the system tray, finds WoW Forever, reads the export GoldScout
saves, checks it with the same validator the GoldScout data bot uses, and
uploads new snapshots once you've agreed to the Contributor Terms. It only
reads game files and never changes them, and it never shows notifications.

Run:  python companion/app.py          (--tray starts hidden in the tray)
"""
import argparse
import json
import os
import queue
import sys
import threading
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
import system  # noqa: E402
import updater  # noqa: E402
import uploader  # noqa: E402

VERSION = "0.6.2"  # tools/release.py checks this matches the tag
FORM_URL = "https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml"
TERMS_URL = "https://github.com/Alkhara/GoldScout-WoW/blob/main/docs/CONTRIBUTOR_TERMS.md"
PRIVACY_URL = "https://github.com/Alkhara/GoldScout-WoW/blob/main/docs/PRIVACY.md"
MAX_URL = 7500           # longer links get cut off; then the export goes via the clipboard
POLL_MS = 15000          # how often to look for newer saved data
RETRY_SECONDS = 300      # wait after a failed upload before trying again
FIRST_CHECK_MS = 30000   # first update check, after startup settles
CHECK_EVERY_MS = 6 * 3600 * 1000
HANDOVER_SECONDS = 25    # how long a new version gets to start before we roll back
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "GoldScout Companion"
CONFIG_FILE = CONFIG_DIR / "config.json"
SHOW_REQUEST = CONFIG_DIR / "show.request"


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


def link(parent, text, url):
    label = ttk.Label(parent, text=text, foreground="#1a5fb4", cursor="hand2")
    label.bind("<Button-1>", lambda _: webbrowser.open(url))
    return label


class App:
    def __init__(self, root, start_hidden, instance=None, updated=False):
        self.root = root
        self.instance = instance
        self.config = load_config()
        self.events = queue.Queue()  # work handed to the Tk thread from other threads
        self.accounts, self.account, self.result, self.stamp = [], None, None, None
        self.uploading = False
        self.tray = None
        self.update, self.updating = None, False

        root.title("GoldScout Companion")
        root.minsize(560, 420)
        try:
            root.iconbitmap(str(HERE / "icon.ico"))
        except tk.TclError:
            pass
        root.protocol("WM_DELETE_WINDOW", self.hide)

        self.welcome = self.build_welcome()
        self.main = self.build_main()
        self.forever = self.find_folder()

        if self.has_consent() or self.config.get("declined"):
            self.show_main()
        else:
            self.show_welcome()
            start_hidden = False  # first run always shows the window
        if start_hidden:
            root.withdraw()

        self.start_tray()
        self.refresh()
        self.root.after(200, self.pump)
        self.root.after(POLL_MS, self.poll)
        if updated:
            self.set_update_text("Updated to %s." % VERSION)
        self.clean_up_updates(30)
        if self.can_update():
            self.root.after(FIRST_CHECK_MS, self.check_updates)

    # -- consent and settings -------------------------------------------------
    def has_consent(self):
        return self.config.get("consent", {}).get("version") == uploader.TERMS_VERSION

    def auto_share(self):
        return self.has_consent() and self.config.get("auto_share", True) and bool(uploader.upload_url())

    def set_auto_share(self, enabled):
        if enabled and not self.has_consent():
            self.show()
            self.show_welcome()
            return
        self.config["auto_share"] = enabled
        save_config(self.config)
        self.update_tray()
        self.update_share_status()
        if enabled:
            self.maybe_upload()

    def set_start_with_windows(self, enabled):
        try:
            system.set_start_with_windows(enabled)
        except OSError as error:
            messagebox.showerror("GoldScout Companion", "Couldn't change the startup setting: %s" % error)
        self.update_tray()

    # -- layout ---------------------------------------------------------------
    def build_welcome(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Welcome to GoldScout Companion", font=("Segoe UI", 15, "bold")).grid(sticky="w")
        ttk.Label(frame, wraplength=500, justify="left", text=(
            "GoldScout learns drop rates from your loot. The companion shares what it learns so the "
            "Farm tab gets better for everyone, and it does it automatically: it runs quietly in the "
            "system tray and uploads new data after you log out or /reload.\n\n"
            "What's shared: creature and item IDs and names, kill and drop counts, mob levels, where "
            "you looted, and which items your professions can make, plus a random ID for your "
            "GoldScout data. Never character, account or realm names. It only reads GoldScout's "
            "saved data and never changes game files.")
        ).grid(sticky="w", pady=(10, 10))
        links = ttk.Frame(frame)
        links.grid(sticky="w")
        link(links, "Contributor Terms", TERMS_URL).pack(side="left")
        ttk.Label(links, text="  ·  ").pack(side="left")
        link(links, "Privacy Policy", PRIVACY_URL).pack(side="left")

        self.startup_choice = tk.BooleanVar(value=True)
        startup = ttk.Checkbutton(frame, text="Start with Windows (in the tray)", variable=self.startup_choice)
        startup.grid(sticky="w", pady=(14, 0))
        if not system.can_start_with_windows():
            startup.state(["disabled"])
            self.startup_choice.set(False)

        ttk.Label(frame, foreground="#555", wraplength=500, justify="left", text=(
            "You can turn off automatic sharing or starting with Windows any time from the tray icon.")
        ).grid(sticky="w", pady=(10, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(sticky="w", pady=(16, 0))
        ttk.Button(buttons, text="I agree, share automatically", command=self.accept).pack(side="left")
        ttk.Button(buttons, text="Not now", command=self.decline).pack(side="left", padx=8)
        return frame

    def build_main(self):
        root = self.root
        frame = ttk.Frame(root, padding=16)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="GoldScout Companion", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        bar = ttk.Frame(frame)
        bar.grid(row=0, column=0, sticky="e")
        self.update_label = ttk.Label(bar, text="", foreground="#555")
        self.update_label.pack(side="left")
        self.update_button = ttk.Button(bar, text="Update", command=self.start_update)
        self.share_status = ttk.Label(frame, text="", foreground="#555")
        self.share_status.grid(row=1, column=0, sticky="w", pady=(0, 12))

        folder = ttk.LabelFrame(frame, text="WoW Forever folder", padding=8)
        folder.grid(row=2, column=0, sticky="ew")
        folder.columnconfigure(0, weight=1)
        self.folder_label = ttk.Label(folder, text="", wraplength=420)
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
        self.notes = tk.Text(data, height=6, wrap="word", relief="flat", background=root.cget("background"),
                             font=("Segoe UI", 9))
        self.notes.grid(row=3, column=0, columnspan=2, sticky="nsew")
        data.rowconfigure(3, weight=1)

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, sticky="ew")
        self.share_button = ttk.Button(buttons, text="Share now", command=self.share_now)
        self.share_button.pack(side="left")
        self.copy_button = ttk.Button(buttons, text="Copy export", command=self.copy)
        self.copy_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left")

        ttk.Label(frame, foreground="#777", wraplength=520, font=("Segoe UI", 8), text=(
            "Closing this window keeps the companion running in the system tray. GoldScout saves its "
            "data when you log out or type /reload, so new loot shows up here after that. "
            "Companion " + VERSION)).grid(row=5, column=0, sticky="w", pady=(12, 0))
        return frame

    def show_welcome(self):
        self.main.pack_forget()
        self.welcome.pack(fill="both", expand=True)

    def show_main(self):
        self.welcome.pack_forget()
        self.main.pack(fill="both", expand=True)

    def accept(self):
        self.config["consent"] = {"version": uploader.TERMS_VERSION, "time": time.time()}
        self.config["auto_share"] = True
        self.config.pop("declined", None)
        save_config(self.config)
        if system.can_start_with_windows():
            self.set_start_with_windows(self.startup_choice.get())
        self.show_main()
        self.update_tray()
        self.refresh()

    def decline(self):
        self.config["declined"] = True
        save_config(self.config)
        self.show_main()
        self.update_tray()
        self.refresh()

    # -- window and tray ------------------------------------------------------
    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self):
        self.root.withdraw()

    def quit(self):
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    def start_tray(self):
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return  # no tray support; closing the window then just hides it
        menu = pystray.Menu(
            pystray.MenuItem("Open GoldScout Companion", lambda: self.events.put(self.show), default=True),
            pystray.MenuItem("Share automatically", lambda: self.events.put(
                lambda: self.set_auto_share(not self.auto_share())), checked=lambda _: self.auto_share()),
            pystray.MenuItem("Start with Windows", lambda: self.events.put(
                lambda: self.set_start_with_windows(not system.start_with_windows_enabled())),
                checked=lambda _: system.start_with_windows_enabled(),
                enabled=lambda _: system.can_start_with_windows()),
            pystray.MenuItem(lambda _: "Update to %s" % (self.update.version if self.update else ""),
                             lambda: self.events.put(self.start_update),
                             visible=lambda _: bool(self.update) and not self.updating),
            pystray.MenuItem("Check for updates", lambda: self.events.put(lambda: self.check_updates(manual=True)),
                             visible=lambda _: self.can_update() and not self.update and not self.updating),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.events.put(self.quit)),
        )
        self.tray = pystray.Icon("GoldScoutCompanion", Image.open(HERE / "icon.png"), "GoldScout Companion", menu)
        self.tray.run_detached()

    def update_tray(self):
        if self.tray:
            self.tray.update_menu()

    def pump(self):
        """Runs work queued by the tray, uploads and the second-launch listener."""
        while True:
            try:
                job = self.events.get_nowait()
            except queue.Empty:
                break
            job()
        if self.instance and self.instance.show_requested():
            self.show()
        try:
            self.root.after(200, self.pump)
        except tk.TclError:
            pass  # the window is gone; we're quitting

    # -- updates --------------------------------------------------------------
    def can_update(self):
        """Only the packaged exe updates itself (running from source can't)."""
        return system.can_start_with_windows()

    def exe(self):
        return Path(sys.executable)

    def set_update_text(self, text, button=None):
        self.update_label.configure(text=text)
        if button:
            self.update_button.configure(text=button, state="normal")
            self.update_button.pack(side="left", padx=(8, 0))
        else:
            self.update_button.pack_forget()

    def check_updates(self, manual=False):
        """Asks GitHub for a newer version: on a timer, or when picked from the tray."""
        def work():
            try:
                found, problem = updater.check(VERSION), None
            except updater.UpdateError as error:
                found, problem = self.update, str(error)   # offline: keep what we knew
            self.events.put(lambda: self.update_found(found, problem if manual else None, manual))
        if manual:
            self.show()
            self.set_update_text("Checking for updates...")
        if not self.updating:
            threading.Thread(target=work, daemon=True).start()
        if not manual:
            self.root.after(CHECK_EVERY_MS, self.check_updates)

    def update_found(self, update, problem=None, manual=False):
        if self.updating:
            return
        self.update = update
        if update:
            note = "  (it didn't start last time)" if self.config.get("update_failed") == update.version else ""
            self.set_update_text("Version %s is available.%s" % (update.version, note), "Update")
        elif problem:
            self.set_update_text(problem)
        elif manual:
            self.set_update_text("You have the latest version.")
        self.update_tray()

    def start_update(self):
        if not self.update or self.updating:
            return
        folder = self.exe().parent
        if not self.can_update() or not updater.can_write(folder):
            webbrowser.open(self.update.page)
            messagebox.showinfo("GoldScout Companion",
                                "The companion can't update itself in %s. The download page is opening: "
                                "download GoldScoutCompanion.exe and replace this one." % folder)
            return
        self.updating = True
        self.set_update_text("Downloading %s..." % self.update.version)
        self.update_tray()
        update = self.update

        def progress(done, total):
            self.events.put(lambda: self.update_label.configure(
                text="Downloading %s... %d%%" % (update.version, done * 100 // max(total, 1))))

        def work():
            try:
                new = updater.download(update, folder, VERSION, progress=progress)
                self.events.put(lambda: self.update_label.configure(text="Checking the signature..."))
                try:
                    updater.verify_signature(new)
                except updater.UpdateError:
                    updater.remove(new)
                    raise
                self.events.put(lambda: self.install_update(new))
            except updater.UpdateError as error:
                message = str(error)
                self.events.put(lambda: self.update_failed(message))
        threading.Thread(target=work, daemon=True).start()

    def install_update(self, new):
        try:
            updater.swap(self.exe(), new)
        except updater.UpdateError as error:
            updater.remove(new)
            self.update_failed(str(error))
            return
        self.set_update_text("Starting %s..." % self.update.version)
        hidden = self.root.state() == "withdrawn"
        if self.tray:
            self.tray.stop()
            self.tray = None
        if self.instance:
            self.instance.close()
        try:
            updater.launch(self.exe(), ["--after-update"] + (["--tray"] if hidden else []))
        except OSError as error:
            self.roll_back("Couldn't start the new version (%s)." % error)
            return
        self.wait_for_handover(time.time() + HANDOVER_SECONDS)

    def wait_for_handover(self, deadline):
        if system.SingleInstance.other_running():
            self.config.pop("update_failed", None)
            save_config(self.config)
            self.root.destroy()   # the new version has taken over
            return
        if time.time() > deadline:
            self.roll_back("The new version didn't start, so this one was kept.")
            return
        self.root.after(250, lambda: self.wait_for_handover(deadline))

    def roll_back(self, message):
        updater.rollback(self.exe())
        if self.instance:
            self.instance.claim(signal=False)
        self.config["update_failed"] = self.update.version
        save_config(self.config)
        self.start_tray()
        self.update_failed(message)

    def update_failed(self, message):
        self.updating = False
        self.set_update_text("Update failed: %s" % message, "Try again")
        self.update_tray()

    def clean_up_updates(self, tries):
        """Deletes files earlier updates left; the old exe stays locked until its copy exits."""
        if not self.can_update():
            return
        if not updater.clean_up(self.exe().parent) and tries > 1:
            self.root.after(2000, lambda: self.clean_up_updates(tries - 1))

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
        else:
            self.maybe_upload()
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
        self.update_share_status()
        self.maybe_upload()

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
            since=self.since_text(account),
            notes=["Your export passed every check the GoldScout data bot runs."],
            can_share=True)

    def upload_state(self, account):
        return self.config.get("uploads", {}).get(account.install_id or "", {})

    def since_text(self, account):
        state = self.upload_state(account)
        if state.get("seq") == account.seq:
            return "Shared %s; nothing new since." % time.strftime(
                "%b %d, %H:%M", time.localtime(state["time"]))
        if state.get("seq"):
            return "New data since your last share."
        return "Not shared yet."

    def update_share_status(self):
        if not uploader.upload_url():
            text = "Automatic sharing isn't available yet; use Share now to share on GitHub."
        elif not self.has_consent():
            text = "Automatic sharing is off. Turn it on from the tray icon."
        elif not self.config.get("auto_share", True):
            text = "Automatic sharing is paused. Turn it back on from the tray icon."
        else:
            text = "Sharing automatically. New data uploads after you log out or /reload."
            error = self.config.get("last_error")
            if error and time.time() - error.get("time", 0) < RETRY_SECONDS * 2:
                text += "  Last try failed: %s" % error.get("message")
        self.share_status.configure(text=text)

    # -- uploading ------------------------------------------------------------
    def maybe_upload(self, force=False):
        if self.uploading or not (force or self.auto_share()):
            return
        error = self.config.get("last_error")
        if not force and error and time.time() - error.get("time", 0) < RETRY_SECONDS:
            return
        pending = []
        for account in self.accounts:
            if account.export and account.install_id and account.seq > self.upload_state(account).get("seq", 0):
                if submission.parse(account.export).ok:
                    pending.append(account)
        if pending:
            self.uploading = True
            threading.Thread(target=self.upload_all, args=(pending,), daemon=True).start()

    def upload_all(self, accounts):
        """Runs on a worker thread; hands results back to the Tk thread."""
        results = []
        for account in accounts:
            token = self.upload_state(account).get("token")
            try:
                reply = uploader.upload(account.export, token, VERSION)
                results.append((account, reply.get("token") or token, None))
            except uploader.UploadError as error:
                results.append((account, token, error))
        self.events.put(lambda: self.uploads_done(results))

    def uploads_done(self, results):
        self.uploading = False
        uploads = self.config.setdefault("uploads", {})
        self.config.pop("last_error", None)
        for account, token, error in results:
            if error:
                self.config["last_error"] = {"time": time.time(), "message": str(error)}
                continue
            uploads[account.install_id] = {"token": token, "seq": account.seq, "time": time.time()}
        save_config(self.config)
        if self.account:
            self.since_label.configure(text=self.since_text(self.account) if self.account.export else "")
        self.update_share_status()

    # -- manual sharing -------------------------------------------------------
    def copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.account.export)
        self.root.update()

    def share_now(self):
        if self.has_consent() and uploader.upload_url():
            self.config.pop("last_error", None)
            self.maybe_upload(force=True)
            return
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


def main():
    parser = argparse.ArgumentParser(description="GoldScout Companion")
    parser.add_argument("--tray", action="store_true", help="start hidden in the system tray")
    parser.add_argument("--after-update", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    instance = system.SingleInstance(SHOW_REQUEST)
    if args.after_update:
        if not instance.claim_when_free(HANDOVER_SECONDS - 5):
            return  # the old version is still running; it rolls back on its own
    elif not instance.claim():
        return  # the copy that's already running shows its window instead
    instance.show_requested()  # clear any stale request
    root = tk.Tk()
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass
    App(root, start_hidden=args.tray, instance=instance, updated=args.after_update)
    root.mainloop()
    instance.close()


if __name__ == "__main__":
    main()
