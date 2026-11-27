"""Shared paths, constants and functions used by more than one stage.

Every stage imports from this file so that folders, seasons, the cutoff
date and the random seed are defined in exactly one place.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, DotProduct, WhiteKernel

# Paths are built from this file's own location (code/helpers.py), so they
# work no matter which folder a script or notebook is started from.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
RESULTS = REPO_ROOT / "results"
FIGURES = REPO_ROOT / "figures"

# Seasons covered by the analysis (Grand Prix races only, no sprints).
SEASONS = [2023, 2024, 2025, 2026]

# Races starting before this date are included (2026 up to Las Vegas).
CUTOFF_DATE = "2026-11-23"

# One seed for every random step, so results can be reproduced.
RANDOM_SEED = 42

# OpenF1 API (free, no login) and the tables downloaded for every race.
API_URL = "https://api.openf1.org/v1"
ENDPOINTS = [
    "drivers",
    "laps",
    "stints",
    "pit",
    "intervals",
    "position",
    "race_control",
    "weather",
    "session_result",
    "overtakes",
]

# The columns that identify one car in one race, and one lap of that car.
KEY = ["session_key", "driver_number"]
LAP_KEY = KEY + ["lap_number"]

# Tyre model (stage 3). A compound is fitted in a race only with at least
# this many usable laps from at least this many drivers.
MIN_COMPOUND_LAPS = 30
MIN_COMPOUND_DRIVERS = 3
# A race whose lap-number effect has a standard error above this value
# (seconds per lap) uses the median of its season instead.
MAX_LAP_EFFECT_SE = 0.01
# The smooth part of the tyre curve may not change faster than over this
# many laps of tyre age; shorter length scales fit bumps in the noise.
MIN_LENGTH_SCALE = 5.0
# The kernel search is started again from this many random points.
GP_RESTARTS = 3


def load_races():
    """Return the race index saved by stage 1 (one row per race)."""
    return pd.read_parquet(DATA_RAW / "sessions.parquet")


def load_raw(endpoint, columns=None, number_columns=(), date_columns=()):
    """Combine one raw table over all races, converting the listed columns explicitly."""
    tables = []
    for race in load_races().itertuples():
        path = DATA_RAW / str(race.year) / f"{race.session_key}_{endpoint}.parquet"
        if not path.exists():
            continue  # OpenF1 has no pit table for six 2023 races
        table = pd.read_parquet(path, columns=columns)
        # The raw files keep values as delivered, so the same column can be
        # numbers in one race and text in another. Unexpected text stops the
        # run here instead of silently becoming a missing value.
        for column in number_columns:
            table[column] = pd.to_numeric(table[column])
        for column in date_columns:
            table[column] = pd.to_datetime(table[column], format="ISO8601", utc=True)
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


def add_step(cleaning_steps, step, laps_before, laps_affected, action, reason):
    """Add one row to the cleaning table (a list with one dictionary per step)."""
    cleaning_steps.append(
        {"step": step, "laps_before": int(laps_before), "laps_affected": int(laps_affected),
         "action": action, "reason": reason}
    )


def scheduled_start_times(races):
    """Return the scheduled start time of every race, indexed by session_key."""
    return pd.to_datetime(races.set_index("session_key")["date"], format="ISO8601", utc=True)


def find_red_flags(race_control):
    """Return one row per red-flag period: from SESSION ABORTED to the next SESSION STARTED."""
    status = race_control[race_control["category"] == "SessionStatus"].sort_values(["session_key", "date"])
    periods = []
    for session_key, messages in status.groupby("session_key"):
        aborted_at = None
        for message in messages.itertuples():
            if message.message == "SESSION ABORTED":
                aborted_at = message.date
            elif message.message == "SESSION STARTED" and aborted_at is not None:
                periods.append({"session_key": session_key, "red_start": aborted_at, "red_end": message.date})
                aborted_at = None
    return pd.DataFrame(periods)


def tyre_kernel():
    """Return the kernel of the tyre curve: smooth part + linear wear trend + lap-to-lap noise."""
    smooth = ConstantKernel(1.0, (1e-3, 1e3)) * RBF(10.0, (MIN_LENGTH_SCALE, 200.0))
    # The linear part continues the wear trend beyond the oldest tyre seen,
    # where the smooth part alone would bend back towards the average.
    trend = ConstantKernel(0.01, (1e-6, 1e2)) * DotProduct(1.0, (1e-2, 1e2))
    noise = WhiteKernel(0.5, (1e-3, 1e1))
    return smooth + trend + noise


def fit_baseline_and_lap_effect(race_laps, fixed_lap_effect=None):
    """Fit step A on the usable laps of one race: driver baselines and the lap-number effect."""
    drivers = pd.get_dummies(race_laps["driver_number"], dtype=float)
    compounds = sorted(race_laps["compound"].unique())
    tyre_age = race_laps["tyre_age"].astype(float)
    columns = {("driver", driver): drivers[driver] for driver in drivers.columns}
    if fixed_lap_effect is None:
        columns[("lap_number", "")] = race_laps["lap_number"].astype(float)
    # The first compound is the reference: a driver's baseline is the lap
    # time on a new tyre of that compound at lap 0.
    for compound in compounds[1:]:
        columns[("level", compound)] = (race_laps["compound"] == compound).astype(float)
    for compound in compounds:
        columns[("wear", compound)] = tyre_age * (race_laps["compound"] == compound)
    design = pd.DataFrame(columns)

    lap_time = race_laps["lap_duration"].to_numpy(float)
    if fixed_lap_effect is not None:
        lap_time = lap_time - fixed_lap_effect * race_laps["lap_number"].to_numpy(float)
    x = design.to_numpy()
    coefficients, _, rank, _ = np.linalg.lstsq(x, lap_time, rcond=None)
    coefficients = pd.Series(coefficients, index=design.columns)

    lap_effect, lap_effect_se = fixed_lap_effect, np.nan
    if fixed_lap_effect is None:
        residuals = lap_time - x @ coefficients.to_numpy()
        noise_variance = residuals @ residuals / (len(lap_time) - rank)
        covariance = noise_variance * np.linalg.pinv(x.T @ x)
        position = list(design.columns).index(("lap_number", ""))
        lap_effect = coefficients.iloc[position]
        lap_effect_se = np.sqrt(covariance[position, position])
    return {
        "baseline": coefficients["driver"],          # seconds, indexed by driver_number
        "lap_effect": float(lap_effect),             # seconds per lap of the race
        "lap_effect_se": float(lap_effect_se),
        "wear": coefficients["wear"],                # straight-line wear, seconds per lap of tyre age
        "laps": len(lap_time),
        "full_rank": rank == design.shape[1],
    }


def tyre_residual(race_laps, baseline, lap_effect):
    """Return lap time minus the driver baseline and the lap-number effect (what step B fits)."""
    return (race_laps["lap_duration"] - race_laps["driver_number"].map(baseline)
            - lap_effect * race_laps["lap_number"]).astype(float)


def fit_tyre_curve(tyre_age, residual, kernel=None):
    """Fit step B for one compound in one race: a Gaussian process of the residual on tyre age."""
    tyre_age = np.asarray(tyre_age, dtype=float).reshape(-1, 1)
    residual = np.asarray(residual, dtype=float)
    # The residual is centred and scaled by hand (not with normalize_y), so
    # the predictions can be turned back into seconds without the noise.
    centre, scale = residual.mean(), residual.std()
    gp = GaussianProcessRegressor(kernel=tyre_kernel() if kernel is None else kernel,
                                  n_restarts_optimizer=GP_RESTARTS, random_state=RANDOM_SEED)
    with warnings.catch_warnings():
        # A parameter that stops at a bound means that part of the kernel
        # was not needed in this fit; it is not a failed fit. Only these
        # warnings are filtered, and the parameters are recorded below.
        # Every other warning (an optimizer that fails, for example) shows.
        warnings.filterwarnings("ignore", category=ConvergenceWarning,
                                message=".*is close to the specified (lower|upper) bound.*")
        gp.fit(tyre_age, (residual - centre) / scale)
    fitted = gp.kernel_.get_params()
    length_scale = [value for name, value in fitted.items() if name.endswith("length_scale")][0]
    return {"gp": gp, "centre": centre, "scale": scale, "length_scale": float(length_scale),
            "length_scale_at_bound": bool(np.isclose(length_scale, MIN_LENGTH_SCALE)),
            "parameters_at_bound": parameters_at_bound(gp.kernel_)}


def parameters_at_bound(kernel):
    """List the fitted kernel parameters that sit at a bound, for example "rbf_length_scale (lower)"."""
    short_names = {"RBF": "rbf", "Matern": "matern", "DotProduct": "dot", "WhiteKernel": "white"}
    parts = kernel.get_params()
    found = []
    # theta and bounds are on the log scale, in the order of the hyperparameters;
    # the comparison is the one scikit-learn uses for its warning.
    for hyperparameter, value, (lower, upper) in zip(kernel.hyperparameters, kernel.theta, kernel.bounds):
        side = "lower" if np.isclose(value, lower) else "upper" if np.isclose(value, upper) else None
        if side is None:
            continue
        # A name such as "k1__k1__k2__length_scale" is the path to the part
        # of the kernel that owns the parameter, then the parameter itself.
        path, parameter = hyperparameter.name.rsplit("__", 1)
        owner = parts[path]
        if isinstance(owner, ConstantKernel):
            # A constant is the amplitude of the part it multiplies (its partner k2).
            owner, parameter = parts[path[:-1] + "2"], "amplitude"
        found.append(f"{short_names[type(owner).__name__]}_{parameter} ({side})")
    return ", ".join(found)


def tyre_curve_distribution(curve, tyre_age):
    """Return the mean and covariance of the tyre curve at the given ages, in seconds, without noise."""
    tyre_age = np.asarray(tyre_age, dtype=float).reshape(-1, 1)
    mean, covariance = curve["gp"].predict(tyre_age, return_cov=True)
    # scikit-learn adds the WhiteKernel noise to the diagonal. The curve
    # itself is wanted, not a single noisy lap, so the noise is taken off.
    noise_level = curve["gp"].kernel_.k2.noise_level
    covariance = covariance - noise_level * np.eye(len(tyre_age))
    return curve["centre"] + curve["scale"] * mean, curve["scale"] ** 2 * covariance


def predict_tyre_curve(curve, tyre_age):
    """Return the mean and standard deviation of the tyre curve (seconds), without lap-to-lap noise."""
    mean, covariance = tyre_curve_distribution(curve, tyre_age)
    return mean, np.sqrt(np.clip(np.diag(covariance), 0.0, None))


def sample_tyre_curves(curve, tyre_age, n_samples, seed=RANDOM_SEED):
    """Draw whole tyre curves (one row per draw) from the fitted model, without lap-to-lap noise."""
    mean, covariance = tyre_curve_distribution(curve, tyre_age)
    rng = np.random.default_rng(seed)
    return rng.multivariate_normal(mean, covariance, size=n_samples, method="eigh")


def predict_lap_time(curve, baseline, lap_effect, lap_number, tyre_age):
    """Return the expected lap time and its standard deviation from the tyre curve, without noise."""
    curve_mean, curve_sd = predict_tyre_curve(curve, tyre_age)
    lap_time = baseline + lap_effect * np.asarray(lap_number, dtype=float) + curve_mean
    return lap_time, curve_sd
