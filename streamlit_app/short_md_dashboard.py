"""Short MD result/dashboard refinements for the Streamlit app.

Kept separate from the large root UI module so stage discovery and performance
reporting remain independently testable.
"""
from __future__ import annotations

from pathlib import Path


def _existing(value) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.exists() else None


def _performance_values(row: dict[str, object]) -> tuple[float | None, float | None]:
    """Return ns/day and h/ns, falling back to measured wall time when needed.

    Some GROMACS versions print the performance summary in a format that the
    legacy parser does not recognize. For dynamics stages we can still derive
    throughput from simulated time and measured MDRUN wall time. Minimization
    has no simulated nanoseconds, so throughput is undefined.
    """
    ns_day = row.get("ns_day")
    hour_ns = row.get("hour_ns")
    if ns_day is not None and hour_ns is not None:
        return float(ns_day), float(hour_ns)

    time_ns = row.get("time_ns")
    elapsed_s = float(row.get("mdrun_elapsed_s") or 0.0)
    if time_ns is None or elapsed_s <= 0:
        return None, None
    simulated_ns = float(time_ns)
    if simulated_ns <= 0:
        return None, None

    ns_day_fallback = simulated_ns * 86400.0 / elapsed_s
    hour_ns_fallback = elapsed_s / (3600.0 * simulated_ns)
    return ns_day_fallback, hour_ns_fallback


def install(app_module) -> None:
    """Patch the loaded root Streamlit module with improved Short MD UX."""
    st = app_module.st
    original_artifacts = app_module._short_md_stage_artifacts

    def stage_artifacts() -> dict[str, dict[str, Path | None]]:
        artifacts = dict(original_artifacts())
        work_dir = _existing(st.session_state.get("short_md_work_dir"))
        stage_rows = st.session_state.get("short_md_stage_results") or []
        completed = {str(row.get("name", "")).strip().lower() for row in stage_rows}

        if "production" in completed and "production" not in artifacts:
            gro = _existing(st.session_state.get("short_md_last_gro"))
            tpr = _existing(st.session_state.get("short_md_last_tpr"))
            xtc = _existing(st.session_state.get("short_md_last_xtc"))
            if gro:
                artifacts["production"] = {"gro": gro, "tpr": tpr, "xtc": xtc}

        if work_dir:
            for stage in app_module.STAGE_ORDER:
                if stage in artifacts or stage not in completed:
                    continue
                candidates = sorted(work_dir.glob(f"*_{stage}.gro")) + sorted(work_dir.glob(f"*{stage}*.gro"))
                gro = next((path for path in candidates if path.is_file()), None)
                if not gro:
                    continue
                stem = gro.with_suffix("")
                tpr = stem.with_suffix(".tpr")
                xtc = stem.with_suffix(".xtc")
                artifacts[stage] = {
                    "gro": gro,
                    "tpr": tpr if tpr.exists() else None,
                    "xtc": xtc if xtc.exists() else None,
                }

        return {stage: artifacts[stage] for stage in app_module.STAGE_ORDER if stage in artifacts}

    def render_per_stage_performance() -> None:
        stage_rows = st.session_state.get("short_md_stage_results") or []
        if not stage_rows:
            return

        rows = []
        for row in stage_rows:
            stage = str(row.get("name", "")).strip().lower()
            label = "MINIMIZATION" if stage == "minimization" else app_module._short_md_stage_label(stage).upper()
            wall_time_s = float(row.get("mdrun_elapsed_s") or 0.0)
            ns_day, _hour_ns = _performance_values(row)
            rows.append(
                {
                    "Stage": label,
                    "Wall time (s)": round(wall_time_s, 2),
                    "Performance (ns/day)": f"{ns_day:.3f}" if ns_day is not None else "—",
                }
            )

        with st.container(border=True):
            st.markdown("#### Performance by stage")
            st.dataframe(rows, hide_index=True, use_container_width=True)

    def render_results() -> None:
        returncode = st.session_state.get("short_md_returncode")
        if returncode is None:
            return
        if returncode == 0:
            st.success("Short MD finished successfully.")
        else:
            st.error("Short MD failed.")

        render_per_stage_performance()

        if returncode == 0:
            app_module._render_short_md_viewer()

        zip_path_text = st.session_state.get("short_md_zip_path")
        if zip_path_text:
            zip_path = Path(str(zip_path_text))
            if zip_path.exists():
                st.download_button(
                    "Download Short MD files",
                    zip_path.read_bytes(),
                    "Short_MD_Files.zip",
                    "application/zip",
                    width="stretch",
                )

        with st.expander("Short MD execution log", expanded=returncode != 0):
            stdout = st.session_state.get("short_md_stdout", "")
            stderr = st.session_state.get("short_md_stderr", "")
            command_log = st.session_state.get("short_md_command_log") or []
            if command_log:
                st.code("\n".join(command_log), language="bash")
            st.code((stdout + "\n" + stderr).strip() or "No Short MD log yet.", language="text")

    app_module._short_md_stage_artifacts = stage_artifacts
    app_module._render_short_md_results = render_results
