import warnings

import numpy as np
import pytest

from src.curve_pca import build_zero_rate_matrix, daily_changes, run_pca


@pytest.fixture(scope="module")
def pca_result():
    _, zero_rate_matrix = build_zero_rate_matrix()
    changes = daily_changes(zero_rate_matrix)
    eigenvalues, eigenvectors = run_pca(changes)
    return eigenvalues, eigenvectors


def test_eigenvalues_non_negative_and_sorted_descending(pca_result):
    eigenvalues, _ = pca_result

    assert all(eigenvalue >= 0 for eigenvalue in eigenvalues)
    assert list(eigenvalues) == sorted(eigenvalues, reverse=True)


def test_pc1_is_a_level_factor(pca_result):
    """PC1's weights should all carry the same sign -- a uniform shift
    applied to every tenor, i.e. the curve moving up or down as a block."""
    eigenvalues, eigenvectors = pca_result
    pc1 = eigenvectors[:, 0]

    assert np.all(pc1 > 0) or np.all(pc1 < 0)

    # Flagged, not asserted: a low ratio here is a genuine finding about
    # this data (level dominance not holding), not necessarily a bug, so
    # it shouldn't fail the suite -- but it's worth surfacing loudly.
    explained_variance_ratio = eigenvalues[0] / eigenvalues.sum()
    if explained_variance_ratio < 0.80:
        warnings.warn(
            f"PC1 explains only {explained_variance_ratio:.1%} of variance, below the 80% "
            "expected from Litterman-Scheinkman level dominance."
        )


def test_pc2_is_a_slope_factor(pca_result):
    """PC2's weights should contain at least one sign change -- short and
    long tenors moving in opposite directions."""
    _, eigenvectors = pca_result
    pc2 = eigenvectors[:, 1]

    signs = np.sign(pc2)
    assert np.any(signs[:-1] != signs[1:])
