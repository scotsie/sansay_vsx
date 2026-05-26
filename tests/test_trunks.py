#!/usr/bin/env python3
"""
Tests for the sansay_vsx_trunks check plugin.

Covers:
  - discovery yields one service per trunk
  - check returns OK with zero metrics when trunk is absent (failover/no-data case)
  - check returns OK with correct metrics for a healthy trunk
  - threshold alerting for egress/ingress/realtime directions
"""

import pytest  # noqa: F401 — used by pytest.approx in threshold tests

from cmk.agent_based.v2 import Metric, Result, State

from cmk_addons.plugins.sansay_vsx.agent_based.sansay_vsx_trunks import (
    check_sansay_vsx_trunks,
    cluster_check_sansay_vsx_trunks,
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
# Check — missing trunk (failover / no-data case)
# ---------------------------------------------------------------------------

class TestCheckMissingTrunk:
    def test_ok_with_no_traffic_when_trunk_absent(self):
        """
        Regression (crash 2026-02-19): trunk service exists but trunk ID is no
        longer in the agent data (e.g. post-failover before first call).
        Must yield OK with 'no call traffic' rather than UNKNOWN or KeyError.
        """
        results = list(check_sansay_vsx_trunks(
            item="99989 Transnexus Osprey",
            params=DEFAULT_PARAMS,
            section=SECTION,
        ))
        result_items = [r for r in results if isinstance(r, Result)]
        metric_items = [r for r in results if isinstance(r, Metric)]
        assert len(result_items) == 1
        assert result_items[0].state == State.OK
        assert "no call traffic" in result_items[0].summary
        metric_names = {m.name for m in metric_items}
        assert "ingress_failed_call_ratio" in metric_names
        assert "egress_avg_call_duration" in metric_names
        assert "realtime_origination_sessions" in metric_names
        assert all(m.value == 0.0 for m in metric_items)


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


# ---------------------------------------------------------------------------
# Cluster check
# ---------------------------------------------------------------------------

class TestClusterCheckSansayVsxTrunks:
    SECTION_WITH_DATA = {"phl-sansay-01": SECTION, "phl-sansay-02": {}}

    def test_active_node_data_used(self):
        results = list(cluster_check_sansay_vsx_trunks(
            item="100 Carrier In", params=DEFAULT_PARAMS, section=self.SECTION_WITH_DATA,
        ))
        assert any(isinstance(r, Result) and r.state != State.UNKNOWN for r in results)

    def test_active_node_name_in_result_summary(self):
        results = list(cluster_check_sansay_vsx_trunks(
            item="100 Carrier In", params=DEFAULT_PARAMS, section=self.SECTION_WITH_DATA,
        ))
        summaries = [r.summary for r in results if isinstance(r, Result)]
        assert any("phl-sansay-01" in s for s in summaries)

    def test_metrics_still_yielded(self):
        results = list(cluster_check_sansay_vsx_trunks(
            item="100 Carrier In", params=DEFAULT_PARAMS, section=self.SECTION_WITH_DATA,
        ))
        metric_names = {r.name for r in results if isinstance(r, Metric)}
        assert "ingress_failed_call_ratio" in metric_names

    def test_both_nodes_empty_yields_ok_with_no_traffic(self):
        results = list(cluster_check_sansay_vsx_trunks(
            item="100 Carrier In",
            params=DEFAULT_PARAMS,
            section={"phl-sansay-01": {}, "phl-sansay-02": {}},
        ))
        result_items = [r for r in results if isinstance(r, Result)]
        metric_items = [r for r in results if isinstance(r, Metric)]
        assert len(result_items) == 1
        assert result_items[0].state == State.OK
        assert "no call traffic" in result_items[0].summary
        assert len(metric_items) > 0
        assert all(m.value == 0.0 for m in metric_items)

    def test_none_node_falls_through_to_active(self):
        """Agent unreachable on one node (None) — other node provides data."""
        section = {"phl-sansay-01": None, "phl-sansay-02": SECTION}
        results = list(cluster_check_sansay_vsx_trunks(
            item="100 Carrier In", params=DEFAULT_PARAMS, section=section,
        ))
        assert any(isinstance(r, Result) and r.state != State.UNKNOWN for r in results)
