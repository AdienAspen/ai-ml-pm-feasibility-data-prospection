from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESTRICTED_TERMS_FILE = ROOT / 'config' / 'restricted_terms.local.txt'
BLOCKED_TRACKED_PREFIXES = ('data/', 'reports/internal/', 'artifacts/internal/', 'logs/')
BLOCKED_SUFFIXES = ('.zip', '.7z', '.tar', '.gz', '.parquet', '.feather', '.sqlite', '.db')
TEXT_EXTENSIONS = {'.py', '.md', '.toml', '.json', '.csv', '.txt', '.gitignore', '.yml', '.yaml'}


def run_git(args: list[str]) -> str:
    result = subprocess.run(['git', *args], cwd=ROOT, check=True, text=True, capture_output=True)
    return result.stdout


def tracked_files() -> list[str]:
    return [line for line in run_git(['ls-files']).splitlines() if line]


def read_restricted_terms() -> list[str]:
    if not RESTRICTED_TERMS_FILE.exists():
        return []
    terms = []
    for raw in RESTRICTED_TERMS_FILE.read_text(encoding='utf-8').splitlines():
        term = raw.strip()
        if term and not term.startswith('#'):
            terms.append(term)
    return terms


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in {'.gitignore', '.python-version'}


def main() -> int:
    failures: list[str] = []
    files = tracked_files()

    for rel_path in files:
        lowered = rel_path.lower()
        if lowered.startswith(BLOCKED_TRACKED_PREFIXES) and not lowered.endswith('/.gitkeep'):
            failures.append(f'blocked tracked path: {rel_path}')
        if lowered.endswith(BLOCKED_SUFFIXES):
            failures.append(f'blocked tracked artifact type: {rel_path}')

    restricted_terms = read_restricted_terms()
    if restricted_terms:
        lowered_terms = [(term, term.lower()) for term in restricted_terms]
        for rel_path in files:
            file_path = ROOT / rel_path
            if not is_text_file(file_path):
                continue
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore').lower()
            except OSError as exc:
                failures.append(f'could not read tracked text file {rel_path}: {exc}')
                continue
            for original, lowered in lowered_terms:
                if lowered in content or lowered in rel_path.lower():
                    failures.append(f'restricted term found in tracked file: {rel_path} :: {original}')

    if failures:
        print('Release safety check failed:')
        for failure in failures:
            print(f'- {failure}')
        return 1

    print('Release safety check passed.')
    print(f'Tracked files checked: {len(files)}')
    if restricted_terms:
        print(f'Restricted local terms checked: {len(restricted_terms)}')
    else:
        print('No local restricted term file found; path/artifact checks only.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
