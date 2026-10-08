import inspect
import io

from PIL import Image

from streamlit_app.short_md_gif_compact import _white_background, generate_short_md_trajectory_gif


def test_compact_gif_defaults_match_martinisolv_size():
    signature = inspect.signature(generate_short_md_trajectory_gif)
    assert signature.parameters["width"].default == 720
    assert signature.parameters["height"].default == 540


def test_white_background_replaces_legacy_dark_canvas():
    frame = Image.new("RGB", (12, 8), "#0E0D11")
    frame.putpixel((3, 3), (255, 79, 163))
    buffer = io.BytesIO()
    frame.save(buffer, format="GIF")

    converted = _white_background(buffer.getvalue())
    image = Image.open(io.BytesIO(converted)).convert("RGB")

    assert image.getpixel((0, 0)) == (255, 255, 255)
    assert image.getpixel((3, 3)) != (255, 255, 255)
