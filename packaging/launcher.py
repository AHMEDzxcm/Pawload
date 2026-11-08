"""Entry point for Palwoad.exe (windowed tray app, also the command line)."""
import os
import sys

if sys.stdout is None:  # windowed build has no console
    sys.stdout = sys.stderr = open(os.devnull, "w")

from palwoad.cli import main

if __name__ == "__main__":
    main()
