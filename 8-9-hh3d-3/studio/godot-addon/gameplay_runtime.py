"""One byte-bound Python generation for the internal gameplay owner.

Only the fixed adapter inventory is executable here. This is a source loader,
not a sandbox: the installed host and Python interpreter remain trusted. No
global import hook or shared ``studio`` module is replaced. Existing owners
must be closed and reopened in a new generation after a source update.
"""
from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import types

_MODULE_LOCK = threading.RLock()


class RuntimeSourceError(ValueError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _need(condition):
    if not condition:
        raise RuntimeSourceError('GAMEPLAY_OWNER_IMPORT_RELEASE_CHANGED')


class GameplayRuntime:
    # Namespace packages carry no executable source. Real package initializers
    # and all transitive internal imports must belong to the captured inventory.
    _NAMESPACES = {'studio', 'studio.host', 'studio.host.core', 'studio.addon'}

    def __init__(self, studio: Path, owner_code):
        self.studio = studio.resolve()
        path = self.studio / 'godot-addon/linux_executor.py'
        raw = path.read_bytes()
        # Bootstrap is stdlib-only. Its bounded reader then checks every input,
        # including itself, before any owner/session code can execute.
        executor = types.ModuleType('_hh_gameplay_executor_bootstrap')
        executor.__file__ = str(path)
        exec(compile(raw, str(path), 'exec', dont_inherit=True), executor.__dict__)
        self._read_file = executor._read_file
        self._raw = {name: self._read_file(self.studio / name, 1048576)
                     for name in executor.GAMEPLAY_RUNTIME_FILES}
        _need(self._raw['godot-addon/linux_executor.py'] == raw)
        owner_path = self.studio / 'godot-addon/gameplay_source_owner.py'
        _need(owner_code == compile(self._raw['godot-addon/gameplay_source_owner.py'],
                                    str(owner_path), 'exec', dont_inherit=True))
        self.files = {name: _sha(value) for name, value in self._raw.items()}
        self.digest = _sha(json.dumps(self.files, sort_keys=True, separators=(',', ':')).encode())
        self._prefix = '_hh_gameplay_runtime_' + _sha(
            str(self.studio).encode() + b'\0' + self.digest.encode())
        self._lock = _MODULE_LOCK
        self._paths = {}
        for name in self._raw:
            if not name.endswith('.py'):
                continue
            logical = 'studio.' + name[:-3].replace('godot-addon/', 'addon/').replace('/', '.')
            package = logical.endswith('.__init__')
            self._paths[logical.removesuffix('.__init__')] = (name, package)
        # Match the exact helper bytes executed by the owner bootstrap too.
        helper = sys.modules.get(__name__)
        _need(helper is not None and getattr(helper, '_gameplay_source', None)
              == self.files['godot-addon/gameplay_runtime.py'])
        self.ensure_current()

    def ensure_current(self):
        for name, expected in self.files.items():
            _need(_sha(self._read_file(self.studio / name, 1048576)) == expected)

    def closure(self):
        self.ensure_current()
        return dict(self.files), self.digest

    def _import(self, name, globals=None, locals=None, fromlist=(), level=0):
        if level:
            package = globals['_gameplay_package']
            name = importlib.util.resolve_name('.' * level + name, package)
        # The host supports a legacy direct-studio-root import spelling. Both
        # spellings resolve inside this generation; neither falls back to disk.
        alias = name.split('.')[0] if name.split('.')[0] in {'protocol', 'host'} else None
        if alias:
            name = 'studio.' + name
        if name == 'studio' or name.startswith('studio.'):
            module = self.module(name)
            if fromlist:
                for item in fromlist:
                    if item != '*' and not hasattr(module, item):
                        self.module(name + '.' + item)
                return module
            return self.module('studio.' + alias if alias else 'studio')
        return builtins.__import__(name, globals, locals, fromlist, 0)

    def module(self, logical):
        with self._lock:
            _need(logical in self._paths or logical in self._NAMESPACES)
            key = self._prefix + '.' + logical
            if key in sys.modules:
                module = sys.modules[key]
                _need(getattr(module, '_gameplay_generation', None) == self.digest)
                return module
            parent, _, leaf = logical.rpartition('.')
            if parent:
                self.module(parent)
                # A package initializer may already have imported this child.
                if key in sys.modules:
                    return self.module(logical)
            module = types.ModuleType(key)
            relative, package = self._paths.get(logical, (None, True))
            module._gameplay_generation = self.digest
            module._gameplay_package = logical if package else parent
            module.__package__ = self._prefix + '.' + module._gameplay_package
            module.__builtins__ = {**vars(builtins), '__import__': self._import}
            if package:
                module.__path__ = []  # No unlisted module may be imported from disk.
            if relative is not None:
                module.__file__ = str(self.studio / relative)
                module._gameplay_source = self.files[relative]
            sys.modules[key] = module
            if parent:
                setattr(sys.modules[self._prefix + '.' + parent], leaf, module)
            try:
                if relative is not None:
                    exec(compile(self._raw[relative], module.__file__, 'exec',
                                 dont_inherit=True), module.__dict__)
            except BaseException:
                del sys.modules[key]
                if parent:
                    delattr(sys.modules[self._prefix + '.' + parent], leaf)
                raise
            return module

    def addon(self, name):
        _need(name in {'linux_executor', 'gameplay_source_profile', 'gameplay_log_policy',
                      'publication_session', 'contract'})
        return self.module('studio.addon.' + name)
