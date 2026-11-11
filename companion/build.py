#!/usr/bin/env python3
"""Builds the companion so it runs without Python.

Windows: GoldScoutCompanion.exe, a single file.
  pip install -r companion/requirements-build.txt -r companion/requirements.txt
  python companion/build.py

macOS: GoldScout Companion.app (no tray icon, so no pystray or Pillow needed).
  pip install -r companion/requirements-build.txt
  python3 companion/build.py [--universal2]

--universal2 builds one app for Apple silicon and Intel Macs; it needs a
universal2 Python (the python.org installer). Signing and notarizing happen
afterwards, in the release workflow. Everything lands in companion/dist/.
"""
import argparse
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOGO = ROOT / "docs" / "logo" / "goldscout-logo-1024.png"
BUNDLE_ID = "com.wowgoldscout.companion"
APP_NAME = "GoldScout Companion"


def version():
    match = re.search(r'^VERSION = "([^"]+)"', (HERE / "app.py").read_text(encoding="utf-8"), re.M)
    return match.group(1)


def common_args():
    data = os.pathsep  # PyInstaller's --add-data separator: ";" on Windows, ":" elsewhere
    return [
        "--noconfirm", "--clean", "--windowed",
        "--paths", str(ROOT / "tools"),
        "--hidden-import", "submission",
        "--add-data", "%s%s." % (HERE / "icon.png", data),
        "--distpath", str(HERE / "dist"),
        "--workpath", str(HERE / "build"),
        "--specpath", str(HERE / "build"),
    ]


def build_windows():
    subprocess.run([sys.executable, "-m", "PyInstaller", *common_args(),
                    "--onefile", "--name", "GoldScoutCompanion",
                    "--hidden-import", "pystray._win32",
                    "--icon", str(HERE / "icon.ico"),
                    "--add-data", "%s;." % (HERE / "icon.ico"),
                    str(HERE / "app.py")], check=True)
    print("Built", HERE / "dist" / "GoldScoutCompanion.exe")


def make_icns(target):
    """GoldScout's logo as a macOS icon, with the system's sips and iconutil."""
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "GoldScout.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                name = "icon_%dx%d%s.png" % (size, size, "@2x" if scale == 2 else "")
                subprocess.run(["sips", "-z", str(size * scale), str(size * scale), str(LOGO),
                                "--out", str(iconset / name)], check=True, capture_output=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], check=True)


def build_mac(universal):
    build = HERE / "build"
    build.mkdir(exist_ok=True)
    icns = build / "GoldScout.icns"
    make_icns(icns)
    args = [sys.executable, "-m", "PyInstaller", *common_args(),
            "--onedir", "--name", APP_NAME,
            "--osx-bundle-identifier", BUNDLE_ID,
            "--exclude-module", "pystray", "--exclude-module", "PIL",
            "--icon", str(icns)]
    if universal:
        args += ["--target-arch", "universal2"]
    subprocess.run(args + [str(HERE / "app.py")], check=True)
    app = HERE / "dist" / (APP_NAME + ".app")
    info_path = app / "Contents" / "Info.plist"
    with open(info_path, "rb") as handle:
        info = plistlib.load(handle)
    info.update({
        "CFBundleShortVersionString": version(),
        "CFBundleVersion": version(),
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "GoldScout. Not affiliated with or endorsed by Blizzard Entertainment.",
    })
    with open(info_path, "wb") as handle:
        plistlib.dump(info, handle)
    # Editing Info.plist broke PyInstaller's ad-hoc signature; redo it so the
    # unsigned build still opens on Apple silicon (releases are re-signed).
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    shutil.rmtree(HERE / "dist" / APP_NAME, ignore_errors=True)  # the onedir folder the .app duplicates
    print("Built", app)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--universal2", action="store_true", help="macOS: one app for Apple silicon and Intel")
    args = parser.parse_args()
    if sys.platform == "darwin":
        build_mac(args.universal2)
    elif sys.platform == "win32":
        build_windows()
    else:
        sys.exit("The companion is built on Windows or macOS.")


if __name__ == "__main__":
    main()
