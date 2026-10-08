from __future__ import annotations

# Keep the established Streamlit UI in a stable module and apply focused
# Short-MD refinements without duplicating the large app entrypoint.
import streamlit_app_legacy as _legacy
from streamlit_app.short_md_dashboard import install as _install_short_md_dashboard
from streamlit_app.short_md_gif_ui import install as _install_short_md_gif_ui

_install_short_md_dashboard(_legacy)
_install_short_md_gif_ui(_legacy)
main = _legacy.main

if __name__ == "__main__":
    main()
