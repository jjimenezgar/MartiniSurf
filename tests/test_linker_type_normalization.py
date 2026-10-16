from streamlit_app.linker_generator import normalize_linker_martini_types, parse_martini_mapper_report, LinkerBead


def test_question_mark_types_are_cleaned_only_in_atoms(tmp_path):
    itp = tmp_path / "linker.itp"
    itp.write_text(
        "[ moleculetype ]\nLINKER 1\n"
        "[ atoms ]\n"
        "1 TN3a? 1 LNK C1 1 0.0 72.0 ; keep this?\n"
        "2 P1 1 LNK C2 2 1.0 72.0\n"
        "3 SC3?? 1 LNK C3 3 0.0 72.0\n"
        "[ bonds ]\n1 2 1 0.47 1000 ; unchanged?\n"
    )
    assert normalize_linker_martini_types(itp) == 2
    result = itp.read_text()
    assert "TN3a?" not in result
    assert "SC3??" not in result
    assert "1 TN3a 1 LNK C1 1 0.0 72.0" in result
    assert "3 SC3 1 LNK C3 3 0.0 72.0" in result
    assert "keep this?" in result
    assert "unchanged?" in result
    assert normalize_linker_martini_types(itp) == 0


def test_mapper_report_type_label_strips_uncertainty_marker(tmp_path):
    report = tmp_path / "report.txt"
    report.write_text(
        "All beads\n"
        "index type atoms a b c d e f\n"
        "0 TN3a? 0,1 x x x x x x\n"
        "Bead connections\n"
    )
    beads = [LinkerBead(1, "C1", 1, "LNK", 0, 0, 0)]
    rows = parse_martini_mapper_report(report, beads)
    assert len(rows) == 1
    assert rows[0].martini_type == "TN3a"
