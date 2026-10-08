from __future__ import annotations

import inspect

from streamlit_app.short_md_dashboard import _performance_values
from streamlit_app.short_md_gif_pillow import generate_short_md_trajectory_gif


def test_gif_renderer_accepts_ui_controls() -> None:
    parameters = inspect.signature(generate_short_md_trajectory_gif).parameters
    assert "fps" in parameters
    assert "max_frames" in parameters
    assert "view_plane" in parameters


def test_performance_falls_back_to_wall_time() -> None:
    ns_day, hour_ns = _performance_values(
        {
            "name": "production",
            "time_ns": 1.0,
            "mdrun_elapsed_s": 20.0,
            "ns_day": None,
            "hour_ns": None,
        }
    )
    assert ns_day == 4320.0
    assert hour_ns is not None
    assert abs(hour_ns - (20.0 / 3600.0)) < 1e-12
