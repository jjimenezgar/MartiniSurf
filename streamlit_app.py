from __future__ import annotations

# Keep the established Streamlit UI in a stable module and apply focused
# refinements without duplicating the large app entrypoint.
import streamlit_app_legacy as _legacy
from streamlit_app.adsorption_mode_guard import install as _install_adsorption_mode_guard
from streamlit_app.short_md_dashboard import install as _install_short_md_dashboard
from streamlit_app.short_md_gif_pillow import generate_short_md_trajectory_gif as _generate_short_md_trajectory_gif
from streamlit_app.short_md_gif_ui import install as _install_short_md_gif_ui

# streamlit_app_legacy imports the renderer by value. On Streamlit hot reloads
# that reference can remain bound to the older Playwright-era function even
# though molecular_viewer has already been patched. Rebind it explicitly so
# the UI and renderer always share the same FPS/max_frames/view_plane API.
_legacy.generate_short_md_trajectory_gif = _generate_short_md_trajectory_gif

_install_adsorption_mode_guard(_legacy)
_install_short_md_dashboard(_legacy)
_install_short_md_gif_ui(_legacy)
main = _legacy.main

if __name__ == "__main__":
    main()
