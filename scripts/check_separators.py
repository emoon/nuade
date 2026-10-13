#!/usr/bin/env python3
"""Check that every function definition has a 119-slash separator line before it (c_code_style_guide.md
"Function Separators").

    scripts/check_separators.py <file>...

A function definition is a top-level declaration that starts at column 0, ends in '{', has a '(' and has no '=' outside
brackets (so prototypes, struct/enum/typedef blocks and initialised tables are not functions).
Preprocessor lines (with their '\\' continuations) are ignored, so macros are never flagged. 'extern "C" {' and
'namespace x {' blocks are transparent. From the definition's first line, the check walks back over blank lines,
comment-only lines and conditional directives (#if/#ifdef/#ifndef/#elif/#else/#endif) and expects the separator.

A line of 40 or more slashes only that is not exactly 119 long is reported too.

Prints 'file:line: text' per missing or wrong separator, then 'missing: N'. Exit 1 if any are missing.
"""
import re
import sys

SEP = '/' * 119
COND_DIRECTIVE = re.compile(r'^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b')
TRANSPARENT = re.compile(r'^(extern\s*""|namespace(\s+\w+)?)$')


def scan(text):
    """Return (lines, has_code, decls): has_code[i] is True for a line with code or a preprocessor directive, decls a
    (first_line, decl_text) pair for every top-level declaration that ends in '{'.

    decl_text has comments removed, string/char literals collapsed to '""', and whitespace collapsed. first_line is the
    0-based line of the declaration's first code character, or None if that character is not at column 0.
    """
    lines = text.split('\n')
    has_code = [False] * len(lines)
    decls = []
    braces = []  # one entry per open '{': True if transparent (extern "C" / namespace)
    stmt = []
    stmt_line = None
    in_block_comment = False
    in_directive = False

    for ln, line in enumerate(lines):
        if in_directive or (not in_block_comment and line.lstrip().startswith('#')):
            has_code[ln] = True
            in_directive = line.rstrip().endswith('\\')
            continue
        i = 0
        n = len(line)
        while i < n:
            c = line[i]
            if in_block_comment:
                end = line.find('*/', i)
                if end < 0:
                    break
                in_block_comment = False
                i = end + 2
                continue
            if line.startswith('//', i):
                break
            if line.startswith('/*', i):
                in_block_comment = True
                i += 2
                continue
            if c.isspace():
                if stmt:
                    stmt.append(' ')
                i += 1
                continue
            has_code[ln] = True
            depth = sum(1 for t in braces if not t)
            start = i
            if c in '"\'':
                j = i + 1
                while j < n and line[j] != c:
                    j += 2 if line[j] == '\\' else 1
                i = j + 1
                c = '""'
            else:
                i += 1
            if depth > 0:
                if c == '{':
                    braces.append(False)
                elif c == '}':
                    braces.pop()
                continue
            if not stmt:
                stmt_line = ln if start == 0 else None
            if c == '{':
                decl = re.sub(r'\s+', ' ', ''.join(stmt)).strip()
                transparent = bool(TRANSPARENT.match(decl))
                braces.append(transparent)
                if not transparent:
                    decls.append((stmt_line, decl))
                stmt = []
            elif c in ';}':
                if c == '}' and braces:
                    braces.pop()
                stmt = []
            else:
                stmt.append(c)
    return lines, has_code, decls


def is_function(decl):
    """A '(' and no '=' outside brackets: 'int f(int x = 0) {' is a function, 'int t[(N)] = {' is not."""
    if '(' not in decl:
        return False
    outer = re.sub(r'\boperator\s*\S+?\(', '(', decl)
    while True:
        stripped = re.sub(r'\([^()]*\)|\[[^\[\]]*\]', '', outer)
        if stripped == outer:
            break
        outer = stripped
    return '=' not in outer


def check_file(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        lines, has_code, decls = scan(f.read())
    missing = []
    for first, decl in decls:
        if first is None or not is_function(decl):
            continue
        j = first - 1
        while j >= 0 and lines[j].rstrip() != SEP and (not has_code[j] or COND_DIRECTIVE.match(lines[j])):
            j -= 1
        if j < 0 or lines[j].rstrip() != SEP:
            missing.append((first + 1, lines[first]))
    for i, line in enumerate(lines):
        text = line.rstrip()
        if len(text) >= 40 and text != SEP and set(text) == {'/'}:
            missing.append((i + 1, f'separator of {len(text)} slashes, not 119'))
    missing.sort()
    return missing


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__.strip())
        return 0 if argv else 2
    total = 0
    for path in argv:
        for line_no, text in check_file(path):
            print(f'{path}:{line_no}: {text[:100]}')
            total += 1
    print(f'missing: {total}')
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
