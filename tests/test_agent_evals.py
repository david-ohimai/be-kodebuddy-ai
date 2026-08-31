"""
Pytest entry point for the regression eval set (app/agent/evals/).

Run with: pytest tests/test_agent_evals.py -v

Each case is its own parametrized test so a regression from a prompt/
threshold change points at the specific curriculum scenario that flipped,
rather than one opaque pass/fail for the whole set.
"""

from __future__ import annotations

import pytest

from app.agent.evals.dataset import EVAL_CASES
from app.agent.evals.runner import run_case


@pytest.mark.parametrize(
    "case", EVAL_CASES, ids=[case.id for case in EVAL_CASES]
)
def test_eval_case(case):
    result = run_case(case)
    assert result.passed, "; ".join(result.failures)
