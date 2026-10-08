"""Adsorption-aware Short MD handling.

Adsorption builds intentionally omit the deposition MDP.  During Production the
protein must be free to translate and rotate; only the surface should remain
fixed.  This hook therefore removes Deposition from the protocol, sanitizes the
Production MDP so protein POSRES/pulling cannot be active, and forces the core
runner to use the equilibrium topology instead of a compatibility *_res.top.
"""
from __future__ import annotations

from dataclasses import replace
from functools import wraps
from pathlib import Path

from streamlit_app import short_md as _short_md


def is_adsorption_short_md(sim_root: Path) -> bool:
    """Detect an Adsorption build from the intentionally absent deposition MDP.

    Current Adsorption builds can still contain ``system_res.top`` as a
    compatibility topology, so the presence of that file is no longer a valid
    discriminator.  Deposition MDP absence is the stable protocol signal.
    """
    sim_root = Path(sim_root)
    mdp_dir = sim_root / "1_mdp"
    return not any(
        (mdp_dir / name).is_file()
        for name in ("deposition.mdp", "deposition_dna.mdp")
    )


def adsorption_config(sim_root: Path, config: _short_md.ShortMDConfig) -> _short_md.ShortMDConfig:
    """Remove deposition from an Adsorption Short MD protocol, if selected."""
    if not is_adsorption_short_md(sim_root):
        return config

    stages = tuple(stage for stage in config.stages if stage.name != "deposition")
    if stages == config.stages:
        return config
    return replace(config, stages=stages)


def sanitize_adsorption_production_mdp_text(text: str) -> str:
    """Return a Production MDP with protein POSRES and pulling disabled.

    ``freezegrps = SRF`` is deliberately preserved, so the surface remains the
    fixed laboratory reference while the protein is free to diffuse.
    """
    out: list[str] = []
    define_written = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith(";") or "=" not in stripped:
            out.append(raw)
            continue

        key, value = stripped.split("=", 1)
        key_clean = key.strip().lower()
        if key_clean == "define":
            tokens = [token for token in value.split() if token.upper() not in {"-DPOSRES", "POSRES"}]
            if tokens:
                out.append(f"define                   = {' '.join(tokens)}")
                define_written = True
            continue
        if key_clean == "pull" or key_clean.startswith("pull-"):
            continue
        out.append(raw)

    # Make the intended physics explicit for both humans and grompp.
    if out and out[-1].strip():
        out.append("")
    out.append("pull                     = no")
    return "\n".join(out).rstrip() + "\n"


def sanitize_adsorption_production_mdps(sim_root: Path) -> list[Path]:
    """Sanitize present Production MDPs in an Adsorption Simulation_Files tree."""
    mdp_dir = Path(sim_root) / "1_mdp"
    changed: list[Path] = []
    for name in ("production.mdp", "production_dna.mdp"):
        path = mdp_dir / name
        if not path.is_file():
            continue
        original = path.read_text()
        sanitized = sanitize_adsorption_production_mdp_text(original)
        if sanitized != original:
            path.write_text(sanitized)
            changed.append(path)
    return changed


def _temporarily_hide_restrained_topologies(sim_root: Path) -> list[tuple[Path, Path]]:
    """Hide compatibility restrained topologies so Production uses equilibrium topology."""
    top_dir = Path(sim_root) / "0_topology"
    moved: list[tuple[Path, Path]] = []
    for name in ("system_final_res.top", "system_res.top"):
        src = top_dir / name
        if not src.is_file():
            continue
        dst = src.with_name(src.name + ".adsorption-disabled")
        if dst.exists():
            dst.unlink()
        src.rename(dst)
        moved.append((src, dst))
    return moved


def _restore_hidden_topologies(moved: list[tuple[Path, Path]]) -> None:
    for original, hidden in reversed(moved):
        if hidden.exists():
            hidden.rename(original)


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
        adsorption = is_adsorption_short_md(sim_root)
        updated_config = adsorption_config(sim_root, config)
        moved: list[tuple[Path, Path]] = []
        if adsorption:
            sanitize_adsorption_production_mdps(sim_root)
            moved = _temporarily_hide_restrained_topologies(sim_root)
        try:
            result = current(sim_root, updated_config, repo_root, extra_tool_dirs)
        finally:
            _restore_hidden_topologies(moved)

        if adsorption:
            note = (
                "Adsorption mode: deposition skipped; Production uses the equilibrium "
                "topology with protein POSRES/pulling disabled, so the protein is free "
                "to translate and rotate while the surface remains fixed.\n"
            )
            result.stdout = note + result.stdout
        return result

    run_short_md._martinisurf_adsorption_aware = True
    _short_md.run_short_md = run_short_md
