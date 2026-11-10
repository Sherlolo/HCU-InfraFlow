"""Check portable skill entrypoints and bundled Markdown resource links offline."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


def check(root):
    root = Path(root).resolve()
    errors = []
    skills = sorted((root / 'skills').glob('*/SKILL.md'))
    files = sorted({*root.glob('skills/**/*.md'), *root.glob('docs/**/*.md'), root / 'README.md'})
    for entry in skills:
        text = entry.read_text(encoding='utf-8')
        front = re.match(r'\A---\s*\n(.*?)\n---\s*\n', text, re.S)
        if not front:
            errors.append(f'{entry.relative_to(root)}: missing YAML frontmatter')
            continue
        name = re.search(r'^name:\s*([a-z0-9-]+)\s*$', front[1], re.M)
        if not name or name[1] != entry.parent.name or len(name[1]) > 64:
            errors.append(f'{entry.relative_to(root)}: skill name/folder mismatch')
        if not re.search(r'^description:\s*\S', front[1], re.M):
            errors.append(f'{entry.relative_to(root)}: missing description')
    for path in files:
        if not path.is_file():
            errors.append(f'{path.relative_to(root)}: missing resource')
            continue
        text = path.read_text(encoding='utf-8')
        if re.search(r'/(?:public4?/home|Users)/|[A-Za-z]:\\Users\\', text):
            errors.append(f'{path.relative_to(root)}: machine-specific home dependency')
        for raw in re.findall(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)', text):
            target = raw.strip().strip('<>')
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            candidate = (path.parent / unquote(url.path)).resolve()
            if not candidate.is_relative_to(root) or not candidate.is_file():
                errors.append(f'{path.relative_to(root)}: missing/outside link {target}')
        if 'skills' in path.relative_to(root).parts:
            # Project-bound documents are commonly named in inline code rather
            # than linked relative to an installed skill directory.
            for resource in re.findall(r'`((?:docs|scripts)/[^`\s]+\.(?:md|py))`', text):
                if not (root / resource).is_file():
                    errors.append(f'{path.relative_to(root)}: missing project resource {resource}')
    if not skills:
        errors.append('No bundled skills found')
    return {'status': 'pass' if not errors else 'fail', 'skills': len(skills),
            'markdown_files': len(files), 'errors': errors,
            'scope': 'Offline names, portability and local resource links; not behavioral or hardware validation'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = check(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
