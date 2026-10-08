from pathlib import Path

from streamlit_app.adsorption_short_md import (
    is_adsorption_short_md,
    sanitize_adsorption_production_mdp_text,
    sanitize_adsorption_production_mdps,
)


def test_adsorption_detection_allows_compatibility_restrained_topology(tmp_path: Path):
    sim_root = tmp_path / "Simulation_Files"
    (sim_root / "1_mdp").mkdir(parents=True)
    (sim_root / "0_topology").mkdir(parents=True)
    (sim_root / "0_topology" / "system_res.top").write_text("compatibility topology\n")
    (sim_root / "1_mdp" / "production.mdp").write_text("integrator = md\n")

    assert is_adsorption_short_md(sim_root)

    (sim_root / "1_mdp" / "deposition.mdp").write_text("integrator = md\n")
    assert not is_adsorption_short_md(sim_root)


def test_adsorption_production_removes_protein_posres_and_pull_but_keeps_surface_freeze():
    source = """define = -DPOSRES -DOTHER
integrator = md
freezegrps = SRF
freezedim = Y Y Y
pull = yes
pull-ngroups = 2
pull-group1-name = Anchor_1
pull-coord1-k = 500
"""
    sanitized = sanitize_adsorption_production_mdp_text(source)

    assert "-DPOSRES" not in sanitized
    assert "-DOTHER" in sanitized
    assert "pull = yes" not in sanitized
    assert "pull-ngroups" not in sanitized
    assert "pull-coord1-k" not in sanitized
    assert "pull                     = no" in sanitized
    assert "freezegrps = SRF" in sanitized
    assert "freezedim = Y Y Y" in sanitized


def test_adsorption_production_mdp_file_is_sanitized(tmp_path: Path):
    sim_root = tmp_path / "Simulation_Files"
    mdp_dir = sim_root / "1_mdp"
    mdp_dir.mkdir(parents=True)
    production = mdp_dir / "production.mdp"
    production.write_text("define = -DPOSRES\npull = yes\nfreezegrps = SRF\n")

    changed = sanitize_adsorption_production_mdps(sim_root)

    assert changed == [production]
    text = production.read_text()
    assert "POSRES" not in text
    assert "pull = yes" not in text
    assert "pull                     = no" in text
    assert "freezegrps = SRF" in text
