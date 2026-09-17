"""Portable path-scrubbed views. Never substitute these for exact raw evidence.

Raw process artifacts remain immutable under .local. Original hashes are kept
separately from view hashes. Binary/source/cache files are hash-only because a
text substitution cannot prove a binary asset free of workstation metadata.
This utility does not certify process results, remove secrets from arbitrary
files, or grant acceptance. Exact verification still requires the local raw set.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re

SCHEMA = 'HH-GT04-EVIDENCE-VIEW-1'
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_FILES = 10000
TEXT = {'.json', '.jsonl', '.txt', '.log'}
ABSOLUTE = re.compile(r'(?<![\w])(?:[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.?-]+[\\/]|/(?:Users|home|tmp|var|mnt|workspace|private|opt)/)', re.I)


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def pairs(values):
    result = {}
    for key, value in values:
        need(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


class PathView:
    def __init__(self, roots, *, forbidden_words=()):
        # Registrations are local only; their actual values never enter manifest.
        need(0 < len(roots) <= 16, 'ROOT_REGISTRATION_LIMIT')
        self.rules = []
        for label, root in roots.items():
            need(re.fullmatch(r'[A-Z][A-Z0-9_]{0,31}', label), 'ROOT_LABEL')
            need(type(root) is str and len(root) > 3 and ABSOLUTE.search(root), 'ROOT_PATH')
            need(not root.endswith(('\\', '/')), 'ROOT_TRAILING_SEPARATOR')
            for variant in {root, root.replace('\\', '/'), root.replace('/', '\\')}:
                self.rules.append((variant, '$' + label))
        self.rules.sort(key=lambda rule: (-len(rule[0]), rule[0]))
        self.forbidden = tuple(forbidden_words)

    def text(self, value):
        need(len(value.encode('utf-8')) <= MAX_BYTES, 'TEXT_LIMIT')
        for literal, label in self.rules:
            # In a path, only an actual component boundary grants substitution.
            value = re.sub(re.escape(literal) + r'(?=$|[\\/\r\n"\'])',
                           lambda match: label, value, flags=re.I)
        need(ABSOLUTE.search(value) is None, 'UNREGISTERED_ABSOLUTE_PATH')
        for word in self.forbidden:
            need(word.casefold() not in value.casefold(), 'FORBIDDEN_PERSONAL_VALUE')
        return value

    def value(self, value, depth=0):
        need(depth <= 64, 'JSON_DEPTH_LIMIT')
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.value(item, depth + 1) for item in value]
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                key = self.text(key)
                need(key not in result, 'NORMALIZED_KEY_COLLISION')
                result[key] = self.value(child, depth + 1)
            return result
        return value

    def artifact(self, name, raw):
        suffix = PurePosixPath(name).suffix
        if 'source' in PurePosixPath(name).parts or suffix not in TEXT:
            return None, 'hash-only-source-or-binary'
        value = raw.decode('utf-8', 'strict')
        if suffix == '.json':
            parsed = json.loads(value, object_pairs_hook=pairs,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
            clean = self.value(parsed)
            return (raw, 'exact-text') if parsed == clean else (encoded(clean), 'sanitized-json')
        # JSONL records keep checksums in the original hash domain. A changed
        # view is explanatory only, never a loadable journal/receipt.
        clean = self.text(value).encode('utf-8')
        return clean, 'exact-text' if clean == raw else 'sanitized-utf8'


def regular(path):
    info = path.lstat()
    need(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPARSE_PATH')
    return info


def inventory(root):
    root = Path(root).absolute()
    for path in (root, *root.parents):
        regular(path)
    files = {}
    total = 0
    for directory, names, leaves in os.walk(root, followlinks=False):
        for name in names:
            regular(Path(directory) / name)
        for name in leaves:
            path = Path(directory) / name
            info = regular(path)
            need(path.is_file() and info.st_size <= MAX_BYTES, 'FILE_LIMIT')
            total += info.st_size
            need(total <= MAX_TOTAL and len(files) < MAX_FILES, 'INVENTORY_LIMIT')
            relative = path.relative_to(root).as_posix()
            need(not ABSOLUTE.search(relative), 'RELATIVE_NAME')
            files[relative] = sha(path.read_bytes())
    return dict(sorted(files.items()))


def build(raw_root, output, scrubber):
    raw_root, output = Path(raw_root).absolute(), Path(output).absolute()
    need(not output.exists(), 'VIEW_ALREADY_EXISTS')
    need(not output.is_relative_to(raw_root), 'VIEW_INSIDE_RAW')
    # Validate the complete plan before making a partial public view.
    before = inventory(raw_root)
    rows, artifacts = {}, {}
    for name, digest in before.items():
        scrubber.text(name)
        data = (raw_root / name).read_bytes()
        need(sha(data) == digest, 'RAW_CHANGED_DURING_VIEW')
        clean, mode = scrubber.artifact(name, data)
        rows[name] = {'raw_sha256': digest, 'raw_size': len(data), 'mode': mode,
                      'view_sha256': sha(clean) if clean is not None else None,
                      'view_size': len(clean) if clean is not None else None}
        if clean is not None:
            artifacts[name] = clean
    need(inventory(raw_root) == before, 'RAW_CHANGED_DURING_VIEW')
    manifest = {'schema': SCHEMA, 'files': rows, 'raw_inventory_sha256': sha(encoded(before)),
                'formal_acceptance': False, 'exact_raw_available_in_view': False,
                'requires_local_raw_for_exact_verification': True}
    output.mkdir(parents=True, exist_ok=False)
    for name, data in artifacts.items():
        destination = output / 'view' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    (output / 'manifest.json').write_bytes(encoded(manifest))
    return manifest


def verify(output, *, raw_root=None, scrubber=None):
    output = Path(output).absolute()
    for path in (output / 'manifest.json', output, *output.parents):
        regular(path)
    manifest = json.loads((output / 'manifest.json').read_bytes(), object_pairs_hook=pairs)
    need(manifest.get('schema') == SCHEMA and manifest.get('formal_acceptance') is False
         and manifest.get('exact_raw_available_in_view') is False
         and manifest.get('requires_local_raw_for_exact_verification') is True, 'VIEW_SCOPE')
    rows = manifest['files']
    expected = {}
    for name, row in rows.items():
        parts = PurePosixPath(name).parts
        need(parts and '..' not in parts and not name.startswith('/') and '\\' not in name
             and ':' not in name, 'UNSAFE_MANIFEST_PATH')
        if row['view_sha256'] is not None:
            expected[name] = row['view_sha256']
    actual = inventory(output / 'view') if (output / 'view').exists() else {}
    need(actual == expected, 'VIEW_INVENTORY_MISMATCH')
    for name in expected:
        need((output / 'view' / name).stat().st_size == rows[name]['view_size'], 'VIEW_SIZE')
    raw_hashes = {name: row['raw_sha256'] for name, row in rows.items()}
    need(sha(encoded(raw_hashes)) == manifest['raw_inventory_sha256'], 'RAW_INVENTORY_DIGEST')
    if raw_root is not None:
        need(scrubber is not None, 'SCRUBBER_REQUIRED')
        need(inventory(raw_root) == raw_hashes, 'LOCAL_RAW_INVENTORY_MISMATCH')
        for name, row in rows.items():
            raw = (Path(raw_root) / name).read_bytes()
            need(len(raw) == row['raw_size'], 'RAW_SIZE')
            clean, mode = scrubber.artifact(name, raw)
            need(mode == row['mode'] and (sha(clean) if clean is not None else None) == row['view_sha256'],
                 'TRANSFORM_BINDING_MISMATCH')
    return {'view_integrity': True, 'raw_transform_verified': raw_root is not None,
            'files': len(rows), 'view_files': len(expected), 'formal_acceptance': False}
