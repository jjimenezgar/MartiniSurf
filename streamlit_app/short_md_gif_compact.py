"""Compact white-background Short MD GIF wrapper matching MartiniSolv."""
from __future__ import annotations

import io
from pathlib import Path

from streamlit_app.short_md_gif_pillow import generate_short_md_trajectory_gif as _base_generate


def _white_background(gif_bytes: bytes) -> bytes:
    """Replace the legacy near-black canvas with white while preserving glyphs."""
    try:
        from PIL import Image
    except ImportError:
        return gif_bytes

    source = Image.open(io.BytesIO(gif_bytes))
    frames = []
    durations = []
    for frame_index in range(getattr(source, "n_frames", 1)):
        source.seek(frame_index)
        rgb = source.convert("RGB")
        pixels = rgb.load()
        width, height = rgb.size
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                # MartiniSurf's legacy GIF canvas is #0E0D11.  Use a small
                # tolerance so palette quantization does not leave a dark halo.
                if r <= 24 and g <= 24 and b <= 28:
                    pixels[x, y] = (255, 255, 255)
        frames.append(rgb)
        durations.append(int(source.info.get("duration", 100)))

    if not frames:
        return gif_bytes
    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    return out.getvalue()


def generate_short_md_trajectory_gif(
    gro_path: Path | None,
    tpr_path: Path | None,
    xtc_path: Path | None,
    outdir: Path,
    selection_text: str,
    gmx_bin: str | None,
    *,
    frame_count_hint: int | None = None,
    show_protein: bool = True,
    show_surface: bool = True,
    show_linker: bool = False,
    show_water: bool = False,
    show_ions: bool = False,
    width: int = 720,
    height: int = 540,
    fps: int = 10,
    max_frames: int = 40,
    view_plane: str = "xz",
):
    gif_bytes, error, frame_count = _base_generate(
        gro_path,
        tpr_path,
        xtc_path,
        outdir,
        selection_text,
        gmx_bin,
        frame_count_hint=frame_count_hint,
        show_protein=show_protein,
        show_surface=show_surface,
        show_linker=show_linker,
        show_water=show_water,
        show_ions=show_ions,
        width=width,
        height=height,
        fps=fps,
        max_frames=max_frames,
        view_plane=view_plane,
    )
    if gif_bytes and not error:
        gif_bytes = _white_background(gif_bytes)
    return gif_bytes, error, frame_count
