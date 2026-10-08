from __future__ import annotations

# Keep the established Streamlit UI in a stable module and apply focused
# refinements without duplicating the large app entrypoint.
import streamlit_app_legacy as _legacy
from streamlit_app.adsorption_mode_guard import install as _install_adsorption_mode_guard
from streamlit_app.short_md_dashboard import install as _install_short_md_dashboard
from streamlit_app.short_md_gif_compact import generate_short_md_trajectory_gif as _generate_short_md_trajectory_gif
from streamlit_app.short_md_gif_ui import install as _install_short_md_gif_ui

# streamlit_app_legacy imports the renderer by value. On Streamlit hot reloads
# that reference can remain bound to an older function. Rebind it explicitly so
# the UI and renderer always share the same compact white-background API.
_legacy.generate_short_md_trajectory_gif = _generate_short_md_trajectory_gif

_install_adsorption_mode_guard(_legacy)
_install_short_md_dashboard(_legacy)
_install_short_md_gif_ui(_legacy)
main = _legacy.main

if __name__ == "__main__":
    main()
