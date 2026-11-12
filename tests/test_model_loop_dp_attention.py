import pytest

from hcu_infra_agent.core import FlowError
from hcu_infra_agent.model_loop import _phase_world


def _args(**overrides):
    value = {
        "prefill_tp": 8,
        "prefill_dp": 8,
        "prefill_pp": 1,
        "decode_tp": 8,
        "decode_dp": 8,
        "decode_pp": 1,
        "dp_attention": False,
        "prefill_dp_attention": None,
        "decode_dp_attention": None,
    }
    value.update(overrides)
    return value


def test_phase_world_ordinary_tp_dp_pp():
    args = _args(prefill_pp=2)
    assert _phase_world(args, "prefill") == 128
    assert _phase_world(args, "decode") == 64


def test_phase_world_dp_attention_shares_tp_pp_devices():
    args = _args(dp_attention=True, prefill_pp=2)
    assert _phase_world(args, "prefill") == 16
    assert _phase_world(args, "decode") == 8


def test_phase_world_phase_override_does_not_use_global_fallback():
    args = _args(dp_attention=True, prefill_dp_attention=False)
    assert _phase_world(args, "prefill") == 64
    assert _phase_world(args, "decode") == 8


def test_phase_world_dp_attention_requires_divisible_tp():
    with pytest.raises(FlowError, match="TP divisible by DP"):
        _phase_world(_args(dp_attention=True, prefill_dp=3), "prefill")
