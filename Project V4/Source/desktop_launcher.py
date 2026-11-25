"""Compatibility entry point. New development starts in main.py."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("main.py")), run_name="__main__")
