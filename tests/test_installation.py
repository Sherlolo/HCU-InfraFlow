import json
from pathlib import Path
import pytest
from hcu_infra_agent import cookbook, installation
from hcu_infra_agent.core import FlowError


def test_official_links_and_fixed_revision(monkeypatch):
    commit='b'*40
    def fetch(url):
        if '/commits/' in url:return json.dumps({'sha':commit}).encode()
        if '/git/trees/' in url:return json.dumps({'tree':[{'path':'docs/qwen38/sglang.md'}]}).encode()
        return b'# Qwen3.8 SGLang\n[Images](../../images.md)\n'
    monkeypatch.setattr(cookbook,'fetch',fetch)
    result=cookbook.search('Qwen3.8 SGLang')
    assert result['hits'][0]['url'].startswith(cookbook.URL+'/blob/'+commit)
    page=cookbook.read(result['hits'][0]['relative_path'],commit=commit)
    assert page['links'][0]['url']==cookbook.URL+'/blob/'+commit+'/images.md'
    with pytest.raises(FlowError):cookbook.read('../../secret.md',commit=commit)


def test_doctor_manual_knowledge_and_container_hint(tmp_path):
    result=installation.doctor({})
    rows={r['component']:r for r in result['components']}
    assert result['status']=='incomplete' and result['hardware_validated'] is False
    assert rows['knowledge-manual']['status']=='missing'
    assert 'manually install' in rows['knowledge-manual']['action']
    assert 'container' in result['container_hint']
    assert not list(tmp_path.iterdir())


def test_fetch_does_not_overwrite(tmp_path):
    existing=tmp_path/'existing';existing.mkdir();(existing/'keep').write_text('keep')
    with pytest.raises(FlowError):installation.fetch_simtools(existing)
    assert (existing/'keep').read_text()=='keep'


def test_readme_is_generic():
    text=(Path(__file__).resolve().parents[1]/'README.md').read_text()
    assert '/public/home/' not in text and 'NMZ_zz_26' not in text and 'yangyn' not in text
    assert 'HYGON-AI/inference-cookbook-das' in text and '手动安装' in text
