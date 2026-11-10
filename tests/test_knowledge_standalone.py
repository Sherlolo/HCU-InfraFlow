"""Knowledge retrieval works with data alone, without reference-project executables."""
import copy
import hashlib
import json
import subprocess

import pytest

from hcu_infra_agent import references
from hcu_infra_agent.cli import main
from hcu_infra_agent.core import FlowError


def data_checkout(tmp_path):
    root = tmp_path / 'knowledge-source'
    page = root / 'knowledge/projects/attention/local/topics/paged-kv.md'
    page.parent.mkdir(parents=True)
    page.write_text('# Paged attention\nHCU gfx938 DTK: check KV cache stride and backend dispatch.\n')
    subprocess.run(['git', 'init', str(root)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(root), 'add', 'knowledge'], check=True, capture_output=True)
    return root, page


def test_cli_data_only_search_and_read_preserve_source(tmp_path, monkeypatch, capsys):
    root, page = data_checkout(tmp_path)
    before = hashlib.sha256(page.read_bytes()).hexdigest()
    binding = tmp_path / 'task' / 'knowledge.json'
    monkeypatch.chdir(tmp_path)
    assert not (root / 'kb.py').exists()
    assert main(['knowledge-bind', str(root), str(binding)]) == 0
    capsys.readouterr()
    # Any accidental fallback to external kb.py/full skill bindings fails.
    from hcu_infra_agent import bindings
    monkeypatch.setattr(bindings, 'verify', lambda *a: pytest.fail('external executable binding used'))
    assert main(['knowledge-query', str(binding), 'gfx938 KV']) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['search_scope'] == 'curated' and len(result['hits']) == 1
    assert main(['knowledge-read', str(binding), result['hits'][0]['relative_path']]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body['sha256'] == before
    assert 'backend dispatch' in body['lines'][1]['text']
    assert hashlib.sha256(page.read_bytes()).hexdigest() == before
    assert not (tmp_path / '.work').exists()
    assert subprocess.check_output(['git', '-C', str(root), 'ls-files', '--others', '--exclude-standard']) == b''


def test_binding_cannot_write_into_reference_checkout(tmp_path):
    root, _ = data_checkout(tmp_path)
    with pytest.raises(FlowError, match='outside'):
        references.bind_knowledge(root, root / 'binding.json')
    assert not (root / 'binding.json').exists()


def test_binding_identity_and_read_escape_are_checked(tmp_path):
    root, _ = data_checkout(tmp_path)
    record = references.bind_knowledge(root, tmp_path / 'binding.json')
    altered = copy.deepcopy(record)
    altered['roots']['knowledge_root'] = str(tmp_path)
    with pytest.raises(FlowError, match='identity'):
        references.search(altered, 'knowledge', 'KV')
    outside = root / 'outside.md'; outside.write_text('not knowledge data')
    with pytest.raises(FlowError):
        references.read(record, 'knowledge', '../outside.md')
    link = root / 'knowledge/escape.md'; link.symlink_to(outside)
    with pytest.raises(FlowError):
        references.read(record, 'knowledge', 'escape.md')


def test_symlinked_knowledge_directory_cannot_escape(tmp_path):
    outside = tmp_path / 'outside'; outside.mkdir()
    root = tmp_path / 'source'; root.mkdir()
    (root / 'knowledge').symlink_to(outside, target_is_directory=True)
    with pytest.raises(FlowError, match='inside'):
        references.bind_knowledge(root, tmp_path / 'binding.json')
