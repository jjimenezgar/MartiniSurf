"""Regression tests for safe protein-only input and the 8AV5 failure."""
import json
import math
from pathlib import Path
import shutil
import subprocess

import pytest

from martinisurf.utils.pdb_generation import load_clean_pdb
from martinisurf.utils.protein_preparation import (
    _select_protein, prepare_protein_pdb, validate_pdb_coordinates,
)

FIXTURE = Path(__file__).parent / 'data' / '8AV5.pdb'


def report():
    return {'removed_residues': [], 'alternate_conformations': [], 'replacements': []}


def atom(serial, name, res='ALA', resid=1, alt=' ', occupancy=1, record='ATOM', x=0, chain='A'):
    return (f'{record:<6}{serial:5d} {name:^4}{alt}{res:>3} {chain}{resid:4d}    '
            f'{x:8.3f}{0:8.3f}{0:8.3f}{occupancy:6.2f}{20:6.2f}          {name[0]:>2}\n')


def backbone(res='ALA', record='ATOM', resid=1):
    return ''.join(atom(i, name, res=res, record=record, resid=resid)
                   for i, name in enumerate(['N', 'CA', 'C', 'O'], 1))


def test_selects_whole_highest_occupancy_conformer_and_removes_heterogens(tmp_path):
    p = tmp_path / 'input.pdb'
    p.write_text(backbone() + atom(5, 'CB', alt='A', occupancy=.3, x=1)
                 + atom(6, 'CB', alt='B', occupancy=.7, x=2)
                 + atom(7, 'O', res='HOH', resid=2, record='HETATM')
                 + atom(8, 'P', res='DA', resid=3))
    audit = report()
    selected = _select_protein(p, audit)
    cb = next(l for l in selected.splitlines() if l[12:16].strip() == 'CB')
    assert float(cb[30:38]) == 2
    assert cb[16] == ' '
    assert 'HOH' not in selected and ' DA ' not in selected
    assert len(audit['removed_residues']) == 2
    assert audit['alternate_conformations'][0]['selected'] == 'B'


def test_first_model_only_and_ties_prefer_a(tmp_path):
    p = tmp_path / 'input.pdb'
    p.write_text('MODEL        1\n' + backbone() + atom(5, 'CB', alt='B', occupancy=.5, x=2)
                 + atom(6, 'CB', alt='A', occupancy=.5, x=1) + 'ENDMDL\n'
                 + 'MODEL        2\n' + backbone(res='GLY') + 'ENDMDL\n')
    audit = report()
    selected = _select_protein(p, audit)
    assert 'GLY' not in selected
    assert audit['alternate_conformations'][0]['selected'] == 'A'


def test_mse_hetatm_is_retained_as_met(tmp_path):
    p = tmp_path / 'mse.pdb'
    p.write_text(backbone(res='MSE', record='HETATM')
                 + atom(5, 'SE', res='MSE', record='HETATM'))
    audit = report()
    selected = _select_protein(p, audit)
    assert 'MSE' not in selected and ' SD ' in selected and 'MET' in selected
    assert audit['replacements'][0]['to'] == 'MET'


def test_unknown_modified_protein_is_not_silently_discarded(tmp_path):
    p = tmp_path / 'modified.pdb'
    p.write_text(backbone(res='SEP', record='HETATM'))
    with pytest.raises(ValueError, match='Unsupported protein residue'):
        _select_protein(p, report())


@pytest.mark.parametrize('content', ['', atom(1, 'CA', x=math.nan), atom(1, 'CA', x=math.inf)])
def test_rejects_empty_or_nonfinite_output(tmp_path, content):
    p = tmp_path / 'bad.pdb'
    p.write_text(content)
    with pytest.raises(ValueError):
        validate_pdb_coordinates(p)


def test_incomplete_backbone_fails_with_audit(tmp_path):
    p = tmp_path / 'backbone.pdb'
    p.write_text(atom(1, 'CA'))
    audit = tmp_path / 'report.json'
    with pytest.raises(ValueError, match='Incomplete backbone'):
        prepare_protein_pdb(p, tmp_path / 'fixed.pdb', audit)
    assert json.loads(audit.read_text())['status'] == 'failed'


def test_internal_chain_break_is_not_filled(tmp_path):
    lines = FIXTURE.read_text().splitlines(keepends=True)
    p = tmp_path / 'gap.pdb'
    p.write_text(''.join(l for l in lines if not (l.startswith('ATOM') and int(l[22:26]) == 20)))
    with pytest.raises(ValueError, match='Unresolved peptide break'):
        prepare_protein_pdb(p, tmp_path / 'fixed.pdb', tmp_path / 'report.json')


@pytest.fixture(scope='module')
def repaired_8av5(tmp_path_factory):
    directory = tmp_path_factory.mktemp('8av5')
    path = load_clean_pdb(str(FIXTURE), directory, protein_only=True)
    return directory, path


def test_8av5_repairs_atoms_preserves_ids_and_saves_original(repaired_8av5):
    directory, path = repaired_8av5
    audit = json.loads((directory / '2_system/protein_preparation.json').read_text())
    assert audit['status'] == 'prepared'
    assert (directory / '2_system/original_input.pdb').read_bytes() == FIXTURE.read_bytes()
    atoms = [l for l in path.read_text().splitlines() if l.startswith('ATOM')]
    assert len({l[21:27] for l in atoms}) == 324
    assert all(l[16] == ' ' for l in atoms)
    assert not any(l.startswith('HETATM') for l in path.read_text().splitlines())
    for resid, expected in [(20, {'CG', 'CD', 'OE1', 'OE2'}), (261, {'CE', 'NZ'})]:
        assert expected <= {l[12:16].strip() for l in atoms if int(l[22:26]) == resid}
    validate_pdb_coordinates(path)


def test_8av5_martinize_has_no_warnings_or_nan(repaired_8av5):
    executable = shutil.which('martinize2')
    if not executable:
        pytest.skip('martinize2 executable unavailable')
    directory, path = repaired_8av5
    completed = subprocess.run(
        [executable, '-f', str(path), '-x', 'cg.pdb', '-o', 'topol.top',
         '-ff', 'martini3001', '-name', 'protein', '-maxwarn', '0',
         '-p', 'backbone', '-pf', '1000', '-dssp'],
        cwd=directory, capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert 'WARNING' not in completed.stderr
    validate_pdb_coordinates(directory / 'cg.pdb')
    assert (directory / 'topol.top').exists()
