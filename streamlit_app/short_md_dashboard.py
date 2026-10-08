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


def install(app_module) -> None:
    """Patch the loaded root Streamlit module with improved Short MD UX."""
    st = app_module.st
    original_artifacts = app_module._short_md_stage_artifacts

    def stage_artifacts() -> dict[str, dict[str, Path | None]]:
        artifacts = dict(original_artifacts())
        work_dir = _existing(st.session_state.get("short_md_work_dir"))
        stage_rows = st.session_state.get("short_md_stage_results") or []
        completed = {str(row.get("name", "")).strip().lower() for row in stage_rows}

        # The runner records the final-stage paths explicitly. Use those as a
        # reliable production fallback instead of depending only on filename
        # globbing; this fixes completed production runs missing from the UI.
        if "production" in completed and "production" not in artifacts:
            gro = _existing(st.session_state.get("short_md_last_gro"))
            tpr = _existing(st.session_state.get("short_md_last_tpr"))
            xtc = _existing(st.session_state.get("short_md_last_xtc"))
            if gro:
                artifacts["production"] = {"gro": gro, "tpr": tpr, "xtc": xtc}

        # Recover any other completed stage from its output files if a custom
        # simulation name or stale browser state confused the old exact prefix.
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

        # Keep the protocol order rather than filesystem/glob order.
        return {stage: artifacts[stage] for stage in app_module.STAGE_ORDER if stage in artifacts}

    def render_per_stage_performance() -> None:
        stage_rows = st.session_state.get("short_md_stage_results") or []
        if not stage_rows:
            return
        rows = []
        for row in stage_rows:
            stage = str(row.get("name", "")).strip().lower()
            label = "Minimization" if stage == "minimization" else app_module._short_md_stage_label(stage)
            rows.append({
                "Stage": label,
                "dt (ps)": row.get("dt_ps"),
                "time (ns)": row.get("time_ns"),
                "nsteps": row.get("nsteps"),
                "GROMPP": app_module.format_elapsed(float(row.get("grompp_elapsed_s") or 0.0)),
                "MDRUN": app_module.format_elapsed(float(row.get("mdrun_elapsed_s") or 0.0)),
                "ns/day": round(float(row["ns_day"]), 4) if row.get("ns_day") is not None else None,
                "h/ns": round(float(row["hour_ns"]), 4) if row.get("hour_ns") is not None else None,
                "saved frame dt (ps)": row.get("saved_frame_dt_ps"),
            })

        with st.container(border=True):
            st.markdown("#### Performance by stage")
            st.caption("GROMACS timing and throughput for every completed Short MD stage.")
            st.dataframe(rows, hide_index=True, use_container_width=True)

            selected = str(st.session_state.get("short_md_view_stage", "production")).lower()
            selected_row = next((row for row in stage_rows if str(row.get("name", "")).lower() == selected), None)
            if selected_row and selected_row.get("ns_day") is not None:
                a, b, c = st.columns(3)
                a.metric(
                    f"{app_module._short_md_stage_label(selected)} throughput",
                    f"{float(selected_row['ns_day']):.3f} ns/day",
                )
                b.metric("hours/ns", f"{float(selected_row.get('hour_ns') or 0.0):.3f}")
                c.metric(
                    "MDRUN wall time",
                    app_module.format_elapsed(float(selected_row.get("mdrun_elapsed_s") or 0.0)),
                )

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
