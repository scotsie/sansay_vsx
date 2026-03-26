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
