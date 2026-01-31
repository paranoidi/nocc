import copy
import re
import sys

import colorama
from colorama import Fore
import pysrt


REMOVE_RE = [
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
    # TODO: "SOME". Says
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

REPLACE_RE = [
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

def nocc(filename):
    if 'nocc' in filename:
        print(Fore.RED + 'Ignored already processed file: {}'.format(filename))
        return

    subs = pysrt.open(filename)
    delete = []
    modified = False
    for index, line in enumerate(subs):
        text = line.text
        # list of identifiers used to clean
        used = []
        for what, regex in REMOVE_RE:
            orig = text

            # song
            if '\u266a' in text:
                text = ''
                used.append('song')
                break

            # multiline
            text = regex.sub('', text)

            # try each line separately
            sublines = []
            for subline in text.split('\n'):
                subline = regex.sub('', subline)
                sublines.append(subline)
            text = '\n'.join(sublines)

            # try as single line
            # if it produces empty line we have multiline crap, eg
            # ( FOO BAR
            # LOREM IPSUM )
            # TODO: pretty sure this makes mistakes ...
            if not regex.sub('', text.replace('\n', '')).strip():
                text = ''
                used.append('multiline with {}'.format(what))
                continue

            if orig != text:
                used.append(what)
            # strip between cases
            text = text.strip()

        for what, src, dst in REPLACE_RE:
            orig = text
            text = re.sub(src, dst, text)
            if orig != text:
                used.append(what)
            # strip between cases
            text = text.strip()

        # TODO: optional?
        joined, text = join_short(text)

        if joined:
            used.append('joined lines')
        if used:
            print(Fore.CYAN + 'Cleaned with: {}{}'.format(Fore.RESET, ', '.join(used)))
        if not text:
            print(Fore.RED + '{}'.format(line.text))
            print()
            delete.append(index)
            modified = True
        elif text != line.text:
            print(Fore.YELLOW + '{}'.format(line.text))
            print(Fore.GREEN + '{}'.format(text))
            print()
            modified = True

        line.text = text

    # remove marked
    for index in delete[::-1]:
        del subs[index]

    if modified:
        subs.save(filename.replace('.srt', '_nocc.srt'), encoding='utf-8')
    else:
        print(Fore.GREEN + 'Already clean file: {}'.format(filename))


def join_short(text):
    """
    In case of short multiline texts, combine them to single line
    """
    lines = text.split('\n')
    if len(lines) > 1 and not '-' in text:
        # find max length
        max_len = 0
        for i, line in enumerate(lines):
            if len(line) > max_len:
                max_len = len(line)
            if line.endswith('?') and i == 0:
                # question, asnwer discussion
                # should stay in separate lines
                return False, text
        # join if all short, and remain short ...
        joined = ' '.join(lines)
        if -1 < max_len < 30 and len(joined) < 40:
            return True, joined
    return False, text


def main():
    colorama.init(autoreset=True)

    if len(sys.argv) == 1:
        print('Use: nocc [filename.srt]')
        sys.exit(0)
    for fn in sys.argv[1:]:
        nocc(fn)

if __name__ == '__main__':
    main()
