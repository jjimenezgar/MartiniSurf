from __future__ import annotations

from pathlib import Path

from streamlit_app.resource_guard import (
    XTC_DOWNSAMPLE_TARGET_BYTES,
    _is_gmx_trjconv_to_pdb,
    _resource_safe_trjconv_command,
)


def test_resource_guard_only_targets_trjconv_pdb() -> None:
    assert _is_gmx_trjconv_to_pdb(["gmx", "trjconv", "-f", "traj.xtc", "-o", "traj.pdb"])
    assert not _is_gmx_trjconv_to_pdb(["gmx", "trjconv", "-f", "traj.xtc", "-o", "traj.xtc"])
    assert not _is_gmx_trjconv_to_pdb(["gmx", "mdrun", "-deffnm", "run"])


def test_resource_guard_increases_skip_for_large_xtc(tmp_path: Path) -> None:
    xtc = tmp_path / "large.xtc"
    xtc.write_bytes(b"0" * (XTC_DOWNSAMPLE_TARGET_BYTES * 3 + 1))
    output = tmp_path / "preview.pdb"
    cmd = ["gmx", "trjconv", "-f", str(xtc), "-o", str(output), "-skip", "2"]

    safe = _resource_safe_trjconv_command(cmd)

    skip_index = safe.index("-skip")
    assert safe[skip_index + 1] == "8"
    assert cmd[cmd.index("-skip") + 1] == "2"  # original command is not mutated


def test_resource_guard_leaves_small_xtc_stride_unchanged(tmp_path: Path) -> None:
    xtc = tmp_path / "small.xtc"
    xtc.write_bytes(b"0" * 1024)
    output = tmp_path / "preview.pdb"
    cmd = ["gmx", "trjconv", "-f", str(xtc), "-o", str(output), "-skip", "3"]

    assert _resource_safe_trjconv_command(cmd) == cmd
