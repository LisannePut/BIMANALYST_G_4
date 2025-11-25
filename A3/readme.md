## Assignment 3 runner

This folder contains `Assignment3.py`, which analyzes an IFC model against BR18-style rules (doors, corridors, stairs).

### Requirements

- Python 3.10+
- Packages: `ifcopenshell`, `numpy`

If needed, install:

```bash
pip install ifcopenshell numpy
```

### How to run

From the project root or from this folder:

```bash
python3 A3/Assignment3.py
```

The script reads the IFC model at `A3/model/25-16-D-ARCH.ifc` by default.

### Faster (quick) run

If full 3D geometry extraction is slow on your machine, use quick mode to skip heavy geometry and rely on metadata where possible:

```bash
python3 A3/Assignment3.py --quick
```

You'll see progress prints (counts, space batches analyzed) and a total runtime.

### Output

The script prints:
- Door count and non-compliant doors
- Corridor count with failing and passing corridors
- Stair flights and non-compliant items
- Stair compartmentation notes (e.g., door in wall, swing heuristic)

### Notes

- Quick mode may be conservative for some checks that depend on exact geometry (e.g., space-door adjacency). Use a full run for final verification.
- If you use a virtual environment, activate it first.

```bash
# macOS zsh example
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip ifcopenshell numpy
python3 A3/Assignment3.py --quick
```

hello everyone
