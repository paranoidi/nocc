# nocc

Remove closed captioning artifacts from subtitle files.

## What it does

Cleans SRT subtitle files by removing:
- Speaker names (e.g., "SOMEONE: says")
- Sound effects in parentheses/brackets (e.g., "(LOUDLY)", "[LOUDLY]")
- Font styling tags
- Songs (♪ character)
- Empty dashes
- Fixes missing spaces after punctuation

## Installation

Currently this not available through PyPI. Use git clone and then:

Install dependencies:

```bash
uv sync
```

Make the command available:

```bash
uv tool install .
```

## Usage

Process SRT files:
```bash
nocc subtitle.srt
```

Process multiple files:
```bash
nocc file1.srt file2.srt
```

Extract and process subtitles from MKV files:
```bash
nocc movie.mkv
```

Filter by language when processing MKV files:
```bash
nocc --lang en movie.mkv
```

Output files are saved with `_nocc` suffix (e.g., `subtitle_nocc.srt`).
