"""Module for extracting SRT subtitle tracks from MKV files."""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from colorama import Fore
import pysrt


def check_mkvextract():
    """Check if mkvextract is available."""
    return shutil.which('mkvextract') is not None


def check_mkvinfo():
    """Check if mkvinfo is available."""
    return shutil.which('mkvinfo') is not None


def list_srt_tracks(mkv_file):
    """
    List all SRT subtitle tracks from an MKV file.
    Returns a list of tuples (track_id, track_name, language) for SRT subtitle tracks.
    Language can be None if not specified in the MKV file.
    """
    if not check_mkvextract():
        print(Fore.RED + 'mkvextract not found. Please install MKVToolNix.')
        return []

    tracks = []
    
    result = subprocess.run(
        ['mkvinfo', mkv_file],
        capture_output=True,
        text=True,
        check=True
    )
    lines = result.stdout.split('\n')
    
    current_track_id = None
    current_codec = None
    current_name = None
    current_language = None
    in_track = False
    
    for line in lines:
        stripped = line.strip()
        # Detect start of a track - check for "| + Track" (with space after pipe)
        # This matches track headers but not "|+ Tracks" section header
        # Use regex to match "| + Track" exactly (with optional trailing whitespace)
        if re.match(r'^\|\s+\+\s+Track\s*$', line.strip()):
            # Save previous track if it was SRT
            if current_track_id is not None and current_codec and 'S_TEXT/UTF8' in current_codec:
                track_name = current_name or f'Track {current_track_id}'
                tracks.append((current_track_id, track_name, current_language))
            # Reset for new track
            current_track_id = None
            current_codec = None
            current_name = None
            current_language = None
            in_track = True
        elif in_track:
            # Check if we've left the track section (e.g., see a section header at same or higher level)
            # This handles cases where tracks section ends before next track
            if line.startswith('|+') and 'Track' not in line:
                # We've left the tracks section, save current track if valid
                if current_track_id is not None and current_codec and 'S_TEXT/UTF8' in current_codec:
                    track_name = current_name or f'Track {current_track_id}'
                    tracks.append((current_track_id, track_name, current_language))
                # Reset and exit track mode
                current_track_id = None
                current_codec = None
                current_name = None
                current_language = None
                in_track = False
                continue
            # First, try to extract track ID from any line that contains it
            # This handles both "Track ID: X" and "Track number: X (track ID for mkvmerge & mkvextract: Y)"
            # Use regex search directly since it's more reliable than string containment
            match = re.search(r'track ID for mkvmerge & mkvextract:\s*(\d+)', stripped, re.IGNORECASE)
            if match:
                try:
                    current_track_id = int(match.group(1))
                except ValueError:
                    pass
            elif 'Track ID:' in stripped and current_track_id is None:
                # Handle standalone "Track ID: X" format
                parts = stripped.split(':')
                if len(parts) > 1:
                    # Get the last part and extract any number from it
                    id_part = parts[-1].strip()
                    # Remove any trailing parentheses or other characters
                    id_part = id_part.rstrip(')').strip()
                    try:
                        current_track_id = int(id_part)
                    except ValueError:
                        pass
            # Also check for "Track number:" as fallback if Track ID wasn't found
            elif 'Track number:' in stripped and current_track_id is None:
                # Extract track number as fallback
                parts = stripped.split(':')
                if len(parts) > 1:
                    # Try to extract track number (first number after colon)
                    id_part = parts[-1].strip().split()[0]  # Get first number
                    try:
                        current_track_id = int(id_part)
                    except ValueError:
                        pass
            # Extract codec
            elif 'Codec ID:' in stripped:
                parts = stripped.split(':', 1)
                if len(parts) > 1:
                    current_codec = parts[-1].strip()
            # Extract track name
            elif 'Name:' in stripped and 'Track name:' not in stripped:
                parts = stripped.split(':', 1)
                if len(parts) > 1:
                    current_name = parts[-1].strip()
            # Extract language (IETF BCP 47)
            elif 'Language (IETF BCP 47):' in stripped:
                parts = stripped.split(':', 1)
                if len(parts) > 1:
                    current_language = parts[-1].strip()
    
    # Don't forget the last track
    if current_track_id is not None and current_codec and 'S_TEXT/UTF8' in current_codec:
        track_name = current_name or f'Track {current_track_id}'
        tracks.append((current_track_id, track_name, current_language))

    return tracks


def extract_srt_track(mkv_file, track_id, output_file):
    """Extract a specific SRT track from an MKV file."""
    try:
        subprocess.run(
            ['mkvextract', 'tracks', mkv_file, f'{track_id}:{output_file}'],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(Fore.RED + f'Failed to extract track {track_id}: {e}')
        return False


def process_mkv(mkv_file, language_filter=None):
    """
    Process an MKV file by extracting and processing SRT subtitle tracks.
    
    Args:
        mkv_file: Path to the MKV file
        language_filter: Optional language code (IETF BCP 47) to filter tracks by (e.g., 'en')
    """
    if not check_mkvextract():
        print(Fore.RED + 'mkvextract not found. Please install MKVToolNix.')
        return

    if not check_mkvinfo():
        print(Fore.RED + 'mkvinfo not found. Please install MKVToolNix.')
        sys.exit(1)

    mkv_path = Path(mkv_file)
    if not mkv_path.exists():
        print(Fore.RED + f'File not found: {mkv_file}')
        return

    print(Fore.CYAN + f'Processing MKV file: {mkv_file}')

    # List all SRT tracks
    all_tracks = list_srt_tracks(mkv_file)
    if not all_tracks:
        print(Fore.YELLOW + 'No SRT subtitle tracks found in MKV file.')
        return

    # Filter tracks by language if specified
    if language_filter:
        tracks = [
            (track_id, track_name, lang)
            for track_id, track_name, lang in all_tracks
            if lang and lang.lower() == language_filter.lower()
        ]
        if not tracks:
            print(Fore.YELLOW + f'No SRT subtitle tracks found with language code: {language_filter}')
            print(Fore.CYAN + f'Available tracks:')
            for track_id, track_name, lang in all_tracks:
                lang_display = lang if lang else '(no language specified)'
                print(Fore.CYAN + f'  Track {track_id}: {track_name} - {lang_display}')
            return
        print(Fore.CYAN + f'Filtering by language: {language_filter}')
    else:
        tracks = all_tracks

    print(Fore.CYAN + f'Found {len(tracks)} SRT subtitle track(s)')

    # Import here to avoid circular import
    from nocc.nocc import process_subtitle_file

    # Create a temporary directory for extracted tracks
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        base_name = mkv_path.stem

        for track_id, track_name, lang in tracks:
            lang_display = f' ({lang})' if lang else ''
            print(Fore.CYAN + f'Processing track {track_id}: {track_name}{lang_display}')

            # Extract track to temporary file
            temp_srt = tmp_path / f'track_{track_id}.srt'
            if not extract_srt_track(mkv_file, track_id, str(temp_srt)):
                continue

            # Sanitize track name for filename
            safe_track_name = re.sub(r'[^\w\s-]', '', track_name).strip().replace(' ', '_')
            if not safe_track_name:
                safe_track_name = f'track{track_id}'
            
            # Construct final output path (filenames are always the cleaned subtitles)
            output_name = f'{base_name}_track{track_id}_{safe_track_name}.srt'
            output_path = mkv_path.parent / output_name

            # Process the extracted SRT file with explicit output path
            was_modified = process_subtitle_file(str(temp_srt), output_path=str(output_path))
            
            if was_modified:
                print(Fore.GREEN + f'Saved processed track to: {output_path}')
            elif temp_srt.exists():
                # File was already clean, but we still want to save it under the same
                # cleaned filename convention.
                shutil.copy(str(temp_srt), str(output_path))
                print(Fore.GREEN + f'Saved clean track to: {output_path}')
