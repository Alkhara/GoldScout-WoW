"""GoldScout Companion: shares your GoldScout drop data automatically and
brings auction house prices into GoldScout.

It lives in the system tray (on macOS, in the Dock), finds WoW Forever, reads the export GoldScout
saves, checks it with the same validator the GoldScout data bot uses, and
uploads new snapshots once you've agreed to the Contributor Terms. Every hour
it also writes the latest auction prices for your realms into the
GoldScout_Prices data addon (auction_prices.py), the only thing it changes in
the WoW folder. Its only notification says a new version is out, and only
while World of Warcraft isn't running.

Run:  python companion/app.py          (--tray starts with the window hidden)
"""
import argparse
import json
import queue
import random
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
import auction_prices  # noqa: E402
import savedvars  # noqa: E402
import submission  # noqa: E402
import system  # noqa: E402
import updater  # noqa: E402
import uploader  # noqa: E402

VERSION = "0.8.0"  # tools/release.py checks this matches the tag; the release build stamps it
FORM_URL = "https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml"
TERMS_URL = "https://github.com/Alkhara/GoldScout-WoW/blob/main/docs/CONTRIBUTOR_TERMS.md"
PRIVACY_URL = "https://github.com/Alkhara/GoldScout-WoW/blob/main/docs/PRIVACY.md"
MAX_URL = 7500           # longer links get cut off; then the export goes via the clipboard
POLL_MS = 15000          # how often to look for newer saved data
RETRY_SECONDS = 300      # wait after a failed upload before trying again
FIRST_CHECK_MS = 30000   # first update check, after startup settles
CHECK_EVERY_MS = 6 * 3600 * 1000
HANDOVER_SECONDS = 25    # how long a new version gets to start before we roll back
PRICE_MINUTE = 25        # check for new prices at :25 UTC (Blizzard's snapshot ~:16, on the server by ~:22)
PRICE_RETRY_SECONDS = 600
FIRST_PRICE_MS = 8000
GAME_CHECK_MS = 60000    # while WoW is open, look again this often before telling about an update
CONFIG_DIR = system.config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
SHOW_REQUEST = CONFIG_DIR / "show.request"
FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"
PASTE_KEY = "Cmd+V" if system.MAC else "Ctrl+V"


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
        self.pricing, self.price_timer, self.price_keys = False, None, None
        self.notify_timer = None

        root.title("GoldScout Companion")
        root.minsize(560, 420)
        try:
            if system.WINDOWS:
                root.iconbitmap(str(HERE / "icon.ico"))
            else:
                self.icon = tk.PhotoImage(file=str(HERE / "icon.png"))
                root.iconphoto(True, self.icon)
        except tk.TclError:
            pass
        root.protocol("WM_DELETE_WINDOW", self.hide)
        if system.MAC:
            # No tray icon on macOS: closing the window keeps the companion in
            # the Dock, and clicking it there opens the window again.
            root.createcommand("tk::mac::ReopenApplication", self.show)
            root.createcommand("tk::mac::Quit", self.quit)

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
        if not self.tray:
            self.settings.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        self.update_controls()
        self.refresh()
        self.root.after(200, self.pump)
        self.root.after(POLL_MS, self.poll)
        if updated:
            self.set_update_text("Updated to %s." % VERSION)
        self.clean_up_updates(30)
        if self.can_update():
            self.root.after(FIRST_CHECK_MS, self.check_updates)
        self.update_prices_status()
        self.schedule_prices(FIRST_PRICE_MS)

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
        self.update_controls()
        self.update_share_status()
        if enabled:
            self.maybe_upload()

    def set_start_at_login(self, enabled):
        try:
            system.set_start_at_login(enabled)
        except OSError as error:
            messagebox.showerror("GoldScout Companion", "Couldn't change the startup setting: %s" % error)
        self.update_controls()

    def controls_place(self):
        """Where the settings are: the tray icon's menu, or the window's Settings."""
        return "the tray icon" if self.tray else "Settings below"

    # -- layout ---------------------------------------------------------------
    def build_welcome(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Welcome to GoldScout Companion", font=(FONT, 15, "bold")).grid(sticky="w")
        ttk.Label(frame, wraplength=500, justify="left", text=(
            "GoldScout learns drop rates from your loot. The companion shares what it learns so the "
            "Farm tab gets better for everyone, and it does it automatically: it runs quietly in the "
            + ("background (in the Dock)" if system.MAC else "system tray") +
            " and uploads new data after you log out or /reload.\n\n"
            "What's shared: creature and item IDs and names, kill and drop counts, mob levels, where "
            "you looted, and which items your professions can make, plus a random ID for your "
            "GoldScout data. Never character, account or realm names.\n\n"
            "It also brings auction house prices into GoldScout: about once an hour it saves the "
            "latest prices for your realms in a small GoldScout_Prices addon, the only thing it "
            "changes in your WoW folder. That works even if you don't share.")
        ).grid(sticky="w", pady=(10, 10))
        links = ttk.Frame(frame)
        links.grid(sticky="w")
        link(links, "Contributor Terms", TERMS_URL).pack(side="left")
        ttk.Label(links, text="  ·  ").pack(side="left")
        link(links, "Privacy Policy", PRIVACY_URL).pack(side="left")

        self.startup_choice = tk.BooleanVar(value=True)
        startup = ttk.Checkbutton(frame, text=system.STARTUP_LABEL + (
            " (in the background)" if system.MAC else " (in the tray)"), variable=self.startup_choice)
        startup.grid(sticky="w", pady=(14, 0))
        if not system.can_start_at_login():
            startup.state(["disabled"])
            self.startup_choice.set(False)

        ttk.Label(frame, foreground="#555", wraplength=500, justify="left", text=(
            "You can turn off automatic sharing or %s any time from %s." % (
                "opening at login" if system.MAC else "starting with Windows",
                "Settings in the companion's window" if system.MAC else "the tray icon"))
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

        ttk.Label(frame, text="GoldScout Companion", font=(FONT, 15, "bold")).grid(row=0, column=0, sticky="w")
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
        self.stats_label = ttk.Label(data, text="", font=(FONT, 10, "bold"))
        self.stats_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.since_label = ttk.Label(data, text="")
        self.since_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 6))
        self.notes = tk.Text(data, height=6, wrap="word", relief="flat", background=root.cget("background"),
                             font=(FONT, 9))
        self.notes.grid(row=3, column=0, columnspan=2, sticky="nsew")
        data.rowconfigure(3, weight=1)

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, sticky="ew")
        self.share_button = ttk.Button(buttons, text="Share now", command=self.share_now)
        self.share_button.pack(side="left")
        self.copy_button = ttk.Button(buttons, text="Copy export", command=self.copy)
        self.copy_button.pack(side="left", padx=8)
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(buttons, text="Quit", command=self.quit).pack(side="right")

        # Settings in the window, when there's no tray icon to hold them (macOS).
        self.settings = ttk.LabelFrame(frame, text="Settings", padding=8)
        self.share_choice = tk.BooleanVar(value=False)
        self.prices_choice = tk.BooleanVar(value=True)
        self.login_choice = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.settings, text="Share automatically", variable=self.share_choice,
                        command=lambda: self.set_auto_share(self.share_choice.get())).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(self.settings, text="Auction prices in GoldScout", variable=self.prices_choice,
                        command=lambda: self.set_prices_enabled(self.prices_choice.get())).grid(
                            row=0, column=1, sticky="w", padx=(16, 0))
        self.login_check = ttk.Checkbutton(self.settings, text=system.STARTUP_LABEL, variable=self.login_choice,
                                           command=lambda: self.set_start_at_login(self.login_choice.get()))
        self.login_check.grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.check_button = ttk.Button(self.settings, text="Check for updates",
                                       command=lambda: self.check_updates(manual=True))
        self.check_button.grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.prices_label = ttk.Label(frame, text="", foreground="#555", wraplength=520, justify="left")
        self.prices_label.grid(row=6, column=0, sticky="w", pady=(10, 0))

        if system.MAC:
            closing = ("Closing this window keeps the companion running in the Dock; click its Dock icon "
                       "to open it again. ")
        else:
            closing = "Closing this window keeps the companion running in the system tray; "
        ttk.Label(frame, foreground="#777", wraplength=520, font=(FONT, 8), text=(
            closing + "Quit stops it until "
            "you start it again. GoldScout saves its "
            "data when you log out or type /reload, so new loot shows up here after that. Auction "
            "prices: Blizzard Entertainment Game Data API; GoldScout isn't affiliated with or endorsed "
            "by Blizzard. Companion " + VERSION)).grid(row=7, column=0, sticky="w", pady=(12, 0))
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
        if system.can_start_at_login():
            self.set_start_at_login(self.startup_choice.get())
        self.show_main()
        self.update_controls()
        self.refresh()

    def decline(self):
        self.config["declined"] = True
        save_config(self.config)
        self.show_main()
        self.update_controls()
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
        if system.MAC:
            return  # pystray and Tk can't share macOS's main thread; the window has Settings instead
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return  # no tray support; closing the window then just hides it
        menu = pystray.Menu(
            pystray.MenuItem("Open GoldScout Companion", lambda: self.events.put(self.show), default=True),
            pystray.MenuItem("Share automatically", lambda: self.events.put(
                lambda: self.set_auto_share(not self.auto_share())), checked=lambda _: self.auto_share()),
            pystray.MenuItem("Auction prices in GoldScout", lambda: self.events.put(
                lambda: self.set_prices_enabled(not self.prices_enabled())),
                checked=lambda _: self.prices_enabled()),
            pystray.MenuItem(system.STARTUP_LABEL, lambda: self.events.put(
                lambda: self.set_start_at_login(not system.start_at_login_enabled())),
                checked=lambda _: system.start_at_login_enabled(),
                enabled=lambda _: system.can_start_at_login()),
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

    def update_controls(self):
        """Brings the tray menu, or the window's Settings, up to date."""
        if self.tray:
            self.tray.update_menu()
            return
        self.share_choice.set(self.auto_share())
        self.prices_choice.set(self.prices_enabled())
        self.login_choice.set(system.start_at_login_enabled())
        self.login_check.state(["!disabled"] if system.can_start_at_login() else ["disabled"])
        if self.can_update() and not self.update and not self.updating:
            self.check_button.grid()
        else:
            self.check_button.grid_remove()

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
        """Only the packaged app updates itself (running from source can't)."""
        return system.packaged()

    def exe(self):
        """The exe on Windows, the .app on macOS."""
        return system.installed_path()

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
        if self.notify_timer:
            self.root.after_cancel(self.notify_timer)
            self.notify_timer = None
        self.update = update
        if update:
            note = "  (it didn't start last time)" if self.config.get("update_failed") == update.version else ""
            self.set_update_text("Version %s is available.%s" % (update.version, note), "Update")
        elif problem:
            self.set_update_text(problem)
        elif manual:
            self.set_update_text("You have the latest version.")
        self.update_controls()
        self.notify_update()

    def notify_update(self):
        """One notification per new version, never while WoW is open:
        it waits until the game is closed. Skipped when the window is open,
        since it already shows Update."""
        self.notify_timer = None
        update = self.update
        if not update or self.updating or self.config.get("update_notified") == update.version:
            return
        if self.root.state() != "withdrawn":
            self.config["update_notified"] = update.version
            save_config(self.config)
            return
        if system.game_running():
            self.notify_timer = self.root.after(GAME_CHECK_MS, self.notify_update)
            return
        if self.tray and getattr(self.tray, "HAS_NOTIFICATION", False):
            try:
                self.tray.notify("GoldScout Companion %s is available. Click the GoldScout icon in the tray, "
                                 "then Update." % update.version, "GoldScout Companion update")
            except Exception:  # noqa: BLE001 - a notification is never worth crashing for
                return
        elif system.MAC:
            system.notify("GoldScout Companion update",
                          "Version %s is available. Click GoldScout Companion in the Dock, then Update."
                          % update.version)
        self.config["update_notified"] = update.version
        save_config(self.config)

    def start_update(self):
        if not self.update or self.updating:
            return
        folder = self.exe().parent
        if not self.can_update() or not updater.can_install() or not updater.can_write(folder):
            webbrowser.open(self.update.page)
            if system.MAC:
                how = "download %s, open it and drag GoldScout Companion into Applications" % updater.MAC_ASSET
            else:
                how = "download GoldScoutCompanion.exe and replace this one"
            messagebox.showinfo("GoldScout Companion",
                                "The companion can't update itself in %s. The download page is opening: %s."
                                % (folder, how))
            return
        self.updating = True
        self.set_update_text("Downloading %s..." % self.update.version)
        self.update_controls()
        update = self.update

        def progress(done, total):
            self.events.put(lambda: self.update_label.configure(
                text="Downloading %s... %d%%" % (update.version, done * 100 // max(total, 1))))

        def work():
            try:
                new = updater.download(update, folder, VERSION, progress=progress)
                self.events.put(lambda: self.update_label.configure(text="Checking the signature..."))
                new = updater.prepare(new, folder)
                try:
                    updater.verify(new)
                except updater.UpdateError:
                    updater.remove(new)
                    updater.clean_up(folder)
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
        if self.instance and self.instance.other_running():
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
        self.update_controls()

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
        keys = sorted(auction_prices.wanted_markets(self.accounts, time.time())) if self.forever else []
        if self.price_keys is not None and keys != self.price_keys:
            self.schedule_prices(1000)   # a new realm or a new scan: no need to wait for the hour
        self.price_keys = keys

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
            text = "Automatic sharing is off. Turn it on from %s." % self.controls_place()
        elif not self.config.get("auto_share", True):
            text = "Automatic sharing is paused. Turn it back on from %s." % self.controls_place()
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

    # -- auction prices -------------------------------------------------------
    def prices_enabled(self):
        return self.config.get("prices_enabled", True)

    def set_prices_enabled(self, enabled):
        self.config["prices_enabled"] = enabled
        save_config(self.config)
        if enabled:
            self.schedule_prices(500)
        elif self.forever and auction_prices.remove_addon(self.forever):
            self.config.get("price_state", {}).pop("written", None)
            save_config(self.config)
        self.update_controls()
        self.update_prices_status()

    def schedule_prices(self, delay_ms=None):
        if self.price_timer:
            self.root.after_cancel(self.price_timer)
        if delay_ms is None:
            now = time.time()
            target = int(now // 3600) * 3600 + PRICE_MINUTE * 60
            if target <= now:
                target += 3600
            delay_ms = int((target - now + random.uniform(0, 180)) * 1000)
        self.price_timer = self.root.after(delay_ms, self.check_prices)

    def check_prices(self):
        """Hourly: brings the GoldScout_Prices data addon up to date (on a worker thread)."""
        self.price_timer = None
        if self.pricing:
            return   # the running check reschedules when it finishes
        if not self.prices_enabled() or not self.forever:
            self.update_prices_status()
            self.schedule_prices()
            return
        self.pricing = True
        forever, accounts = self.forever, list(self.accounts)
        state = json.loads(json.dumps(self.config.get("price_state", {})))

        def work():
            try:
                summary = auction_prices.update(
                    forever, accounts, state, time.time(),
                    fetch=lambda path: auction_prices.get_json(path, VERSION))
                problem = summary.get("problem")
            except (auction_prices.PriceError, OSError, KeyError, TypeError, ValueError) as error:
                summary, problem = None, str(error)
            self.events.put(lambda: self.prices_done(state, summary, problem))
        threading.Thread(target=work, daemon=True).start()

    def prices_done(self, state, summary, problem):
        self.pricing = False
        if summary is not None:
            self.config["price_state"] = state
        previous = (self.config.get("price_status") or {}).get("summary")
        self.config["price_status"] = {"time": time.time(), "problem": problem,
                                       "summary": summary if summary is not None else previous}
        save_config(self.config)
        self.update_prices_status()
        self.schedule_prices(PRICE_RETRY_SECONDS * 1000 if summary is None else None)

    def update_prices_status(self):
        if not self.prices_enabled():
            text = "Auction prices in GoldScout are off. Turn them on from %s." % self.controls_place()
        else:
            status = self.config.get("price_status") or {}
            summary = status.get("summary") or {}
            markets = summary.get("markets") or {}
            newest = {}   # realms with the same ruleset share an auction house: list it once
            for key, market in markets.items():
                label = auction_prices.market_label(key)
                newest[label] = max(newest.get(label, 0), market["snapshot"])
            parts = []
            for label in sorted(newest):
                minutes = max(0, int((time.time() - newest[label]) // 60))
                age = "%d min" % minutes if minutes < 90 else "%d h" % (minutes // 60)
                parts.append("%s (%s old)" % (label, age))
            if parts:
                text = ("Auction prices in GoldScout: " + ", ".join(parts) +
                        ". GoldScout loads them at login or /reload.")
            elif summary.get("unsupported") and not summary.get("unknown"):
                text = ("Auction prices: GoldScout doesn't have prices for your region yet. Scan at the "
                        "auction house in GoldScout for prices in the meantime.")
            elif summary.get("unknown"):
                text = ("Auction prices: GoldScout doesn't know your auction house yet. Scan it once in "
                        "GoldScout, then log out or /reload; the companion matches it within the hour.")
            elif summary:
                text = "Auction prices: log in with GoldScout installed once, then they'll be saved for it."
            else:
                text = "Auction prices: checking..."
            if status.get("problem"):
                text += "  Last check: " + status["problem"]
        self.prices_label.configure(text=text)

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
                                "In the form that's opening, click the export box, press %s, tick the two "
                                "boxes and press Create." % PASTE_KEY)


def main():
    parser = argparse.ArgumentParser(description="GoldScout Companion")
    parser.add_argument("--tray", action="store_true", help="start with the window hidden (in the tray or Dock)")
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
    if system.WINDOWS:
        try:
            ttk.Style(root).theme_use("vista")
        except tk.TclError:
            pass
    App(root, start_hidden=args.tray, instance=instance, updated=args.after_update)
    root.mainloop()
    instance.close()


if __name__ == "__main__":
    main()
