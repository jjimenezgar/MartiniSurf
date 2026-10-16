"""Regression for bead selectors in adsorption surface decoration."""
from pathlib import Path
from streamlit_app.command_builder import BuildConfig, build_args


def test_adsorption_passes_both_linker_endpoints():
    config = BuildConfig(
        input_path="1UBQ", orientation_mode="Adsorption", ads_mode=True,
        linker_path=Path("LINKER.gro"), surface_linkers=5,
        linker_surface_bead="1:C1", linker_protein_bead="4:C4",
    )
    args = build_args(config)
    assert args[args.index("--linker-surface-bead") + 1] == "1:C1"
    assert args[args.index("--linker-protein-bead") + 1] == "4:C4"
    assert "--ads-mode" in args


def test_linker_mode_passes_each_selector_once():
    config = BuildConfig(
        input_path="1UBQ", orientation_mode="Linker",
        linker_path=Path("LINKER.gro"),
        linker_surface_bead="1:C1", linker_protein_bead="4:C4",
    )
    args = build_args(config)
    assert args.count("--linker-protein-bead") == 1
    assert args.count("--linker-surface-bead") == 1
