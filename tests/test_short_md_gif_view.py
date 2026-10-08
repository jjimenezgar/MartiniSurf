from streamlit_app.short_md_gif_pillow import _project_point, _sample_indices


def test_side_views_keep_z_vertical() -> None:
    point = (1.0, 2.0, 3.0)
    assert _project_point(point, "xz") == (1.0, 3.0, 2.0)
    assert _project_point(point, "yz") == (2.0, 3.0, 1.0)


def test_top_view_uses_xy_plane() -> None:
    assert _project_point((1.0, 2.0, 3.0), "xy") == (1.0, 2.0, 3.0)


def test_frame_sampling_respects_user_limit() -> None:
    sampled = _sample_indices(100, 40)
    assert len(sampled) <= 40
    assert sampled[0] == 0
    assert sampled[-1] == 99
