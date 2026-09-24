"""Smoke test: the Streamlit app runs end to end on the sample data."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_app_runs_on_every_sample_group():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    for label in ["Sample Co (12 employees)", "Sample Co (45 employees)"]:
        at.sidebar.radio[0].set_value(label).run()
        assert not at.exception
        assert len(at.metric) == 4 and len(at.dataframe) == 3  # rate editor + options + per-employee


def test_app_handles_no_feasible_option():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.selectbox(key="max_deductible").set_value(1500).run()
    assert not at.exception
    assert any("No option meets every goal" in w.value for w in at.warning)


def test_app_benchmarks_against_a_specific_carrier():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.selectbox[0].set_value("Highmark Coverage Advantage Inc.").run()
    assert not at.exception
    assert any("Strong case to push back" in i.value for i in at.info)  # 18% > 13.59% top of range
