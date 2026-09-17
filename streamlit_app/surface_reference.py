from __future__ import annotations

from collections.abc import Callable

import streamlit as st


MARTINI3_BEAD_CLASSES = [
    {"Class": "C", "Meaning": "Apolar / non-polar", "Subtypes": "C1–C6", "Typical notation": "C1, SC1, TC1"},
    {"Class": "N", "Meaning": "Intermediate polarity", "Subtypes": "N1–N6", "Typical notation": "N4, SN4a, TN4d"},
    {"Class": "P", "Meaning": "Polar", "Subtypes": "P1–P6", "Typical notation": "P4, SP4, TP4"},
    {"Class": "Q", "Meaning": "Monovalent charged", "Subtypes": "Q1–Q5", "Typical notation": "Q5+, TQ5-"},
    {"Class": "X", "Meaning": "Halo compounds", "Subtypes": "X1–X4", "Typical notation": "X2, SX2, TX2"},
    {"Class": "D", "Meaning": "Divalent charged", "Subtypes": "Dedicated type", "Typical notation": "D (+2 / -2)"},
    {"Class": "W", "Meaning": "Water", "Subtypes": "Dedicated type", "Typical notation": "W"},
]

MARTINI3_BEAD_SIZES = [
    {"Prefix": "—", "Size": "Regular (R)", "Mapping guide": "4 heavy atoms : 1 bead", "σ self (nm)": 0.47, "Example": "P4"},
    {"Prefix": "S", "Size": "Small", "Mapping guide": "3 heavy atoms : 1 bead", "σ self (nm)": 0.41, "Example": "SP4"},
    {"Prefix": "T", "Size": "Tiny", "Mapping guide": "2 heavy atoms : 1 bead", "σ self (nm)": 0.34, "Example": "TP4"},
]

MARTINI3_CROSS_SIZES = [
    {"Pair": "R–S", "σ (nm)": 0.43},
    {"Pair": "R–T", "σ (nm)": 0.395},
    {"Pair": "S–T", "σ (nm)": 0.365},
]

MARTINI3_LABELS = [
    {"Label": "d", "Meaning": "Hydrogen-bond donor", "Applies mainly to": "P / N"},
    {"Label": "a", "Meaning": "Hydrogen-bond acceptor", "Applies mainly to": "P / N"},
    {"Label": "e", "Meaning": "Electron-rich", "Applies mainly to": "C / X"},
    {"Label": "v", "Meaning": "Electron-poor (vacancy)", "Applies mainly to": "C / X"},
]

_SURFACE_CAPTION = "All generated surface workflows use Martini 3 compatible bead definitions."
_HOOK_INSTALLED = False
_ORIGINAL_CAPTION: Callable[..., object] | None = None


def render_surface_bead_reference() -> None:
    """Render a compact, native Martini 3 bead reference for the Surface step."""
    with st.expander("Martini 3 bead type reference", expanded=False):
        st.caption(
            "Use this as a quick naming guide for surface beads. The chemical class controls "
            "interaction character; an optional S/T prefix changes bead size."
        )

        class_tab, size_tab, label_tab = st.tabs(["Chemical classes", "Bead sizes", "Specific labels"])
        with class_tab:
            st.dataframe(MARTINI3_BEAD_CLASSES, hide_index=True, width="stretch")
            st.caption(
                "P, N and C each span six polarity levels; Q spans five ion types and X four halo-compound types."
            )

        with size_tab:
            st.dataframe(MARTINI3_BEAD_SIZES, hide_index=True, width="stretch")
            st.caption("Cross-size Lennard–Jones σ values used in Martini 3:")
            st.dataframe(MARTINI3_CROSS_SIZES, hide_index=True, width="stretch")

        with label_tab:
            st.dataframe(MARTINI3_LABELS, hide_index=True, width="stretch")
            st.caption(
                "For charged Q beads, Martini 3 also defines charge-specific labels; consult the force-field documentation "
                "when parametrizing charged chemical groups."
            )

        st.info(
            "Example: `P4` is a regular polar bead, `SP4` is the small-size version and `TP4` the tiny-size version. "
            "For the default MartiniSurf hexagonal surface, `P4 P4` therefore denotes two regular P4 surface bead sites."
        )
        st.markdown(
            "Reference: [MartiniSurf bead map](https://github.com/BioKT/MartiniSurf/blob/master/martinisurf/data/CG_Beads_Martini3.png) · "
            "[Martini 3 small-molecule parametrization guide](https://cgmartini.nl/docs/tutorials/Martini3/Small_Molecule_Parametrization/)"
        )


def install_surface_reference_hook() -> None:
    """Attach the bead reference immediately after the Surface-step Martini 3 caption.

    The main Streamlit app is intentionally kept unchanged here; the package hook is narrow,
    idempotent, and only reacts to the exact Surface-step caption.
    """
    global _HOOK_INSTALLED, _ORIGINAL_CAPTION
    if _HOOK_INSTALLED:
        return

    _ORIGINAL_CAPTION = st.caption

    def caption_with_surface_reference(body, *args, **kwargs):
        result = _ORIGINAL_CAPTION(body, *args, **kwargs)
        if str(body) == _SURFACE_CAPTION:
            render_surface_bead_reference()
        return result

    st.caption = caption_with_surface_reference
    _HOOK_INSTALLED = True
