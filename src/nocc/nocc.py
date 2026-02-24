import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Protocol, Tuple

import colorama
from colorama import Fore
import pysrt

from nocc.mkvextract import process_mkv


# Configuration constants
class Config:
    """Configuration constants for subtitle cleaning."""

    # Thresholds for join_short function
    MAX_LINE_LENGTH: int = 30
    MAX_JOINED_LENGTH: int = 40
    SONG_CHARACTER: str = '\u266a'


# Type definitions
RemoveRule = Tuple[str, re.Pattern[str]]
ReplaceRule = Tuple[str, str, str]
CleaningResult = Tuple[str, List[str]]  # (cleaned_text, list_of_applied_rules)


class OutputHandler(Protocol):
    """Protocol for output handlers to abstract console output."""

    def info(self, message: str) -> None:
        """Print informational message."""
        ...

    def warning(self, message: str) -> None:
        """Print warning message."""
        ...

    def error(self, message: str) -> None:
        """Print error message."""
        ...

    def success(self, message: str) -> None:
        """Print success message."""
        ...

    def show_cleaning(self, original: str, cleaned: str, rules: List[str]) -> None:
        """Show cleaning operation details."""
        ...

    def show_deleted(self, text: str) -> None:
        """Show deleted subtitle text."""
        ...


class ConsoleOutputHandler:
    """Default console output handler using colorama."""

    def info(self, message: str) -> None:
        print(Fore.CYAN + message)

    def warning(self, message: str) -> None:
        print(Fore.YELLOW + message)

    def error(self, message: str) -> None:
        print(Fore.RED + message)

    def success(self, message: str) -> None:
        print(Fore.GREEN + message)

    def show_cleaning(self, original: str, cleaned: str, rules: List[str]) -> None:
        if rules:
            print(Fore.CYAN + 'Cleaned with: {}{}'.format(Fore.RESET, ', '.join(rules)))
        print(Fore.YELLOW + original)
        print(Fore.GREEN + cleaned)
        print()

    def show_deleted(self, text: str) -> None:
        print(Fore.RED + text)
        print()


# Cleaning rules
REMOVE_RE: List[RemoveRule] = [
    # HTML font, we want to leave <i> etc alone
    ('font styling', re.compile(r'</?font.*?>')),
    # SOMEONE:
    # - says
    # SOME ONE:
    # - says
    # SOME-ONE:
    # - says
    # SOME. ONE:
    # - says
    ('multiline person', re.compile(r'^[0-9A-Z\s\-\#\.]+:\n-\s')),
    # SOMEONE: says
    # SOMEONE : says
    # SOME ONE: says
    # SOME-ONE: says
    # SOME. ONE: says
    ('person', re.compile(r'^[0-9A-Z\s\-\#\.]*?\s?:\s')),
    # middle. SOMEONE: aasf
    ('person middle', re.compile(r'[0-9A-Z]{3,10}\s?:\s')),
    # (LOUDLY)
    ('effect', re.compile(r'\(.*?\)')),
    # [LOUDLY]
    ('effect', re.compile(r'\[.*?\]')),
    # -
    ('empty dash', re.compile(r'^\s?-\s?$')),
    # double spaces
    ('double spaces', re.compile(r'\s\s')),
]

REPLACE_RE: List[ReplaceRule] = [
    # -foobar
    ('dash missing space', r'^-(\w)', r'- \1'),
    # aaa.foobar
    ('dot missing space', r'\.(\w)', r'. \1'),
    # aaa.foobar
    ('comma missing space', r',(\w)', r', \1'),
    # aaa?foobar
    ('? missing space', r'\?(\w)', r'? \1'),
    # aaa!foobar
    ('! missing space', r'\!(\w)', r'! \1'),
]

class SubtitleCleaner:
    """Handles cleaning of subtitle text by applying removal and replacement rules."""

    def __init__(
        self,
        remove_rules: Optional[List[RemoveRule]] = None,
        replace_rules: Optional[List[ReplaceRule]] = None,
        config: Optional[Config] = None,
    ) -> None:
        """
        Initialize the subtitle cleaner.

        Args:
            remove_rules: List of (name, regex_pattern) tuples for removal rules
            replace_rules: List of (name, source_pattern, replacement) tuples for replacement rules
            config: Configuration object with thresholds and constants
        """
        self.remove_rules = remove_rules if remove_rules is not None else REMOVE_RE
        self.replace_rules = replace_rules if replace_rules is not None else REPLACE_RE
        self.config = config if config is not None else Config()

    def clean_text(self, text: str) -> CleaningResult:
        """
        Clean a single subtitle text by applying all cleaning rules.

        Args:
            text: The original subtitle text to clean

        Returns:
            Tuple of (cleaned_text, list_of_applied_rule_names)
        """
        if not text:
            return '', []

        original_text = text
        applied_rules: List[str] = []

        # Check for song character first (special case)
        if self.config.SONG_CHARACTER in text:
            return '', ['song']

        # Apply removal rules
        for rule_name, regex_pattern in self.remove_rules:
            original_before_rule = text

            # Apply regex to whole text first (handles patterns that span lines)
            text = regex_pattern.sub('', text)

            # Apply regex to each line separately for line-by-line patterns
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                cleaned_line = regex_pattern.sub('', line)
                cleaned_lines.append(cleaned_line)
            text = '\n'.join(cleaned_lines)

            # Check if the entire text (when joined) would be empty after this rule
            # This handles multiline patterns that span across lines
            # e.g., "( FOO BAR\nLOREM IPSUM )" would be completely removed
            joined_text = text.replace('\n', ' ')
            if not regex_pattern.sub('', joined_text).strip():
                # The entire text is matched by this pattern, remove it
                return '', [f'multiline with {rule_name}']

            # Strip whitespace between rule applications
            text = text.strip()

            if original_before_rule != text:
                applied_rules.append(rule_name)

        # Apply replacement rules
        for rule_name, source_pattern, replacement in self.replace_rules:
            original_before_rule = text
            text = re.sub(source_pattern, replacement, text).strip()
            if original_before_rule != text:
                applied_rules.append(rule_name)

        # Join short multiline texts
        joined, text = self._join_short(text)
        if joined:
            applied_rules.append('joined lines')

        return text, applied_rules

    def _join_short(self, text: str) -> Tuple[bool, str]:
        """
        In case of short multiline texts, combine them to single line.

        Args:
            text: The text to potentially join

        Returns:
            Tuple of (was_joined, result_text)
        """
        lines = text.split('\n')
        if len(lines) <= 1 or '-' in text:
            return False, text

        # Find max line length
        max_len = max((len(line) for line in lines), default=0)

        # Don't join if first line ends with '?' (question-answer format)
        if lines[0].endswith('?'):
            return False, text

        # Join if all lines are short and the joined result is also short
        joined = ' '.join(lines)
        if 0 < max_len < self.config.MAX_LINE_LENGTH and len(joined) < self.config.MAX_JOINED_LENGTH:
            return True, joined

        return False, text


def process_subtitle_file(
    filename: str,
    output_handler: Optional[OutputHandler] = None,
    output_path: Optional[str] = None,
) -> bool:
    """
    Process a subtitle file, cleaning it and saving the result.

    Args:
        filename: Path to the SRT file to process
        output_handler: Optional output handler for messages (defaults to ConsoleOutputHandler)
        output_path: Optional path for the output file. If None, the original file is
                     renamed to have a leading underscore (e.g., subtitle.srt ->
                     _subtitle.srt) and the cleaned subtitles are written back to the
                     original filename. If provided, uses this exact path without
                     renaming the source file.

    Returns:
        True if the file was modified, False otherwise

    Raises:
        FileNotFoundError: If the file doesn't exist
        pysrt.Error: If the file cannot be parsed
    """
    handler = output_handler or ConsoleOutputHandler()
    cleaner = SubtitleCleaner()

    try:
        subs = pysrt.open(filename)
    except Exception as e:
        handler.error(f'Failed to open subtitle file {filename}: {e}')
        raise

    delete_indices: List[int] = []
    modified = False

    for index, subtitle in enumerate(subs):
        original_text = subtitle.text
        cleaned_text, applied_rules = cleaner.clean_text(original_text)

        if not cleaned_text:
            handler.show_deleted(original_text)
            delete_indices.append(index)
            modified = True
        elif cleaned_text != original_text:
            handler.show_cleaning(original_text, cleaned_text, applied_rules)
            modified = True

        subtitle.text = cleaned_text

    # Remove marked subtitles (in reverse order to maintain indices)
    for index in reversed(delete_indices):
        del subs[index]

    if output_path is not None:
        if modified:
            output_filename = output_path
            try:
                subs.save(output_filename, encoding='utf-8')
            except Exception as e:
                handler.error(f'Failed to save processed file {output_filename}: {e}')
                raise
        else:
            handler.success(f'Already clean file: {filename}')
    else:
        original_path = Path(filename)
        backup_path = original_path.with_name(f'_{original_path.name}')
        try:
            original_path.rename(backup_path)
        except Exception as e:
            handler.error(f'Failed to backup original file {filename} to {backup_path}: {e}')
            raise

        try:
            subs.save(str(original_path), encoding='utf-8')
        except Exception as e:
            handler.error(f'Failed to save processed file {original_path}: {e}')
            raise

        if modified:
            handler.success(f'Cleaned file: {filename}')
        else:
            handler.success(f'Already clean file: {filename}')

    return modified


def main() -> None:
    """
    Main entry point for the nocc command-line tool.

    Processes subtitle files (.srt) or extracts and processes subtitles from MKV files (.mkv).
    """
    colorama.init(autoreset=True)

    parser = argparse.ArgumentParser(
        description='Remove closed captioning from subtitles',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--lang',
        type=str,
        help='Language code (IETF BCP 47) to filter MKV subtitle tracks (e.g., --lang en)'
    )
    parser.add_argument(
        'files',
        nargs='+',
        help='Subtitle files (.srt) or MKV files (.mkv) to process'
    )

    args = parser.parse_args()

    handler = ConsoleOutputHandler()

    for fn in args.files:
        fn_path = Path(fn)
        if fn_path.suffix.lower() == '.mkv':
            process_mkv(fn, language_filter=args.lang)
        else:
            if args.lang:
                handler.warning(f'Warning: --lang argument is only used for MKV files. Ignoring for {fn}')
            try:
                process_subtitle_file(fn, handler)
            except Exception as e:
                handler.error(f'Error processing {fn}: {e}')
                sys.exit(1)


if __name__ == '__main__':
    main()
