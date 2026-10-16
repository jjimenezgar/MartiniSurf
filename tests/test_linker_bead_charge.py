from pathlib import Path

import pytest

from streamlit_app.linker_generator import assign_linker_bead_charge


@pytest.fixture
def linker_itp(tmp_path: Path) -> Path:
    path = tmp_path / "linker.itp"
    path.write_text("[ moleculetype ]\nLNK 1\n\n[ atoms ]\n1 P4 1 LNK B1 1 0.0 72\n2 P4 1 LNK B2 2 0.0 72 ; bead two\n3 P4 1 LNK B3 3 0.0 72\n\n[ bonds ]\n1 2 1 0.47 1250\n")
    return path


@pytest.mark.parametrize("charge", [-2, -1, 0, 1, 2])
def test_assign_charge(linker_itp: Path, charge: int) -> None:
    assert assign_linker_bead_charge(linker_itp, 2, charge) == charge
    contents = linker_itp.read_text()
    assert f"2 P4 1 LNK B2 2 {charge} 72 ; bead two" in contents
    assert "[ bonds ]\n1 2 1 0.47 1250" in contents


def test_invalid_bead_does_not_modify_file(linker_itp: Path) -> None:
    original = linker_itp.read_text()
    with pytest.raises(ValueError, match="not found"):
        assign_linker_bead_charge(linker_itp, 99, 1)
    assert linker_itp.read_text() == original


def test_invalid_charge_does_not_modify_file(linker_itp: Path) -> None:
    original = linker_itp.read_text()
    with pytest.raises(ValueError, match="Charge must"):
        assign_linker_bead_charge(linker_itp, 1, 3)
    assert linker_itp.read_text() == original
