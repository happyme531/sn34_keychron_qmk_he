"""Repository, target and external dependencies shared by every SN34 board."""
from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = json.loads((ROOT / 'platforms/sn34/upstream.json').read_text(encoding='utf-8'))


def keyboard_name():
    name = os.environ.get('SN34_KEYBOARD', 'battle68')
    if not re.fullmatch(r'[a-z0-9_]+(?:/[a-z0-9_]+)*', name):
        raise ValueError(f'Invalid QMK keyboard name: {name}')
    return name


def board_directory():
    return ROOT / 'keyboards' / keyboard_name() / 'board'


def local_config():
    path = ROOT / '.sn34-local.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def location(name, default=None):
    value = os.environ.get('SN34_' + name) or local_config().get(name.lower()) or default
    if value is None:
        raise ValueError(f'Missing external dependency: set SN34_{name} or {name.lower()} in .sn34-local.json')
    return (ROOT / value).resolve()


@dataclass(frozen=True)
class BuildPaths:
    build: Path
    qmk: Path
    sdk: Path
    dfp: Path
    cmsis: Path
    newlib: Path

    @classmethod
    def environment(cls):
        keymap = os.environ.get('SN34_KEYMAP', 'default')
        return cls(location('BUILD_DIR', '.build/sn34/' + keyboard_name() + '/' + keymap), ROOT,
                   location('SDK_DIR'), location('DFP_DIR'), location('CMSIS_DIR'), location('NEWLIB_INCLUDE'))

    def export(self):
        return {'SN34_' + key: str(value) for key, value in
                zip(('BUILD_DIR', 'QMK_DIR', 'SDK_DIR', 'DFP_DIR', 'CMSIS_DIR', 'NEWLIB_INCLUDE'), self.__dict__.values())}

    def roots(self):
        return {'workspace': ROOT, 'qmk': self.qmk, 'sdk': self.sdk,
                'dfp': self.dfp, 'cmsis': self.cmsis, 'newlib': self.newlib}

    def validate(self):
        for path in (ROOT, *self.__dict__.values()):
            if any(c.isspace() for c in str(path)):
                raise ValueError(f'QMK Make requires paths without whitespace: {path}')
        for name, path in self.roots().items():
            if not path.is_dir():
                raise FileNotFoundError(f'Missing {name} dependency: {path}')
        if self.build == ROOT or self.build in ROOT.parents:
            raise ValueError('The build directory must not be the repository or its parent')

    def label(self, path):
        path = path.resolve()
        if path.is_relative_to(ROOT):
            return path.relative_to(ROOT).as_posix()
        for name, root in self.roots().items():
            if path.is_relative_to(root):
                return '@' + name + '/' + path.relative_to(root).as_posix()
        if path.is_relative_to(self.build):
            return '@build/' + path.relative_to(self.build).as_posix()
        raise ValueError(f'Build input outside configured dependency roots: {path}')

    def serialized_roots(self):
        return {name: path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
                for name, path in {**self.roots(), 'build': self.build}.items()}


def write_if_changed(path, data):
    path = Path(path)
    if isinstance(data, str):
        data = data.encode('utf-8')
    if path.is_file() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def qmk_revision(qmk):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(qmk), *args], text=True).strip()
    head = git('rev-parse', 'HEAD')
    if subprocess.run(['git', '-C', str(qmk), 'merge-base', '--is-ancestor', UPSTREAM['base_commit'], head], capture_output=True).returncode:
        raise ValueError(f"Unsupported QMK history: {UPSTREAM['base_commit']} must be an ancestor of {head}")
    return {'qmk_repository': UPSTREAM['repository'], 'qmk_base_commit': UPSTREAM['base_commit'],
            'qmk_commit': head, 'qmk_dirty': bool(git('status', '--porcelain', '--untracked-files=normal'))}


def resolve_input(label, manifest=None):
    if not label.startswith('@'):
        return ROOT / label
    name, relative = label[1:].split('/', 1)
    root = (manifest or {}).get('source_roots', {}).get(name)
    if root is None:
        root = BuildPaths.environment().roots().get(name)
    if not root:
        raise ValueError(f'Unknown input root: {name}')
    root = str(root)
    if os.name == 'nt' and root.startswith('/mnt/') and len(root) > 7:
        root = root[5].upper() + ':/' + root[7:]
    elif os.name == 'nt' and root.startswith('/'):
        root = '//wsl.localhost/' + (manifest or {}).get('wsl_distribution', 'Ubuntu') + root
    return (ROOT / root / relative).resolve()
