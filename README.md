# f1-track-position

## What the project does

This project asks whether Formula 1 teams give up race time to gain track position over a direct rival, and whether this depends on how hard overtaking is at a circuit. It uses lap and pit stop data from Grand Prix races in the 2023 to 2026 seasons, a tyre model that gives each car's time-optimal pit lap, and a two-car race simulator to compare real pit decisions with time-minimising and position-maximising strategies.

## What to install

Python 3.10 to 3.13 is required. From the repository root:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

TODO: confirm the Python version and the installation steps on Nuvolos.

## What to run, in order

Run every step from the repository root, with the virtual environment active. Open the notebooks with `jupyter lab` and run all cells from top to bottom.

1. `code/01_get_data.py` (TODO)
2. `code/02_clean.ipynb` (TODO)
3. `code/03_overtaking.ipynb` (TODO)
4. `code/04_tyre_model.ipynb` (TODO)
5. `code/05_simulator.ipynb` (TODO)
6. `code/06_tests.ipynb` (TODO)
7. `code/07_figures.ipynb` (TODO)

`code/helpers.py` holds the shared paths, constants and functions and is imported by the other files; it is not run on its own.

## How long it takes and what it produces

| Step | Time | Produces |
|------|------|----------|
| `01_get_data.py` | TODO | raw data in `data/raw/` |
| `02_clean.ipynb` | TODO | TODO |
| `03_overtaking.ipynb` | TODO | TODO |
| `04_tyre_model.ipynb` | TODO | TODO |
| `05_simulator.ipynb` | TODO | TODO |
| `06_tests.ipynb` | TODO | TODO |
| `07_figures.ipynb` | TODO | figures in `figures/`, tables in `results/` |

## Where the data comes from

The data comes from the free OpenF1 API (https://openf1.org), which needs no login. The raw data is not included in this repository; `code/01_get_data.py` downloads it into `data/raw/`. See `data/README.md` for details and the licence statement.
