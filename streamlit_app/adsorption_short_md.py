"""Make Short MD adsorption runs skip the deposition stage.

Adsorption-mode builds intentionally do not generate deposition.mdp or the
restrained production topology used by the deposition workflow.  The generic
Short MD defaults still enable deposition, which makes an otherwise valid
adsorption test fail before production.  This hook keeps deposition behaviour
unchanged while making adsorption tests use the unrestrained equilibrium
protein topology.
"""
from __future__ import annotations

from dataclasses import replace
from functools import wraps
from pathlib import Path

from streamlit_app import short_md as _short_md


def is_adsorption_short_md(sim_root: Path) -> bool:
    """Return True only for a system that looks like an Adsorption build.

    A Deposition build has a deposition MDP and normally a restrained
    production topology.  Adsorption intentionally has neither.  Requiring
    both signals avoids hiding a genuinely broken Deposition build.
    """
    sim_root = Path(sim_root)
    mdp_dir = sim_root / "1_mdp"
    top_dir = sim_root / "0_topology"

    deposition_mdp_present = any(
        (mdp_dir / name).is_file()
        for name in ("deposition.mdp", "deposition_dna.mdp")
    )
    restrained_topology_present = any(
        (top_dir / name).is_file()
        for name in ("system_final_res.top", "system_res.top")
    )
    return not deposition_mdp_present and not restrained_topology_present


def adsorption_config(sim_root: Path, config: _short_md.ShortMDConfig) -> _short_md.ShortMDConfig:
    """Remove deposition from an Adsorption Short MD protocol, if selected."""
    if not is_adsorption_short_md(sim_root):
        return config

    stages = tuple(stage for stage in config.stages if stage.name != "deposition")
    if stages == config.stages:
        return config
    return replace(config, stages=stages)


def install_adsorption_short_md_hook() -> None:
    """Patch the public runner once, preserving the existing call signature."""
    current = _short_md.run_short_md
    if getattr(current, "_martinisurf_adsorption_aware", False):
        return

    @wraps(current)
    def run_short_md(
        sim_root: Path,
        config: _short_md.ShortMDConfig,
        repo_root: Path,
        extra_tool_dirs: list[Path] | None = None,
    ) -> _short_md.ShortMDResult:
        updated_config = adsorption_config(sim_root, config)
        result = current(sim_root, updated_config, repo_root, extra_tool_dirs)
        if updated_config is not config:
            note = (
                "Adsorption mode: deposition stage skipped; the protein is free "
                "to translate and rotate using the equilibrium (unrestrained) topology.\n"
            )
            result.stdout = note + result.stdout
        return result

    run_short_md._martinisurf_adsorption_aware = True
    _short_md.run_short_md = run_short_md
