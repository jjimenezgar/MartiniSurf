from __future__ import annotations

# Keep the established Streamlit UI in a stable module and apply focused
# Short-MD dashboard refinements without duplicating the 90k-line app entrypoint.
import streamlit_app_legacy as _legacy
from streamlit_app.short_md_dashboard import install as _install_short_md_dashboard

_install_short_md_dashboard(_legacy)
main = _legacy.main

if __name__ == "__main__":
    main()
