"""Regression tests for single-bead surface decoration in adsorption mode."""

import numpy as np
import pytest

from martinisurf.system_tethered import _append_surface_linkers, _oriented_linker_coords


def test_single_bead_linker_decorates_surface():
    protein = np.array([[0.0, 0.0, 2.0]])
    surface = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    linker = np.array([[0.3, 0.2, 0.1]])
    atoms = [(1, "LNK", "B1", 1)]
    result, final_atoms = _append_surface_linkers(
        protein, [], surface, linker, atoms, count=2, surface_min_dist=0.5
    )
    assert result.shape == (3, 3)
    assert len(final_atoms) == 2
    np.testing.assert_allclose(result[1:, 2], [0.5, 0.5])
    assert set(result[1:, 0]) == {0.0, 1.0}


def test_multi_bead_linker_still_requires_distinct_endpoints():
    with pytest.raises(ValueError, match="must be different"):
        _oriented_linker_coords(
            np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]]),
            np.array([0.0, 0.0, -1.0]),
            protein_index=0,
            surface_index=0,
        )
