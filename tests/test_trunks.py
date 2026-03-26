#!/usr/bin/env python3
"""
Tests for the sansay_vsx_trunks check plugin.

Covers:
  - discovery yields one service per trunk
  - check returns UNKNOWN when trunk is absent from section (crash 2026-02-19)
  - check returns OK with correct metrics for a healthy trunk
  - threshold alerting for egress/ingress/realtime directions
"""

import pytest  # noqa: F401 — used by pytest.approx in threshold tests

from cmk.agent_based.v2 import Metric, Result, State

from cmk_addons.plugins.sansay_vsx.agent_based.sansay_vsx_trunks import (
    check_sansay_vsx_trunks,
    discovery_sansay_vsx_trunks,
)


DEFAULT_PARAMS = {
    "egress": {
        "failed_call_ratio_levels": ("no_levels", None),
        "answer_seize_ratio_levels": ("no_levels", None),
        "avg_postdial_delay_levels": ("no_levels", None),
    },
    "ingress": {
        "failed_call_ratio_levels": ("no_levels", None),
        "answer_seize_ratio_levels": ("no_levels", None),
        "avg_postdial_delay_levels": ("no_levels", None),
    },
    "gw_egress_stat": {
        "failed_call_ratio_levels": ("no_levels", None),
        "answer_seize_ratio_levels": ("no_levels", None),
        "avg_postdial_delay_levels": ("no_levels", None),
    },
    "realtime": {
        "origination_utilization_levels": ("no_levels", None),
        "termination_utilization_levels": ("no_levels", None),
    },
}

SECTION = {
    "100": {
        "alias": "Carrier In",
        "recid": 1,
        "calculated_stats": {
            "ingress": {
                "avg_postdial_delay": 0.3,
                "avg_call_duration": 50.0,
                "failed_call_ratio": 10.0,
                "answer_seize_ratio": 90.0,
            },
            "egress": {
                "avg_postdial_delay": 0.25,
                "avg_call_duration": 45.0,
                "failed_call_ratio": 0.0,
                "answer_seize_ratio": 100.0,
            },
            "realtime": {
                "origination_sessions": 3,
                "origination_utilization": 3.0,
                "termination_sessions": 5,
                "termination_utilization": 5.0,
            },
        },
    },
    "200": {
        "alias": "Customer Out",
        "recid": 2,
        "calculated_stats": {
            "ingress": {
                "avg_postdial_delay": 0.0,
                "avg_call_duration": 0.0,
                "failed_call_ratio": 0.0,
                "answer_seize_ratio": 0.0,
            },
            "egress": {
                "avg_postdial_delay": 0.0,
                "avg_call_duration": 0.0,
                "failed_call_ratio": 0.0,
                "answer_seize_ratio": 0.0,
            },
            "realtime": {
                "origination_sessions": 0,
                "origination_utilization": 0.0,
                "termination_sessions": 0,
                "termination_utilization": 0.0,
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class TestDiscoverySansayVsxTrunks:
    def test_discovers_all_trunks(self):
        services = list(discovery_sansay_vsx_trunks(SECTION))
        assert len(services) == 2

    def test_service_item_is_id_plus_alias(self):
        services = {s.item for s in discovery_sansay_vsx_trunks(SECTION)}
        assert "100 Carrier In" in services
        assert "200 Customer Out" in services

    def test_empty_section_yields_no_services(self):
        assert list(discovery_sansay_vsx_trunks({})) == []


# ---------------------------------------------------------------------------
# Check — missing trunk (crash regression)
# ---------------------------------------------------------------------------

class TestCheckMissingTrunk:
    def test_unknown_when_trunk_absent_from_section(self):
        """
        Regression (crash 2026-02-19): trunk service exists but trunk ID is no
        longer in the agent data.  Must yield UNKNOWN rather than KeyError.
        """
        results = list(check_sansay_vsx_trunks(
            item="99989 Transnexus Osprey",
            params=DEFAULT_PARAMS,
            section=SECTION,
        ))
        assert len(results) == 1
        assert isinstance(results[0], Result)
        assert results[0].state == State.UNKNOWN
        assert "99989" in results[0].summary


# ---------------------------------------------------------------------------
# Check — happy path
# ---------------------------------------------------------------------------

class TestCheckSansayVsxTrunks:
    def _check(self, trunk_id, alias, params=None):
        return list(check_sansay_vsx_trunks(
            item=f"{trunk_id} {alias}",
            params=params or DEFAULT_PARAMS,
            section=SECTION,
        ))

    def test_first_result_is_ok(self):
        results = self._check("100", "Carrier In")
        assert any(isinstance(r, Result) and r.state == State.OK for r in results)

    def test_metrics_emitted_for_all_directions(self):
        results = self._check("100", "Carrier In")
        metric_names = {r.name for r in results if isinstance(r, Metric)}
        assert "ingress_failed_call_ratio" in metric_names
        assert "egress_answer_seize_ratio" in metric_names
        assert "realtime_origination_utilization" in metric_names
        assert "realtime_termination_sessions" in metric_names

    def test_idle_trunk_emits_ok(self):
        results = self._check("200", "Customer Out")
        assert any(isinstance(r, Result) and r.state == State.OK for r in results)


# ---------------------------------------------------------------------------
# Check — threshold alerting
# ---------------------------------------------------------------------------

class TestCheckThresholds:
    def _params_with_levels(self, direction, metric, warn, crit):
        params = {k: {**v} for k, v in DEFAULT_PARAMS.items()}
        params[direction][f"{metric}_levels"] = ("fixed", (warn, crit))
        return params

    def test_failed_call_ratio_warn(self):
        # ingress failed_call_ratio is 10.0; warn at 5.0
        params = self._params_with_levels("ingress", "failed_call_ratio", 5.0, 20.0)
        results = list(check_sansay_vsx_trunks(
            item="100 Carrier In", params=params, section=SECTION
        ))
        states = [r.state for r in results if isinstance(r, Result)]
        assert State.WARN in states
        assert State.CRIT not in states

    def test_failed_call_ratio_crit(self):
        # ingress failed_call_ratio is 10.0; crit at 8.0
        params = self._params_with_levels("ingress", "failed_call_ratio", 5.0, 8.0)
        results = list(check_sansay_vsx_trunks(
            item="100 Carrier In", params=params, section=SECTION
        ))
        states = [r.state for r in results if isinstance(r, Result)]
        assert State.CRIT in states

    def test_answer_seize_ratio_lower_bound_ok(self):
        # egress answer_seize_ratio is 100.0; lower warn at 70.0 — no alert expected
        params = self._params_with_levels("egress", "answer_seize_ratio", 70.0, 50.0)
        results = list(check_sansay_vsx_trunks(
            item="100 Carrier In", params=params, section=SECTION
        ))
        alert_states = [r.state for r in results if isinstance(r, Result) and r.state != State.OK]
        assert not alert_states

    def test_realtime_utilization_warn(self):
        # realtime origination_utilization is 3.0; warn at 2.0
        params = self._params_with_levels("realtime", "origination_utilization", 2.0, 5.0)
        results = list(check_sansay_vsx_trunks(
            item="100 Carrier In", params=params, section=SECTION
        ))
        states = [r.state for r in results if isinstance(r, Result)]
        assert State.WARN in states
