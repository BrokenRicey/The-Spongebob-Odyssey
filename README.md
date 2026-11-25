# Senior design: Texas Grid Analysis

**Project V4 is the current desktop application.**

- [Download the Windows application](https://github.com/BrokenRicey/The-Spongebob-Odyssey/releases/tag/project-v4)
- [Simple installation instructions](START-HERE.txt)
- [V4 controls and model assumptions](Project%20V4/README.md)

Download the Windows ZIP, extract everything, and run **Texas Grid Analysis V4.exe**.
No Python installation is needed for the portable application.

## Repository layout

| Folder | Contents |
| --- | --- |
| `Project V4/` | Current desktop app source, instructions, and verification |
| `Project V4/Source/simulation/` | Electrical model, solver, and study editing |
| `Project V4/Source/map/` | Map interface and desktop editor |
| `Project V4/Source/data/` | Bundled study data |
| `Project V4/Source/tests/` | Automated checks |
| `Project V3/` | Previous desktop version, retained for reference |
| `Houston Grid/` | Team's separate GIS and ERCOT bus import work |
| `Archive/` | Earlier Houston map files |

The root `TL_Senior_Simulation_*.py` files are historical solver references.
Start V4 with `Project V4/main.py`; its source dependencies and setup steps are
in [START-HERE.txt](START-HERE.txt). Executables and ZIP packages are distributed
through GitHub Releases, separate from the source folders.

V4 supports editable baseline/scenario networks, equipment outages, hypothetical
data-center placement, simulation, comparison, and saved studies. Its electrical
parameters and connectivity include study assumptions; it is not a validated
ERCOT operating model. No AI results assistant is included.
