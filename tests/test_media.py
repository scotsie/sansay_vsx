#!/usr/bin/env python3
"""
Tests for the sansay_vsx_media check plugin.

Covers:
  - discovery yields one service per media server alias
  - empty section yields UNKNOWN
  - media server not found in section yields UNKNOWN
  - duplicate alias yields UNKNOWN
  - normal up media server yields OK with session metrics
  - down media server yields CRIT
  - session utilization threshold alerting
"""

from cmk.agent_based.v2 import Metric, Result, State

from cmk_addons.plugins.sansay_vsx.agent_based.sansay_vsx_media_stats import (
    check_sansay_vsx_media,
    cluster_check_sansay_vsx_media,
    discovery_sansay_vsx_media,
)


DEFAULT_PARAMS = {
    "session_levels": ("fixed", (80.0, 90.0)),
}

SECTION = [
    {
        "mediaSrvIndex": 1,
        "alias": "Internal Media Switching",
        "switchType": "Internal Media Switching",
        "numActiveSessions": 0,
        "publicIP": "10.0.0.1",
        "priority": 2,
        "maxConnections": 3000,
        "status": "up",
    },
    {
        "mediaSrvIndex": 2,
        "alias": "MST3 HA Pair",
        "switchType": "External Advanced Hybrid-Media Switching",
        "numActiveSessions": 4,
        "publicIP": "10.0.0.2",
        "priority": 0,
        "maxConnections": 8000,
        "status": "up",
    },
    {
        "mediaSrvIndex": 3,
        "alias": "MLT transcoder",
        "switchType": "Advanced Hybrid-MLT",
        "numActiveSessions": 0,
        "publicIP": "10.0.0.3",
        "priority": 0,
        "maxConnections": 2000,
        "status": "down",
    },
]


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class TestDiscoverySansayVsxMedia:
    def test_discovers_all_media_servers(self):
        services = list(discovery_sansay_vsx_media(SECTION))
        assert len(services) == 3

    def test_service_items_are_aliases(self):
        items = {s.item for s in discovery_sansay_vsx_media(SECTION)}
        assert "Internal Media Switching" in items
        assert "MST3 HA Pair" in items
        assert "MLT transcoder" in items

    def test_empty_section_yields_no_services(self):
        assert list(discovery_sansay_vsx_media([])) == []

    def test_skips_entries_with_no_alias(self):
        """Regression: a media entry missing 'alias' (raw vendor passthrough,
        unlike trunks) must not crash discovery."""
        section = [
            {"mediaSrvIndex": 99, "status": "up"},  # no alias key
            SECTION[0],
        ]
        services = list(discovery_sansay_vsx_media(section))
        assert len(services) == 1
        assert services[0].item == "Internal Media Switching"


# ---------------------------------------------------------------------------
# Check — edge cases
# ---------------------------------------------------------------------------

class TestCheckEdgeCases:
    def test_unknown_on_empty_section(self):
        results = list(check_sansay_vsx_media(
            item="Internal Media Switching", params=DEFAULT_PARAMS, section=[]
        ))
        assert results[0].state == State.UNKNOWN

    def test_unknown_when_alias_not_found(self):
        results = list(check_sansay_vsx_media(
            item="Nonexistent Server", params=DEFAULT_PARAMS, section=SECTION
        ))
        assert results[0].state == State.UNKNOWN
        assert "Nonexistent Server" in results[0].summary

    def test_unknown_on_duplicate_aliases(self):
        dup_section = [
            {**SECTION[0], "mediaSrvIndex": 1},
            {**SECTION[0], "mediaSrvIndex": 99},
        ]
        results = list(check_sansay_vsx_media(
            item="Internal Media Switching", params=DEFAULT_PARAMS, section=dup_section
        ))
        assert results[0].state == State.UNKNOWN
        assert "Multiple" in results[0].summary


# ---------------------------------------------------------------------------
# Check — happy path (up server)
# ---------------------------------------------------------------------------

class TestCheckMediaUp:
    def _check(self, alias, params=None):
        return list(check_sansay_vsx_media(
            item=alias, params=params or DEFAULT_PARAMS, section=SECTION
        ))

    def test_up_server_yields_ok_result(self):
        results = self._check("Internal Media Switching")
        ok_results = [r for r in results if isinstance(r, Result) and r.state == State.OK]
        assert ok_results

    def test_summary_includes_ip(self):
        results = self._check("Internal Media Switching")
        ok_result = next(r for r in results if isinstance(r, Result) and r.state == State.OK)
        assert "10.0.0.1" in ok_result.summary

    def test_active_sessions_metric_emitted(self):
        results = self._check("MST3 HA Pair")
        metrics = {r.name: r.value for r in results if isinstance(r, Metric)}
        assert "num_active_sessions" in metrics
        assert metrics["num_active_sessions"] == 4

    def test_session_utilization_result_emitted(self):
        results = self._check("MST3 HA Pair")
        util_results = [r for r in results if isinstance(r, Result) and "utilization" in r.summary.lower()]
        assert util_results


# ---------------------------------------------------------------------------
# Check — down server
# ---------------------------------------------------------------------------

class TestCheckMediaDown:
    def test_down_server_yields_crit(self):
        results = list(check_sansay_vsx_media(
            item="MLT transcoder", params=DEFAULT_PARAMS, section=SECTION
        ))
        crit_results = [r for r in results if isinstance(r, Result) and r.state == State.CRIT]
        assert crit_results

    def test_down_summary_mentions_not_up(self):
        results = list(check_sansay_vsx_media(
            item="MLT transcoder", params=DEFAULT_PARAMS, section=SECTION
        ))
        crit_result = next(r for r in results if isinstance(r, Result) and r.state == State.CRIT)
        assert "not" in crit_result.summary.lower() or "up" in crit_result.summary.lower()


# ---------------------------------------------------------------------------
# Check — missing fields (raw vendor passthrough, not all fields guaranteed)
# ---------------------------------------------------------------------------

class TestCheckMissingFields:
    def _section_missing(self, *keys):
        entry = {**SECTION[0]}
        for key in keys:
            entry.pop(key, None)
        return [entry]

    def test_missing_public_ip_does_not_crash(self):
        section = self._section_missing("publicIP")
        results = list(check_sansay_vsx_media(
            item="Internal Media Switching", params=DEFAULT_PARAMS, section=section
        ))
        assert any(isinstance(r, Result) and r.state == State.OK for r in results)

    def test_missing_status_does_not_crash_and_is_treated_as_down(self):
        """
        Regression: a matched entry missing 'status' must not crash. Treating
        it as not 'up' (rather than assuming healthy) is the safe default.
        """
        section = self._section_missing("status")
        results = list(check_sansay_vsx_media(
            item="Internal Media Switching", params=DEFAULT_PARAMS, section=section
        ))
        crit_results = [r for r in results if isinstance(r, Result) and r.state == State.CRIT]
        assert crit_results

    def test_missing_num_active_sessions_defaults_to_zero(self):
        section = self._section_missing("numActiveSessions")
        results = list(check_sansay_vsx_media(
            item="Internal Media Switching", params=DEFAULT_PARAMS, section=section
        ))
        metrics = {r.name: r.value for r in results if isinstance(r, Metric)}
        assert metrics["num_active_sessions"] == 0

    def test_missing_max_connections_does_not_crash(self):
        section = self._section_missing("maxConnections")
        results = list(check_sansay_vsx_media(
            item="Internal Media Switching", params=DEFAULT_PARAMS, section=section
        ))
        assert any(isinstance(r, Result) for r in results)

    def test_multiple_match_missing_media_srv_index_does_not_crash(self):
        """Regression: the 'multiple matches' error detail indexes mediaSrvIndex
        on every match, which isn't guaranteed to be present."""
        dup_section = [
            {**SECTION[0], "mediaSrvIndex": 1},
            self._section_missing("mediaSrvIndex")[0],
        ]
        results = list(check_sansay_vsx_media(
            item="Internal Media Switching", params=DEFAULT_PARAMS, section=dup_section
        ))
        assert results[0].state == State.UNKNOWN


# ---------------------------------------------------------------------------
# Check — session utilization thresholds
# ---------------------------------------------------------------------------

class TestCheckMediaSessionThresholds:
    def _section_with_sessions(self, active, maximum):
        return [{
            "mediaSrvIndex": 1,
            "alias": "Test Server",
            "switchType": "Internal",
            "numActiveSessions": active,
            "publicIP": "10.0.0.1",
            "priority": 0,
            "maxConnections": maximum,
            "status": "up",
        }]

    def test_session_utilization_ok(self):
        section = self._section_with_sessions(100, 1000)   # 10%
        results = list(check_sansay_vsx_media(
            item="Test Server", params=DEFAULT_PARAMS, section=section
        ))
        util_results = [r for r in results if isinstance(r, Result) and "utilization" in r.summary.lower()]
        assert util_results[0].state == State.OK

    def test_session_utilization_warn(self):
        section = self._section_with_sessions(850, 1000)   # 85%
        results = list(check_sansay_vsx_media(
            item="Test Server", params=DEFAULT_PARAMS, section=section
        ))
        util_results = [r for r in results if isinstance(r, Result) and "utilization" in r.summary.lower()]
        assert util_results[0].state == State.WARN

    def test_session_utilization_crit(self):
        section = self._section_with_sessions(950, 1000)   # 95%
        results = list(check_sansay_vsx_media(
            item="Test Server", params=DEFAULT_PARAMS, section=section
        ))
        util_results = [r for r in results if isinstance(r, Result) and "utilization" in r.summary.lower()]
        assert util_results[0].state == State.CRIT

    def test_zero_max_connections_no_crash(self):
        """When maxConnections is 0, utilization calculation is skipped."""
        section = self._section_with_sessions(0, 0)
        results = list(check_sansay_vsx_media(
            item="Test Server", params=DEFAULT_PARAMS, section=section
        ))
        assert any(isinstance(r, Result) for r in results)


# ---------------------------------------------------------------------------
# Cluster check
# ---------------------------------------------------------------------------

class TestClusterCheckSansayVsxMedia:
    SECTION_WITH_DATA = {"phl-sansay-01": SECTION, "phl-sansay-02": []}

    def test_active_node_data_used(self):
        results = list(cluster_check_sansay_vsx_media(
            item="MST3 HA Pair", params=DEFAULT_PARAMS, section=self.SECTION_WITH_DATA,
        ))
        assert any(isinstance(r, Result) and r.state == State.OK for r in results)

    def test_active_node_name_in_result_summary(self):
        results = list(cluster_check_sansay_vsx_media(
            item="MST3 HA Pair", params=DEFAULT_PARAMS, section=self.SECTION_WITH_DATA,
        ))
        summaries = [r.summary for r in results if isinstance(r, Result)]
        assert any("phl-sansay-01" in s for s in summaries)

    def test_metrics_still_yielded(self):
        results = list(cluster_check_sansay_vsx_media(
            item="MST3 HA Pair", params=DEFAULT_PARAMS, section=self.SECTION_WITH_DATA,
        ))
        metric_names = {r.name for r in results if isinstance(r, Metric)}
        assert "num_active_sessions" in metric_names

    def test_both_nodes_empty_yields_unknown(self):
        results = list(cluster_check_sansay_vsx_media(
            item="MST3 HA Pair",
            params=DEFAULT_PARAMS,
            section={"phl-sansay-01": [], "phl-sansay-02": []},
        ))
        assert len(results) == 1
        assert results[0].state == State.UNKNOWN

    def test_none_node_falls_through_to_active(self):
        """Agent unreachable on one node (None) — other node provides data."""
        section = {"phl-sansay-01": None, "phl-sansay-02": SECTION}
        results = list(cluster_check_sansay_vsx_media(
            item="MST3 HA Pair", params=DEFAULT_PARAMS, section=section,
        ))
        assert any(isinstance(r, Result) and r.state == State.OK for r in results)
