from __future__ import annotations

from streamlit_app.adsorption_mode_guard import (
    remove_adsorption_deposition_mdps,
    sync_adsorption_short_md_default,
)


def test_adsorption_forces_deposition_off_and_restores_previous_choice() -> None:
    state = {
        "orientation_mode": "Adsorption",
        "short_md_run_deposition": True,
    }

    sync_adsorption_short_md_default(state)
    assert state["short_md_run_deposition"] is False

    # Even if a stale/imported state tries to turn it back on, Adsorption wins.
    state["short_md_run_deposition"] = True
    sync_adsorption_short_md_default(state)
    assert state["short_md_run_deposition"] is False

    state["orientation_mode"] = "Anchor"
    sync_adsorption_short_md_default(state)
    assert state["short_md_run_deposition"] is True


def test_adsorption_preserves_intentionally_disabled_deposition_after_leaving() -> None:
    state = {
        "orientation_mode": "Adsorption",
        "short_md_run_deposition": False,
    }
    sync_adsorption_short_md_default(state)
    state["orientation_mode"] = "Linker"
    sync_adsorption_short_md_default(state)
    assert state["short_md_run_deposition"] is False


def test_adsorption_cleanup_removes_standard_and_dna_deposition_mdps(tmp_path) -> None:
    mdp_dir = tmp_path / "Simulation_Files" / "1_mdp"
    mdp_dir.mkdir(parents=True)
    deposition = mdp_dir / "deposition.mdp"
    deposition_dna = mdp_dir / "deposition_dna.mdp"
    production = mdp_dir / "production.mdp"
    deposition.write_text("stale")
    deposition_dna.write_text("stale dna")
    production.write_text("keep")

    removed = remove_adsorption_deposition_mdps(tmp_path)

    assert set(removed) == {deposition, deposition_dna}
    assert not deposition.exists()
    assert not deposition_dna.exists()
    assert production.read_text() == "keep"
