# Project V4 development notes

Start with README.md for the current workflow and model assumptions.
Source/main.py starts the desktop editor; main.py is the repository launcher.
The source folders separate simulation, map, program, data, and tests.
The app uses simulation/houston.py and simulation/editor.py with the embedded
map/assets/editor interface. Older UI modules remain for regression checks.

Build on Windows with Python 3.12 and Source/requirements-desktop.txt.
From Source, run python -m pytest -q and node --check map/assets/editor.js.
Run python main.py --self-test for desktop integration checks.
Build the portable folder with python -m PyInstaller --noconfirm TexasGrid.spec.
Distribute the entire dist/Texas Grid Analysis V4 folder, including _internal.

The AI results assistant is outside the project scope.
