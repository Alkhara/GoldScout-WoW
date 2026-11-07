#!/usr/bin/env python3
"""Builds GoldScoutCompanion.exe, a single file that runs without Python.

  pip install pyinstaller pystray pillow
  python companion/build.py

The exe lands in companion/dist/.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "GoldScoutCompanion",
        "--paths", str(ROOT / "tools"),
        "--hidden-import", "submission",
        "--hidden-import", "pystray._win32",
        "--icon", str(HERE / "icon.ico"),
        "--add-data", "%s;." % (HERE / "icon.png"),
        "--add-data", "%s;." % (HERE / "icon.ico"),
        "--distpath", str(HERE / "dist"),
        "--workpath", str(HERE / "build"),
        "--specpath", str(HERE / "build"),
        str(HERE / "app.py"),
    ], check=True)
    print("Built", HERE / "dist" / "GoldScoutCompanion.exe")


if __name__ == "__main__":
    main()
