#!/usr/bin/env python3
"""
Tests for the sansay_vsx_system check plugin.

Covers:
  - discovery based on cpu_idle_percent presence
  - empty section yields UNKNOWN
  - CPU utilization calculation and threshold alerting
  - session utilization calculation and threshold alerting
  - session drop detection via value_store
"""

import pytest
from unittest.mock import patch

from cmk.agent_based.v2 import Metric, Result, Service, State

from cmk_addons.plugins.sansay_vsx.agent_based.sansay_vsx_system import (
    check_sansay_vsx_system,
    discovery_sansay_vsx_system,
)


DEFAULT_PARAMS = {
    "cpu_levels": ("fixed", (80.0, 90.0)),
    "session_levels": ("fixed", (80.0, 90.0)),
    "session_drop_levels": ("fixed", (10.0, 20.0)),
}

SECTION_NORMAL = {
    "cpu_idle_percent": 95,
    "sum_active_session": 100,
    "max_session_allowed": 1000,
    "cluster_active_session": 100,
    "ha_current_state": "active",
    "ha_pre_state": "standby",
}

SECTION_HIGH_CPU = {**SECTION_NORMAL, "cpu_idle_percent": 5}    # 95% utilization
SECTION_WARN_CPU = {**SECTION_NORMAL, "cpu_idle_percent": 15}   # 85% utilization


def _check(section, params=None, value_store=None):
    vs = value_store if value_store is not None else {}
    with patch(
        "cmk_addons.plugins.sansay_vsx.agent_based.sansay_vsx_system.get_value_store",
        return_value=vs,
    ):
        return list(check_sansay_vsx_system(params=params or DEFAULT_PARAMS, section=section))


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class TestDiscoverySansayVsxSystem:
    def test_discovers_service_when_cpu_present(self):
        services = list(discovery_sansay_vsx_system(SECTION_NORMAL))
        assert len(services) == 1
        assert isinstance(services[0], Service)

    def test_no_service_when_cpu_absent(self):
        assert list(discovery_sansay_vsx_system({"ha_current_state": "active"})) == []

    def test_no_service_for_empty_section(self):
        assert list(discovery_sansay_vsx_system({})) == []


# ---------------------------------------------------------------------------
# Check — empty / no data
# ---------------------------------------------------------------------------

class TestCheckNoData:
    def test_unknown_on_empty_section(self):
        results = _check({})
        assert len(results) == 1
        assert results[0].state == State.UNKNOWN


# ---------------------------------------------------------------------------
# Check — CPU
# ---------------------------------------------------------------------------

class TestCheckCpu:
    def test_normal_cpu_is_ok(self):
        results = _check(SECTION_NORMAL)
        cpu_results = [r for r in results if isinstance(r, Result) and "CPU" in r.summary]
        assert cpu_results[0].state == State.OK

    def test_cpu_utilization_summary_text(self):
        results = _check(SECTION_NORMAL)
        cpu_results = [r for r in results if isinstance(r, Result) and "CPU" in r.summary]
        assert "5.0%" in cpu_results[0].summary   # 100 - 95 = 5%

    def test_cpu_metric_emitted(self):
        results = _check(SECTION_NORMAL)
        metrics = {r.name: r.value for r in results if isinstance(r, Metric)}
        assert "cpu_utilization" in metrics
        assert metrics["cpu_utilization"] == pytest.approx(5.0)

    def test_cpu_warn_state(self):
        # cpu_idle=15 → utilization=85% → above warn=80
        results = _check(SECTION_WARN_CPU)
        cpu_results = [r for r in results if isinstance(r, Result) and "CPU" in r.summary]
        assert cpu_results[0].state == State.WARN

    def test_cpu_crit_state(self):
        # cpu_idle=5 → utilization=95% → above crit=90
        results = _check(SECTION_HIGH_CPU)
        cpu_results = [r for r in results if isinstance(r, Result) and "CPU" in r.summary]
        assert cpu_results[0].state == State.CRIT


# ---------------------------------------------------------------------------
# Check — session utilization
# ---------------------------------------------------------------------------

class TestCheckSessionUtilization:
    def test_session_utilization_ok(self):
        # 100/1000 = 10% — below warn
        results = _check(SECTION_NORMAL)
        session_results = [r for r in results if isinstance(r, Result) and "Session" in r.summary]
        assert session_results[0].state == State.OK

    def test_session_utilization_metric(self):
        results = _check(SECTION_NORMAL)
        metrics = {r.name: r.value for r in results if isinstance(r, Metric)}
        assert "session_utilization" in metrics
        assert metrics["session_utilization"] == pytest.approx(10.0)

    def test_session_utilization_warn(self):
        section = {**SECTION_NORMAL, "sum_active_session": 850, "max_session_allowed": 1000}
        results = _check(section)
        session_results = [r for r in results if isinstance(r, Result) and "Session" in r.summary]
        assert session_results[0].state == State.WARN

    def test_session_utilization_crit(self):
        section = {**SECTION_NORMAL, "sum_active_session": 920, "max_session_allowed": 1000}
        results = _check(section)
        session_results = [r for r in results if isinstance(r, Result) and "Session" in r.summary]
        assert session_results[0].state == State.CRIT


# ---------------------------------------------------------------------------
# Check — session drop detection
# ---------------------------------------------------------------------------

class TestCheckSessionDrop:
    def test_no_drop_summary_on_first_run(self):
        """No previous value stored → no 'Drop' in summary."""
        results = _check(SECTION_NORMAL, value_store={})
        session_results = [r for r in results if isinstance(r, Result) and "Session" in r.summary]
        assert "Drop" not in session_results[0].summary

    def test_drop_shown_in_summary(self):
        vs = {"sansay_vsx.session_utilization": 30.0}
        # current is 10%, previous 30% → drop of 20%
        results = _check(SECTION_NORMAL, value_store=vs)
        session_results = [r for r in results if isinstance(r, Result) and "Session" in r.summary]
        assert "Drop" in session_results[0].summary

    def test_large_drop_triggers_crit(self):
        # drop_crit is 20%; drop 30→10 = 20% drop → crit
        vs = {"sansay_vsx.session_utilization": 30.0}
        results = _check(SECTION_NORMAL, value_store=vs)
        session_results = [r for r in results if isinstance(r, Result) and "Session" in r.summary]
        assert session_results[0].state == State.CRIT

    def test_moderate_drop_triggers_warn(self):
        # drop_warn is 10%; drop 25→10 = 15% drop → warn
        vs = {"sansay_vsx.session_utilization": 25.0}
        results = _check(SECTION_NORMAL, value_store=vs)
        session_results = [r for r in results if isinstance(r, Result) and "Session" in r.summary]
        assert session_results[0].state == State.WARN

    def test_value_store_updated_after_check(self):
        vs = {}
        _check(SECTION_NORMAL, value_store=vs)
        assert "sansay_vsx.session_utilization" in vs
        assert vs["sansay_vsx.session_utilization"] == pytest.approx(10.0)
