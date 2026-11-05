# Project V3

Texas Grid Analysis V3 brings the load editor, Houston transmission map, simulation controls, and results into one screen.

## Download and run

Download `Project-V3-Windows-x64.zip` from the [Project V3 release](https://github.com/BrokenRicey/The-Spongebob-Odyssey/releases/tag/project-v3). Extract the ZIP and open `Texas Grid Analysis/Texas Grid Analysis.exe`. Keep the `_internal` folder beside the executable.

See [START-HERE.md](START-HERE.md) for load editing, route attachments, project saving, and map controls. Street tiles require internet access; bundled geographic data and calculations run locally.

## Source and verification

Editable code and the build specification are in [Source](Source). Packaged application checks and screenshots are in [Verification/single-screen-packaged](Verification/single-screen-packaged).

The electrical network is representative and synthetic. GIS routes provide geographic context; a route attachment does not establish an electrical connection. Fault and transient studies are unavailable.

Build outputs and bundled runtime libraries are distributed as release assets, so source commits stay within GitHub's file-size limit.

## Team folder layout

```text
Project V3/
├── main.py                 Start the combined program from source
├── Source/
│   ├── main.py             Application entry point used by the build
│   ├── simulation/         Thanh's simulation engines and shared study logic
│   │   ├── TL_Senior_Simulation_V1.py
│   │   ├── TL_Senior_Simulation_V4.py
│   │   ├── gridsim/        Network building, scenarios, and solver results
│   │   └── study.py        Project saving, validation, and exports
│   ├── map/                James's Houston map implementation
│   │   ├── generator.py    Generates the standalone HTML/SVG map
│   │   ├── assets/         Houston data, JavaScript, CSS, and Leaflet
│   │   ├── window.py       Map integration with the desktop program
│   │   └── diagram.py      Electrical diagram and sweep chart
│   ├── program/            Shared desktop controls, editor, and result tables
│   ├── data/               Shared electrical model and source snapshots
│   ├── app/                Earlier browser/API application
│   ├── tests/              Automated tests
│   └── scripts/            Data preparation and packaging tools
└── Verification/           Test reports and screenshots
```

The simulation files available here are V1 and V4; there is no V2 engine in this snapshot. Keep the existing version names so the team can identify the actual solver. New simulation versions belong beside them in `Source/simulation/`.

Developers need Python and the dependencies in `Source/requirements-desktop.txt`. From the repository root, run `python main.py` to start the combined program. From `Source/`, run `python -m map.generator` to generate and view the standalone Houston map, or add `--no-browser` to generate it without opening a browser. Generated HTML, SVG, and GIS exports go in `Source/map/output/`.

Run `python -m pytest -q` from `Source/` for the automated tests. Build the portable application from `Source/` using `python -m PyInstaller --noconfirm TexasGrid.spec`.

Simulation and map code communicate through shared study inputs and result data. Keep solver calculations in `simulation/`, geographic rendering in `map/`, and the shared desktop controls in `program/`. Edit those source folders; the release download contains the compiled program and bundled runtime.
