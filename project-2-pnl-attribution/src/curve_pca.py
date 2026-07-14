"""PCA on daily changes in the bootstrapped GBP SONIA zero-rate curve.

Historical BoE OIS spot rates (data/processed/boe_historical_curves.csv,
see src/data_ingestion.py) are treated as par-rate-equivalent quotes and
bootstrapped per date -- same convention as the rest of this project
(Project 1's single-curve, par-swap-equation bootstrap). This keeps every
z(T) in this project meaning "bootstrapped zero rate", never a raw BoE
quote used directly as if it were already a zero rate.
"""

import csv
import importlib.util
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.swap import Curve

_BOOTSTRAP_PATH = (
    Path(__file__).resolve().parent.parent.parent / "project-1-curve-construction" / "src" / "bootstrap.py"
)
_bootstrap_spec = importlib.util.spec_from_file_location("project1_bootstrap", _BOOTSTRAP_PATH)
_bootstrap_module = importlib.util.module_from_spec(_bootstrap_spec)
_bootstrap_spec.loader.exec_module(_bootstrap_module)
bootstrap_curve = _bootstrap_module.bootstrap_curve

HISTORICAL_CSV = Path("data/processed/boe_historical_curves.csv")
TENORS = list(range(1, 11))


def build_zero_rate_matrix(csv_path: Path = HISTORICAL_CSV) -> tuple[list[str], np.ndarray]:
    """Bootstrap a Curve for each date in the historical archive and extract
    zero_rate(T) for T=1..10.

    Returns (dates, matrix) where matrix is (num_dates x 10), column order
    matching TENORS (1Y..10Y).
    """
    dates = []
    zero_rates = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            quotes = [(float(tenor), float(row[f"{tenor}Y"])) for tenor in TENORS]
            dfs = bootstrap_curve(quotes)
            curve = Curve(dfs)
            zero_rates.append([curve.zero_rate(float(tenor)) for tenor in TENORS])
            dates.append(row["date"])
    return dates, np.array(zero_rates)


def daily_changes(zero_rate_matrix: np.ndarray) -> np.ndarray:
    """(num_dates x 10) -> (num_dates-1 x 10) day-over-day differences."""
    return np.diff(zero_rate_matrix, axis=0)


def run_pca(changes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Eigendecompose the 10x10 covariance matrix of daily changes.

    Returns (eigenvalues, eigenvectors), sorted descending by eigenvalue.
    eigenvectors[:, i] is the i-th principal component (10 tenor weights).
    """
    cov = np.cov(changes, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    order = np.argsort(eigenvalues)[::-1]
    return eigenvalues[order], eigenvectors[:, order]


def main() -> None:
    dates, zero_rate_matrix = build_zero_rate_matrix()
    changes = daily_changes(zero_rate_matrix)
    eigenvalues, eigenvectors = run_pca(changes)

    explained_variance_ratio = eigenvalues / eigenvalues.sum()

    print(f"{len(dates)} dates ({dates[0]} to {dates[-1]}), {changes.shape[0]} daily changes\n")

    header = "        " + "".join(f"{tenor}Y".rjust(8) for tenor in TENORS)
    for i in range(3):
        print(f"PC{i + 1}  (explained variance: {explained_variance_ratio[i]:.2%})")
        print(header)
        print("weights " + "".join(f"{w:>8.3f}" for w in eigenvectors[:, i]))
        print()

    fig, ax = plt.subplots()
    for i in range(3):
        ax.plot(TENORS, eigenvectors[:, i], marker="o", label=f"PC{i + 1}")
    ax.axhline(0, color="grey", linewidth=0.5)
    ax.set_xlabel("Tenor (years)")
    ax.set_ylabel("Eigenvector weight")
    ax.set_title("Top 3 principal components of daily zero-rate changes")
    ax.legend()
    plt.show()


if __name__ == "__main__":
    main()
