from streamlit_app.short_md_dashboard import _performance_values


def test_performance_values_use_gromacs_values_when_present() -> None:
    assert _performance_values({"ns_day": 123.4, "hour_ns": 0.194}) == (123.4, 0.194)


def test_performance_values_fall_back_to_wall_time() -> None:
    ns_day, hour_ns = _performance_values({
        "ns_day": None,
        "hour_ns": None,
        "time_ns": 0.1,
        "mdrun_elapsed_s": 20.0,
    })
    assert ns_day == 432.0
    assert abs(hour_ns - (20.0 / 360.0)) < 1e-12


def test_minimization_has_no_throughput() -> None:
    assert _performance_values({"time_ns": None, "mdrun_elapsed_s": 5.0}) == (None, None)
