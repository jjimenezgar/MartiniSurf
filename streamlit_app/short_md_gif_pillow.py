"""Dependency-light Short MD GIF rendering for MartiniSurf.

The Streamlit deployment should not need Playwright/Chromium just to export a
trajectory GIF. This renderer uses mdtraj for XTC coordinates and Pillow for
2-D drawing. It keeps the surface reference frame when the surface is shown,
while protein-only views are rigidly aligned for a stable camera.
"""
from __future__ import annotations

import io
from pathlib import Path


def _minimum_image(delta, box):
    import numpy as np

    box = np.asarray(box, dtype=float)
    if box.shape != (3, 3) or abs(float(np.linalg.det(box))) < 1e-12:
        return delta
    fractional = np.linalg.solve(box.T, delta)
    fractional -= np.round(fractional)
    return fractional @ box


def _protein_indices(atoms):
    protein = []
    bb = []
    by_residue: dict[tuple[int, str], list[int]] = {}
    for index, atom in enumerate(atoms):
        name = str(atom.get("name", "")).strip().upper()
        key = (int(atom.get("resid", 0)), str(atom.get("resn", "")).strip())
        if name == "BB" or (name.startswith("BB") and name[2:].isdigit()) or name.startswith("SC"):
            protein.append(index)
            by_residue.setdefault(key, []).append(index)
            if name == "BB" or (name.startswith("BB") and name[2:].isdigit()):
                bb.append(index)
    return protein, bb, by_residue


def _make_protein_whole(xyz, boxes, atoms):
    """Reconstruct protein BB/sidechains across PBC without moving other components."""
    import numpy as np

    whole = np.asarray(xyz, dtype=float).copy()
    _protein, bb, by_residue = _protein_indices(atoms)
    if not bb:
        return whole
    bb = sorted(bb, key=lambda idx: (int(atoms[idx].get("resid", 0)), idx))
    for frame_index in range(whole.shape[0]):
        box = boxes[frame_index] if boxes is not None and len(boxes) > frame_index else None
        if box is None:
            continue
        for previous, current in zip(bb, bb[1:]):
            prev_resid = int(atoms[previous].get("resid", 0))
            cur_resid = int(atoms[current].get("resid", 0))
            if cur_resid < prev_resid or cur_resid - prev_resid > 2:
                continue
            delta = xyz[frame_index, current] - xyz[frame_index, previous]
            whole[frame_index, current] = whole[frame_index, previous] + _minimum_image(delta, box)
        for indices in by_residue.values():
            anchors = [idx for idx in indices if str(atoms[idx].get("name", "")).strip().upper().startswith("BB")]
            if not anchors:
                continue
            anchor = anchors[0]
            for idx in indices:
                if idx == anchor:
                    continue
                delta = xyz[frame_index, idx] - xyz[frame_index, anchor]
                whole[frame_index, idx] = whole[frame_index, anchor] + _minimum_image(delta, box)
    return whole


def _rigid_align(xyz, atom_indices):
    import numpy as np

    if not atom_indices:
        return np.asarray(xyz, dtype=float).copy()
    aligned = np.asarray(xyz, dtype=float).copy()
    reference = aligned[0, atom_indices]
    ref_center = reference.mean(axis=0)
    ref0 = reference - ref_center
    for frame_index in range(aligned.shape[0]):
        mobile = aligned[frame_index, atom_indices]
        mob_center = mobile.mean(axis=0)
        mob0 = mobile - mob_center
        u, _s, vt = np.linalg.svd(mob0.T @ ref0)
        rotation = u @ vt
        if np.linalg.det(rotation) < 0:
            u[:, -1] *= -1
            rotation = u @ vt
        aligned[frame_index] = (aligned[frame_index] - mob_center) @ rotation + ref_center
    return aligned


def _sample_indices(total: int, target: int) -> list[int]:
    if total <= target:
        return list(range(total))
    if target <= 1:
        return [0]
    return sorted({round(i * (total - 1) / (target - 1)) for i in range(target)})


def _stable_subsample(indices: list[int], limit: int) -> list[int]:
    if len(indices) <= limit:
        return indices
    return [indices[i] for i in _sample_indices(len(indices), limit)]


def _project_point(point, view_plane: str) -> tuple[float, float, float]:
    """Project 3-D coordinates onto a fixed scientific viewing plane.

    XZ and YZ are lateral views with Z kept vertical, which is the meaningful
    direction for protein approach to an XY surface. XY is retained as a top
    view for inspection of lateral motion.
    """
    x, y, z = map(float, point)
    plane = str(view_plane).strip().lower()
    if plane == "yz":
        return y, z, x
    if plane == "xy":
        return x, y, z
    return x, z, y


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
    width: int = 960,
    height: int = 700,
    fps: int = 10,
    max_frames: int = 40,
    view_plane: str = "xz",
) -> tuple[bytes | None, str | None, int]:
    """Generate a PBC-safe Short MD GIF with a surface-oriented fixed camera."""
    del tpr_path, outdir, selection_text, gmx_bin, frame_count_hint
    if not gro_path or not xtc_path:
        return None, "A GRO and XTC are required to generate the trajectory GIF.", 0
    if not Path(gro_path).exists() or not Path(xtc_path).exists():
        return None, "The selected trajectory files are not available anymore.", 0
    if int(fps) < 1:
        return None, "GIF FPS must be at least 1.", 0
    if int(max_frames) < 1:
        return None, "GIF max frames must be at least 1.", 0
    if str(view_plane).lower() not in {"xz", "yz", "xy"}:
        return None, "GIF view must be XZ, YZ or XY.", 0

    try:
        import mdtraj as md
        from PIL import Image, ImageDraw
        from streamlit_app import molecular_viewer as mv
    except ImportError as exc:
        return None, f"GIF generation needs mdtraj, NumPy and Pillow in the Streamlit environment: {exc}", 0

    try:
        traj = md.load(str(xtc_path), top=str(gro_path))
    except Exception as exc:  # noqa: BLE001
        return None, f"Could not load trajectory for GIF generation: {exc}", 0
    if traj.n_frames == 0:
        return None, "The selected trajectory contains no frames.", 0

    frame_ids = _sample_indices(traj.n_frames, min(120, max(1, int(max_frames))))
    traj = traj[frame_ids]
    atoms = mv._parse_gro_atoms(Path(gro_path))
    if len(atoms) != traj.n_atoms:
        return None, "Trajectory atom count does not match the GRO topology.", 0

    components = mv._short_md_component_resnames(Path(gro_path))
    surface_resn = {str(x).upper() for x in components.get("surface", [])}
    water_resn = {str(x).upper() for x in components.get("water", [])}
    ion_resn = {str(x).upper() for x in components.get("ions", [])}
    linker_resn = {str(x).upper() for x in components.get("linker", [])}

    protein_indices, bb_indices, _by_residue = _protein_indices(atoms)
    protein_set = set(protein_indices)
    categories: list[str] = []
    for idx, atom in enumerate(atoms):
        resn = str(atom.get("resn", "")).strip().upper()
        name = str(atom.get("name", "")).strip().upper()
        if idx in protein_set:
            categories.append("protein_bb" if name.startswith("BB") else "protein_sc")
        elif resn in surface_resn:
            categories.append("surface")
        elif resn in water_resn:
            categories.append("water")
        elif resn in ion_resn:
            categories.append("ions")
        elif resn in linker_resn:
            categories.append("linker")
        else:
            categories.append("other")

    # GIFs deliberately use the connected BB trace as the protein glyph. Side
    # chains made the compact 2-D view look like detached pink particles and do
    # not help interpret protein-to-surface approach.
    enabled = {
        "protein_bb": show_protein,
        "protein_sc": False,
        "surface": show_surface,
        "linker": show_linker,
        "water": show_water,
        "ions": show_ions,
        "other": False,
    }
    visible = [i for i, category in enumerate(categories) if enabled.get(category, False)]
    if not visible:
        return None, "Select at least one component that is present in the trajectory.", 0

    water = [i for i in visible if categories[i] == "water"]
    surface = [i for i in visible if categories[i] == "surface"]
    keep_water = set(_stable_subsample(water, 650))
    keep_surface = set(_stable_subsample(surface, 1400))
    visible = [
        i for i in visible
        if (categories[i] != "water" or i in keep_water)
        and (categories[i] != "surface" or i in keep_surface)
    ]

    boxes = traj.unitcell_vectors
    xyz = _make_protein_whole(traj.xyz, boxes, atoms)
    if show_protein and not show_surface:
        xyz = _rigid_align(xyz, bb_indices or protein_indices)

    center_indices = surface if show_surface and surface else (bb_indices or visible)
    center = xyz[:, center_indices, :].mean(axis=(0, 1))
    coords = xyz - center

    projected_frames: list[dict[int, tuple[float, float, float]]] = []
    all_xy: list[tuple[float, float]] = []
    for frame in coords:
        projected: dict[int, tuple[float, float, float]] = {}
        for atom_index in visible:
            projected_point = _project_point(frame[atom_index], view_plane)
            projected[atom_index] = projected_point
            all_xy.append((projected_point[0], projected_point[1]))
        projected_frames.append(projected)

    min_x = min(x for x, _ in all_xy)
    max_x = max(x for x, _ in all_xy)
    min_y = min(y for _, y in all_xy)
    max_y = max(y for _, y in all_xy)
    span_x = max(max_x - min_x, 0.1)
    span_y = max(max_y - min_y, 0.1)
    margin = 46.0
    scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)

    palette = {
        "protein_bb": "#FF4FA3",
        "surface": "#42C7D5",
        "linker": "#E2B600",
        "water": "#D5DCE1",
        "ions": "#48A868",
    }
    radii = {"protein_bb": 5, "surface": 3, "linker": 5, "water": 2, "ions": 3}

    edges: list[tuple[int, int]] = []
    for left, right in zip(bb_indices, bb_indices[1:]):
        gap = int(atoms[right].get("resid", 0)) - int(atoms[left].get("resid", 0))
        if 0 <= gap <= 2:
            edges.append((left, right))

    def screen(point):
        px, py, _pz = point
        return margin + (px - min_x) * scale, height - (margin + (py - min_y) * scale)

    images = []
    for projected in projected_frames:
        image = Image.new("RGB", (width, height), "#0E0D11")
        draw = ImageDraw.Draw(image)
        for left, right in edges:
            if left in projected and right in projected:
                draw.line([screen(projected[left]), screen(projected[right])], fill="#FF4FA3", width=8)
        for atom_index in sorted(projected, key=lambda idx: projected[idx][2]):
            category = categories[atom_index]
            radius = radii.get(category, 3)
            x, y = screen(projected[atom_index])
            draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius],
                fill=palette.get(category, "#A8B1B8"),
                outline=None if category == "water" else "#5C5660",
                width=1,
            )
        images.append(image)

    if not images:
        return None, "No frames were rendered for the trajectory GIF.", 0
    buffer = io.BytesIO()
    duration_ms = max(40, round(1000 / int(fps)))
    images[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    return buffer.getvalue(), None, len(images)


def install() -> None:
    from streamlit_app import molecular_viewer as mv

    mv.generate_short_md_trajectory_gif = generate_short_md_trajectory_gif
