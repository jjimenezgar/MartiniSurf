"""Streamlit interface helpers for MartiniSurf."""

from streamlit_app.resource_guard import install_subprocess_resource_guard
from streamlit_app.surface_reference import install_surface_reference_hook

install_subprocess_resource_guard()
install_surface_reference_hook()
