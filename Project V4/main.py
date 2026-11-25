"""Run the combined Project V4 desktop application."""
import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    source = Path(__file__).resolve().parent / "Source"
    sys.path.insert(0, str(source))
    runpy.run_path(str(source / "main.py"), run_name="__main__")
