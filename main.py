#!/usr/bin/env python3
"""
main.py — Entry point for Tropilla Emulator.

Usage:
    python main.py
"""

import logging
import sys

# Configure logging before importing any emulator module
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

from emulator.gui import EmulatorApp


def main() -> None:
    app = EmulatorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
