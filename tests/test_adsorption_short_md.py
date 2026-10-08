from pathlib import Path

from streamlit_app.adsorption_short_md import adsorption_config, is_adsorption_short_md
from streamlit_app.short_md import ShortMDConfig, ShortMDStage


def _config() -> ShortMDConfig:
    return ShortMDConfig(
        stages=(
            ShortMDStage("nvt", True, 0.001, 0.02),
            ShortMDStage("npt", True, 0.005, 0.02),
            ShortMDStage("deposition", True, 0.01, 0.05),
            ShortMDStage("production", True, 0.01, 0.1),
        )
    )


def _tree(root: Path) -> None:
    (root / "0_topology").mkdir(parents=True)
    (root / "1_mdp").mkdir(parents=True)


def test_adsorption_build_skips_deposition(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert is_adsorption_short_md(tmp_path)

    original = _config()
    updated = adsorption_config(tmp_path, original)

    assert [stage.name for stage in updated.stages] == ["nvt", "npt", "production"]
    assert [stage.name for stage in original.stages] == ["nvt", "npt", "deposition", "production"]


def test_deposition_mdp_keeps_deposition_stage(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "1_mdp" / "deposition.mdp").write_text("integrator = md\n")

    assert not is_adsorption_short_md(tmp_path)
    config = _config()
    assert adsorption_config(tmp_path, config) is config


def test_restrained_topology_does_not_hide_broken_deposition_build(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "0_topology" / "system_final_res.top").write_text("; restrained topology\n")

    assert not is_adsorption_short_md(tmp_path)
    config = _config()
    assert adsorption_config(tmp_path, config) is config


def test_dna_deposition_mdp_is_recognized(tmp_path: Path) -> None:
    _tree(tmp_path)
    (tmp_path / "1_mdp" / "deposition_dna.mdp").write_text("integrator = md\n")

    assert not is_adsorption_short_md(tmp_path)
