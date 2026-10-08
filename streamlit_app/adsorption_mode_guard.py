"""Keep Adsorption builds and Short MD controls free of deposition artifacts."""
from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from pathlib import Path

from streamlit_app.adsorption_short_md import sanitize_adsorption_production_mdps


_DEPOSITION_MDP_NAMES = ("deposition.mdp", "deposition_dna.mdp")
_MARKER_KEY = "_short_md_deposition_forced_off_by_adsorption"
_PREVIOUS_KEY = "_short_md_deposition_before_adsorption"


def _is_adsorption_state(state: MutableMapping[str, object]) -> bool:
    return str(state.get("orientation_mode", "")).strip().lower() == "adsorption"


def sync_adsorption_short_md_default(state: MutableMapping[str, object]) -> None:
    """Force Deposition off in Adsorption and restore the prior choice afterwards."""
    adsorption = _is_adsorption_state(state)
    forced = bool(state.get(_MARKER_KEY, False))

    if adsorption:
        if not forced:
            state[_PREVIOUS_KEY] = bool(state.get("short_md_run_deposition", True))
            state[_MARKER_KEY] = True
        state["short_md_run_deposition"] = False
        return

    if forced:
        state["short_md_run_deposition"] = bool(state.get(_PREVIOUS_KEY, True))
        state[_MARKER_KEY] = False
        state.pop(_PREVIOUS_KEY, None)


def remove_adsorption_deposition_mdps(run_root: Path) -> list[Path]:
    """Remove stale deposition MDPs from an Adsorption Simulation_Files tree."""
    mdp_dir = Path(run_root) / "Simulation_Files" / "1_mdp"
    removed: list[Path] = []
    for name in _DEPOSITION_MDP_NAMES:
        path = mdp_dir / name
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed


def _args_use_adsorption(args: Sequence[object]) -> bool:
    return any(str(value).strip() == "--ads-mode" for value in args)


def install(app_module) -> None:
    """Install Adsorption-specific UI defaults and downloadable-file cleanup."""
    original_short_md_step = app_module._render_short_md_step
    original_run_martinisurf = app_module.run_martinisurf

    def render_short_md_step(outdir: Path) -> None:
        sync_adsorption_short_md_default(app_module.st.session_state)
        original_short_md_step(outdir)

    def run_martinisurf(args, run_root: Path, repo_root: Path):
        adsorption = _args_use_adsorption(args)
        sim_root = Path(run_root) / "Simulation_Files"
        if adsorption:
            # A project directory can be reused. Remove an old deposition MDP
            # before the new Adsorption build so it can never leak into exports.
            remove_adsorption_deposition_mdps(Path(run_root))
        result = original_run_martinisurf(args, run_root, repo_root)
        if adsorption:
            # Fresh Adsorption builds already skip deposition.mdp in the core
            # generator. This second cleanup also protects against stale files
            # left by older versions or interrupted/reused runs.
            remove_adsorption_deposition_mdps(Path(run_root))
            # Make the downloadable Production protocol match the intended
            # Adsorption physics: no protein POSRES or pulling, while SRF
            # freeze groups remain intact.
            sanitize_adsorption_production_mdps(sim_root)
        return result

    app_module._render_short_md_step = render_short_md_step
    app_module.run_martinisurf = run_martinisurf
