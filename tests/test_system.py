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
    "ha_local_status": 0,
    "ha_remote_status": 0,
    "switch_over_flag": 3,
}

SECTION_HIGH_CPU = {**SECTION_NORMAL, "cpu_idle_percent": 5}    # 95% utilization
SECTION_WARN_CPU = {**SECTION_NORMAL, "cpu_idle_percent": 15}   # 85% utilization

SECTION_STANDBY = {**SECTION_NORMAL, "ha_current_state": "standby", "ha_pre_state": "oos"}
SECTION_STANDBY_PEER_UNHEALTHY = {**SECTION_STANDBY, "ha_remote_status": 1}
SECTION_ACTIVE_PEER_UNHEALTHY = {**SECTION_NORMAL, "ha_remote_status": 1}
SECTION_LOCAL_UNHEALTHY = {**SECTION_NORMAL, "ha_local_status": 2}
SECTION_STANDALONE = {**SECTION_NORMAL, "ha_current_state": "standalone", "ha_pre_state": ""}
SECTION_OOS = {**SECTION_NORMAL, "ha_current_state": "oos"}
SECTION_BOOT = {**SECTION_NORMAL, "ha_current_state": "boot"}
SECTION_SWITCHOVER = {**SECTION_NORMAL, "switch_over_flag": 1}
SECTION_NO_HA_FIELD = {k: v for k, v in SECTION_NORMAL.items() if k != "ha_current_state"}


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


# ---------------------------------------------------------------------------
# Check — HA state
# ---------------------------------------------------------------------------

def _ha_result(section, params=None):
    """Return only the HA-related Result from the check output."""
    results = _check(section, params=params)
    return [r for r in results if isinstance(r, Result) and "HA:" in r.summary]


class TestCheckHaState:
    def test_active_peer_healthy_is_ok(self):
        ha = _ha_result(SECTION_NORMAL)
        assert len(ha) == 1
        assert ha[0].state == State.OK

    def test_active_peer_healthy_summary(self):
        ha = _ha_result(SECTION_NORMAL)
        assert "Active" in ha[0].summary
        assert "peer healthy" in ha[0].summary

    def test_active_shows_pre_state_when_different(self):
        # ha_pre_state="standby" differs from ha_current_state="active" → shown
        ha = _ha_result(SECTION_NORMAL)
        assert "was: standby" in ha[0].summary

    def test_active_omits_pre_state_when_same(self):
        section = {**SECTION_NORMAL, "ha_pre_state": "active"}
        ha = _ha_result(section)
        assert "was:" not in ha[0].summary

    def test_active_peer_unhealthy_is_warn(self):
        ha = _ha_result(SECTION_ACTIVE_PEER_UNHEALTHY)
        assert ha[0].state == State.WARN

    def test_active_peer_unhealthy_summary(self):
        ha = _ha_result(SECTION_ACTIVE_PEER_UNHEALTHY)
        assert "peer unhealthy" in ha[0].summary

    def test_standby_peer_healthy_is_ok(self):
        ha = _ha_result(SECTION_STANDBY)
        assert ha[0].state == State.OK

    def test_standby_peer_healthy_summary(self):
        ha = _ha_result(SECTION_STANDBY)
        assert "Standby" in ha[0].summary
        assert "peer healthy" in ha[0].summary

    def test_standby_peer_unhealthy_is_warn(self):
        ha = _ha_result(SECTION_STANDBY_PEER_UNHEALTHY)
        assert ha[0].state == State.WARN

    def test_local_unhealthy_is_warn(self):
        ha = _ha_result(SECTION_LOCAL_UNHEALTHY)
        assert ha[0].state == State.WARN
        assert "local unhealthy" in ha[0].summary

    def test_standalone_is_ok(self):
        ha = _ha_result(SECTION_STANDALONE)
        assert ha[0].state == State.OK
        assert "Standalone" in ha[0].summary

    def test_oos_is_crit(self):
        ha = _ha_result(SECTION_OOS)
        assert ha[0].state == State.CRIT
        assert "out of service" in ha[0].summary

    def test_boot_is_warn(self):
        ha = _ha_result(SECTION_BOOT)
        assert ha[0].state == State.WARN
        assert "booting" in ha[0].summary

    def test_switchover_is_warn(self):
        ha = _ha_result(SECTION_SWITCHOVER)
        assert ha[0].state == State.WARN
        assert "Switchover" in ha[0].summary

    def test_no_ha_field_emits_no_ha_result(self):
        ha = _ha_result(SECTION_NO_HA_FIELD)
        assert ha == []

    def test_cpu_check_still_runs_alongside_ha(self):
        results = _check(SECTION_NORMAL)
        cpu_results = [r for r in results if isinstance(r, Result) and "CPU" in r.summary]
        assert len(cpu_results) == 1
