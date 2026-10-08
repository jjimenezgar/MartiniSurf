"""Short MD GIF controls shared with the MartiniSurf legacy Streamlit UI."""
from __future__ import annotations

from pathlib import Path

from streamlit_app.short_md_gif_pillow import generate_short_md_trajectory_gif


_VIEW_OPTIONS = {
    "Side view · XZ": "xz",
    "Side view · YZ": "yz",
    "Top view · XY": "xy",
}


def install(app_module) -> None:
    """Replace the GIF control block with preview and scientific camera controls."""
    st = app_module.st

    def render_short_md_gif_controls(
        selected: dict[str, Path | None],
        outdir: Path,
        selection_text: str,
    ) -> None:
        st.session_state.setdefault("short_md_gif_fps", 10)
        st.session_state.setdefault("short_md_gif_max_frames", 40)
        st.session_state.setdefault("short_md_gif_view", "Side view · XZ")

        stage_name = str(st.session_state.short_md_view_stage)
        stage_label = app_module._short_md_stage_label(stage_name)
        gro = selected.get("gro")
        tpr = selected.get("tpr")
        xtc = selected.get("xtc")
        gmx = app_module.detect_gmx(app_module.TOOL_DIRS)
        gif_available = bool(gro and tpr and xtc and gmx)

        with st.container(border=True):
            st.markdown("#### Trajectory GIF")
            st.caption(
                "The GIF uses the same visible components as the trajectory viewer. "
                "Side views keep Z vertical so protein approach to an XY surface is easy to inspect."
            )
            settings = st.columns(3)
            settings[0].number_input(
                "FPS",
                min_value=1,
                max_value=30,
                step=1,
                key="short_md_gif_fps",
            )
            settings[1].number_input(
                "Max frames",
                min_value=2,
                max_value=120,
                step=1,
                key="short_md_gif_max_frames",
            )
            settings[2].selectbox(
                "View",
                list(_VIEW_OPTIONS),
                key="short_md_gif_view",
            )

            view_plane = _VIEW_OPTIONS.get(str(st.session_state.short_md_gif_view), "xz")
            signature = (
                stage_name,
                str(gro or ""),
                str(tpr or ""),
                str(xtc or ""),
                bool(st.session_state.short_md_view_protein),
                bool(st.session_state.short_md_view_surface),
                bool(st.session_state.short_md_view_linker),
                bool(st.session_state.short_md_view_water),
                bool(st.session_state.short_md_view_ions),
                int(st.session_state.short_md_gif_fps),
                int(st.session_state.short_md_gif_max_frames),
                view_plane,
            )

            actions = st.columns([0.45, 0.55])
            if actions[0].button(
                "Generate trajectory GIF",
                width="stretch",
                disabled=not gif_available,
            ):
                with st.spinner("Generating trajectory GIF"):
                    # Call the dependency-light renderer directly. This avoids a
                    # stale function reference in streamlit_app_legacy after a
                    # Streamlit hot reload, which previously caused TypeError
                    # when FPS/max_frames/view_plane were passed.
                    gif_bytes, error, frame_count = generate_short_md_trajectory_gif(
                        gro,
                        tpr,
                        xtc,
                        outdir,
                        selection_text,
                        gmx,
                        frame_count_hint=app_module._short_md_frame_count_hint(stage_name),
                        show_protein=bool(st.session_state.short_md_view_protein),
                        show_surface=bool(st.session_state.short_md_view_surface),
                        show_linker=bool(st.session_state.short_md_view_linker),
                        show_water=bool(st.session_state.short_md_view_water),
                        show_ions=bool(st.session_state.short_md_view_ions),
                        fps=int(st.session_state.short_md_gif_fps),
                        max_frames=int(st.session_state.short_md_gif_max_frames),
                        view_plane=view_plane,
                    )
                st.session_state["short_md_gif_signature"] = signature
                st.session_state["short_md_gif_error"] = error or ""
                st.session_state["short_md_gif_frames"] = frame_count
                st.session_state["short_md_gif_bytes"] = gif_bytes or b""
                st.session_state["short_md_gif_name"] = (
                    f"MartiniSurf_{stage_label.replace(' ', '_')}_trajectory.gif"
                )

            if not gif_available:
                actions[1].caption("Run a trajectory stage first to enable GIF export.")
                return

            matches = st.session_state.get("short_md_gif_signature") == signature
            gif_bytes = st.session_state.get("short_md_gif_bytes") if matches else b""
            error = st.session_state.get("short_md_gif_error") if matches else ""

            if gif_bytes:
                frame_count = int(st.session_state.get("short_md_gif_frames") or 0)
                actions[1].download_button(
                    f"Download GIF ({frame_count} frames)",
                    data=bytes(gif_bytes),
                    file_name=str(st.session_state.short_md_gif_name),
                    mime="image/gif",
                    width="stretch",
                )
                st.image(
                    bytes(gif_bytes),
                    caption=(
                        f"{stage_label} · {_VIEW_OPTIONS.get(str(st.session_state.short_md_gif_view), 'xz').upper()} "
                        f"· {int(st.session_state.short_md_gif_fps)} FPS · {frame_count} frames"
                    ),
                    width="stretch",
                )
            elif error:
                actions[1].warning(str(error))

    app_module._render_short_md_gif_controls = render_short_md_gif_controls
