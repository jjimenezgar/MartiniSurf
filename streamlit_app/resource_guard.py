from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Any


XTC_DOWNSAMPLE_TARGET_BYTES = 8 * 1024 * 1024
MAX_PREVIEW_PDB_BYTES = 24 * 1024 * 1024
_GUARD_INSTALLED = False
_ORIGINAL_RUN = subprocess.run


def _arg_value(cmd: list[str], flag: str) -> str | None:
    try:
        index = cmd.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(cmd):
        return None
    return cmd[index + 1]


def _is_gmx_trjconv_to_pdb(cmd: list[str]) -> bool:
    if len(cmd) < 2 or cmd[1] != "trjconv":
        return False
    output = _arg_value(cmd, "-o")
    return bool(output and Path(output).suffix.lower() == ".pdb")


def _resource_safe_trjconv_command(cmd: list[str]) -> list[str]:
    safe_cmd = list(cmd)
    xtc_text = _arg_value(safe_cmd, "-f")
    if not xtc_text:
        return safe_cmd

    xtc_path = Path(xtc_text)
    if not xtc_path.exists():
        return safe_cmd

    try:
        xtc_size = xtc_path.stat().st_size
    except OSError:
        return safe_cmd

    size_factor = max(1, math.ceil(xtc_size / XTC_DOWNSAMPLE_TARGET_BYTES))
    if size_factor <= 1:
        return safe_cmd

    try:
        skip_index = safe_cmd.index("-skip")
        current_skip = max(1, int(safe_cmd[skip_index + 1]))
        safe_cmd[skip_index + 1] = str(current_skip * size_factor)
    except (ValueError, IndexError):
        safe_cmd.extend(["-skip", str(size_factor)])
    return safe_cmd


def _guarded_run(cmd: Any, *args: Any, **kwargs: Any):
    if not isinstance(cmd, (list, tuple)):
        return _ORIGINAL_RUN(cmd, *args, **kwargs)

    string_cmd = [str(part) for part in cmd]
    if not _is_gmx_trjconv_to_pdb(string_cmd):
        return _ORIGINAL_RUN(cmd, *args, **kwargs)

    safe_cmd = _resource_safe_trjconv_command(string_cmd)
    result = _ORIGINAL_RUN(safe_cmd, *args, **kwargs)
    output_text = _arg_value(safe_cmd, "-o")
    if result.returncode != 0 or not output_text:
        return result

    output_path = Path(output_text)
    try:
        output_size = output_path.stat().st_size
    except OSError:
        return result

    if output_size <= MAX_PREVIEW_PDB_BYTES:
        return result

    try:
        output_path.unlink()
    except OSError:
        pass

    detail = (
        f"MartiniSurf resource guard: converted trajectory preview was "
        f"{output_size / (1024 * 1024):.1f} MB, above the "
        f"{MAX_PREVIEW_PDB_BYTES / (1024 * 1024):.0f} MB hosted-memory budget. "
        "The trajectory preview was skipped; use the final GRO preview or download the XTC for local analysis."
    )
    prior_stderr = getattr(result, "stderr", None)
    stderr = (str(prior_stderr).rstrip() + "\n" + detail).strip() if prior_stderr else detail
    return subprocess.CompletedProcess(
        args=safe_cmd,
        returncode=2,
        stdout=getattr(result, "stdout", None),
        stderr=stderr,
    )


def install_subprocess_resource_guard() -> None:
    """Protect Streamlit from oversized GROMACS trjconv -> PDB previews.

    Only `gmx trjconv` calls whose output is PDB are touched. Simulation commands
    such as grompp/mdrun and non-GROMACS subprocesses are passed through unchanged.
    """
    global _GUARD_INSTALLED
    if _GUARD_INSTALLED:
        return
    subprocess.run = _guarded_run
    _GUARD_INSTALLED = True
