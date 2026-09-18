"""Conservative protein-only preparation before martinize2.

Missing side-chain atoms are modeled, never entire missing residues.
Terminal patches remain the responsibility of martinize2.
Original inputs and a JSON audit trail are retained by the loader.
"""
import io
import json
import math
from collections import defaultdict
from pathlib import Path

STANDARD = set('ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split())
NUCLEIC = set('A C G U I DA DC DG DT DI DU'.split())


def validate_pdb_coordinates(path: Path) -> None:
    """Reject empty, malformed or non-finite atomistic/CG coordinate files."""
    count = 0
    for line in Path(path).read_text().splitlines():
        if line[:6].strip() not in {'ATOM', 'HETATM'}:
            continue
        count += 1
        try:
            xyz = [float(line[a:b]) for a, b in ((30, 38), (38, 46), (46, 54))]
        except ValueError as exc:
            raise ValueError(f'Malformed coordinates in {path}: {line[:27]}') from exc
        if not all(math.isfinite(x) for x in xyz):
            raise ValueError(f'Non-finite coordinates in {path}: {line[:27]}')
    if not count:
        raise ValueError(f'No atoms found in {path}.')


def _label(key):
    segment, chain, resid, icode = key
    return f'{chain or "_"}:{resid.strip()}{icode.strip()} (segment {segment})'


def _select_protein(infile, report, chain=None):
    groups = defaultdict(list)
    segment = 0
    models = 0
    for line in Path(infile).read_text().splitlines():
        record = line[:6].strip()
        if record == 'MODEL':
            models += 1
            if models > 1:
                break
        if record == 'ENDMDL':
            break
        if record == 'TER':
            segment += 1
        if record not in {'ATOM', 'HETATM'}:
            continue
        if chain is not None and line[21:22] != chain:
            continue
        if len(line) < 54:
            raise ValueError(f'Truncated PDB atom record: {line}')
        xyz = [float(line[a:b]) for a, b in ((30, 38), (38, 46), (46, 54))]
        if not all(math.isfinite(x) for x in xyz):
            raise ValueError(f'Non-finite input coordinates: {line[:27]}')
        key = (segment, line[21].strip(), line[22:26], line[26])
        groups[key].append(line.ljust(80))
    output = []
    previous_segment = None
    for key, lines in groups.items():
        names = {l[17:20].strip() for l in lines}
        atom_names = {l[12:16].strip() for l in lines}
        if not names <= STANDARD | {'MSE'}:
            if names <= NUCLEIC or (all(l.startswith('HETATM') for l in lines) and not {'N', 'CA', 'C'} <= atom_names):
                report['removed_residues'].append({'residue': _label(key), 'names': sorted(names)})
                continue
            raise ValueError(f'Unsupported protein residue {sorted(names)} at {_label(key)}; provide a reviewed standard-residue model.')
        # Select a whole residue conformer; shared blank-altloc atoms are retained.
        conformers = defaultdict(list)
        for line in lines:
            if line[16] != ' ':
                try:
                    occupancy = float(line[54:60].strip() or '0')
                except ValueError as exc:
                    raise ValueError(f'Invalid occupancy at {_label(key)}') from exc
                if not math.isfinite(occupancy):
                    raise ValueError(f'Invalid occupancy at {_label(key)}')
                conformers[line[16]].append(occupancy)
        chosen = min(conformers, key=lambda c: (-sum(conformers[c])/len(conformers[c]), c != 'A', c)) if conformers else ' '
        selected = [l for l in lines if l[16] in {' ', chosen}]
        if conformers:
            report['alternate_conformations'].append({'residue': _label(key), 'selected': chosen})
        selected_names = {l[17:20].strip() for l in selected}
        if len(selected_names) != 1:
            raise ValueError(f'Ambiguous residue identity at {_label(key)}')
        resname = next(iter(selected_names))
        if resname == 'MSE':
            report['replacements'].append({'residue': _label(key), 'from': 'MSE', 'to': 'MET'})
        seen = set()
        prepared = []
        for line in selected:
            atom = line[12:16].strip()
            element = line[76:78].strip().upper()
            if element in {'H', 'D'} or (not element and atom.lstrip('0123456789').startswith(('H', 'D'))):
                continue
            if atom in seen:
                raise ValueError(f'Duplicate atom {atom} at {_label(key)}')
            seen.add(atom)
            line = 'ATOM  ' + line[6:16] + ' ' + line[17:]
            if resname == 'MSE':
                line = line[:17] + 'MET' + line[20:]
                if atom == 'SE':
                    line = line[:12] + ' SD ' + line[16:76] + ' S' + line[78:]
            prepared.append(line + '\n')
        if not {'N', 'CA', 'C', 'O'} <= seen:
            raise ValueError(f'Incomplete backbone at {_label(key)}: missing {sorted({"N", "CA", "C", "O"} - seen)}. Review/model this region before martinization.')
        if previous_segment is not None and previous_segment != key[:2]:
            output.append('TER\n')
        output.extend(prepared)
        previous_segment = key[:2]
    if not output:
        raise ValueError('No supported protein residues found in the selected input.')
    report['model'] = 'first'
    return ''.join(output) + 'END\n'


def _check_backbone(fixer):
    """Avoid modeling across unresolved peptide breaks (including numbering gaps)."""
    from openmm import unit
    xyz = fixer.positions.value_in_unit(unit.angstrom)
    for chain in fixer.topology.chains():
        previous = None
        for residue in chain.residues():
            atoms = {a.name: a.index for a in residue.atoms()}
            if previous is not None:
                prev, prev_atoms = previous
                distance = math.dist(xyz[prev_atoms['C']], xyz[atoms['N']])
                # Numbering gaps can represent unresolved loops even if the ends are close.
                gap = int(residue.id) - int(prev.id) > 1
                if distance > 2.0 or distance < 0.9 or gap:
                    raise ValueError(f'Unresolved peptide break in chain {chain.id or "_"}: {prev.id}{prev.insertionCode} -> {residue.id}{residue.insertionCode} (C-N {distance:.2f} A). Review missing residues/chain boundaries before martinization.')
            previous = (residue, atoms)


def prepare_protein_pdb(infile: Path, outfile: Path, report_path: Path, chain=None) -> Path:
    report = {'status': 'preparing', 'input': str(infile), 'protein_only': True,
              'removed_residues': [], 'alternate_conformations': [],
              'replacements': [], 'added_atoms': [], 'missing_residues_added': False,
              'repair_seed': 42, 'terminal_atoms_deferred': []}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from pdbfixer import PDBFixer
        from openmm import Platform
        from openmm.app import PDBFile
        selected = _select_protein(infile, report, chain)
        # CPU avoids requiring a GPU on servers and Colab runtimes.
        fixer = PDBFixer(pdbfile=io.StringIO(selected), platform=Platform.getPlatformByName('CPU'))
        identities = [(r.chain.id, r.id, r.insertionCode, r.name) for r in fixer.topology.residues()]
        _check_backbone(fixer)
        fixer.missingResidues = {}
        fixer.findMissingAtoms()
        for residue, atoms in fixer.missingAtoms.items():
            report['added_atoms'].append({'chain': residue.chain.id, 'resid': residue.id,
                                          'icode': residue.insertionCode, 'resname': residue.name,
                                          'atoms': [a.name for a in atoms]})
        for residue, atoms in fixer.missingTerminals.items():
            report['terminal_atoms_deferred'].append({'chain': residue.chain.id, 'resid': residue.id,
                                          'icode': residue.insertionCode, 'resname': residue.name,
                                          'atoms': list(atoms)})
        # martinize2 applies terminal patches itself. In vermouth 0.15, supplying
        # newly added OXT alongside its automatic +C-ter patch can fail
        # canonicalization. Do not model terminal atoms.
        fixer.missingTerminals = {}
        fixer.addMissingAtoms(seed=42)
        fixer.findMissingAtoms()
        if any(fixer.missingAtoms.values()):
            raise ValueError('Protein repair left missing heavy atoms.')
        if identities != [(r.chain.id, r.id, r.insertionCode, r.name) for r in fixer.topology.residues()]:
            raise ValueError('Protein repair changed residue identities or numbering.')
        with outfile.open('w') as handle:
            PDBFile.writeFile(fixer.topology, fixer.positions, handle, keepIds=True)
        validate_pdb_coordinates(outfile)
        report['status'] = 'prepared'
        print(f'Protein prepared; repair/removal report: {report_path}')
        return outfile
    except ImportError as exc:
        report['status'] = 'failed'
        report['error'] = 'Protein preparation requires pdbfixer and OpenMM. Reinstall MartiniSurf dependencies.'
        raise RuntimeError(report['error']) from exc
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = str(exc)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + '\n')


def validate_protein_backbone(path: Path) -> None:
    from openmm.app import PDBFile
    _check_backbone(PDBFile(str(path)))
