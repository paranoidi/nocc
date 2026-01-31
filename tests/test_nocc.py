import shutil
import sys
import tempfile
from io import StringIO
from pathlib import Path

import pysrt

from nocc.nocc import nocc


def get_test_file_path(filename: str) -> Path:
    """Get the path to a test file."""
    return Path(__file__).parent / filename


def get_expected_output_path(filename: str) -> Path:
    """Get the path to the expected output file."""
    return Path(__file__).parent / filename.replace('.srt', '_nocc.srt')


def read_srt_file(filepath: Path) -> str:
    """Read and normalize SRT file content for comparison."""
    if not filepath.exists() or filepath.stat().st_size == 0:
        return ""
    subs = pysrt.open(str(filepath))
    lines = []
    for sub in subs:
        lines.append(str(sub.index))
        lines.append(f"{sub.start} --> {sub.end}")
        lines.append(sub.text)
        lines.append("")
    return "\n".join(lines).strip()


def run_nocc_test(test_filename: str):
    """Helper function to run nocc test on a file."""
    test_file = get_test_file_path(test_filename)
    expected_file = get_expected_output_path(test_filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_copy = Path(tmpdir) / test_filename
        shutil.copy(test_file, test_copy)

        # Suppress print output during test
        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            nocc(str(test_copy))
        finally:
            sys.stdout = old_stdout

        output_file = test_copy.parent / test_filename.replace('.srt', '_nocc.srt')
        expected_content = read_srt_file(expected_file)
        actual_content = read_srt_file(output_file)

        assert actual_content == expected_content, f"Output mismatch for {test_filename}"


def test_dash_missing_space():
    """Test dash-missing-space.srt file."""
    run_nocc_test("dash-missing-space.srt")


def test_dotted_name():
    """Test dotted-name.srt file."""
    run_nocc_test("dotted-name.srt")


def test_font_multiline_persons():
    """Test font-multiline-persons.srt file."""
    run_nocc_test("font-multiline-persons.srt")


def test_font_multine_split_effect():
    """Test font-multine-split-effect.srt file."""
    run_nocc_test("font-multine-split-effect.srt")


def test_person_on_firstline_dash_next():
    """Test person-on-firstline-dash-next.srt file."""
    run_nocc_test("person-on-firstline-dash-next.srt")


def test_person_on_firstline():
    """Test person-on-firstline.srt file."""
    run_nocc_test("person-on-firstline.srt")


def test_short_multiline():
    """Test short-multiline.srt file."""
    run_nocc_test("short-multiline.srt")


def test_song():
    """Test song.srt file."""
    run_nocc_test("song.srt")


def test_twodashes():
    """Test twodashes.srt file (should remain unchanged)."""
    test_file = get_test_file_path("twodashes.srt")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_copy = Path(tmpdir) / "twodashes.srt"
        shutil.copy(test_file, test_copy)

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            nocc(str(test_copy))
        finally:
            sys.stdout = old_stdout

        # twodashes.srt should not generate output file (already clean)
        output_file = test_copy.parent / "twodashes_nocc.srt"
        assert not output_file.exists(), "twodashes.srt should not generate output file (already clean)"
