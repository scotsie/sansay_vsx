#!/usr/bin/env python3
"""
Tests for agent processing functions in agent_sansay_vsx.py.

Covers both happy paths and the specific failure modes observed in crash reports:
  - KeyError('trunks') when resource endpoint returns None (crash 2026-03-25)
  - Non-dict table entries ('Max recursion depth reached') from HA failover events
  - Duplicate calculated_stats keys (ingress/ingress_stat, egress/gw_egress_stat)
"""

import pytest
from unittest.mock import MagicMock, patch

from cmk_addons.plugins.sansay_vsx.special_agents.agent_sansay_vsx import (
    process_media_stats,
    process_realtime_data,
    process_realtime_trunk_data,
    process_resource_data,
    process_system_stats,
    process_trunk_stats,
    poll_sansay_vsx,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_args(**overrides):
    args = MagicMock()
    args.debug = False
    args.host = "10.0.0.1"
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


def _field(name, content):
    return {"name": name, "content": content}


def _trunk_row(trunk_id, alias, recid, pdd=3000, attempts=10, duration=500, fails=1, answers=9):
    return {
        "field": [
            _field("id", str(recid)),
            _field("trunk_id", str(trunk_id)),
            _field("alias", alias),
            _field("1st15mins_pdd_ms", str(pdd)),
            _field("1st15mins_call_attempt", str(attempts)),
            _field("1st15mins_call_durationSec", str(duration)),
            _field("1st15mins_call_fail", str(fails)),
            _field("1st15mins_call_answer", str(answers)),
        ]
    }


RESOURCE_DATA = {
    "mysqldump": {
        "database": {
            "table": [
                {
                    "name": "ingress_stat",
                    "row": [_trunk_row("100", "Carrier In", 1, attempts=10, fails=1, answers=9)],
                },
                {
                    "name": "gw_egress_stat",
                    "row": [_trunk_row("100", "Carrier In", 1, pdd=2000, attempts=8, duration=400, fails=0, answers=8)],
                },
            ]
        }
    }
}

REALTIME_DATA = {
    "mysqldump": {
        "database": {
            "table": [
                {
                    "name": "system_stat",
                    "row": {
                        "field": [
                            _field("cpu_idle_percent", 95),
                            _field("sum_active_session", 10),
                            _field("max_session_allowed", 1000),
                            _field("cluster_active_session", 10),
                            _field("ha_current_state", "active"),
                        ]
                    },
                },
                {
                    "name": "XBResourceRealTimeStatList",
                    "row": [
                        {
                            "field": [
                                _field("trunkId", "100"),
                                _field("fqdn", "carrier.example.com"),
                                _field("numOrig", "3"),
                                _field("numTerm", "5"),
                                _field("cps", "1"),
                                _field("numPeak", "8"),
                                _field("totalCLZ", "0"),
                                _field("numCLZCps", "0"),
                                _field("totalLimit", "100"),
                                _field("cpsLimit", "10"),
                            ]
                        },
                        # Group-type entries should be filtered out
                        {
                            "field": [
                                _field("trunkId", "GROUP-1"),
                                _field("fqdn", "Group"),
                                _field("numOrig", "3"),
                                _field("numTerm", "5"),
                                _field("cps", "0"),
                                _field("numPeak", "0"),
                                _field("totalCLZ", "0"),
                                _field("numCLZCps", "0"),
                                _field("totalLimit", "0"),
                                _field("cpsLimit", "0"),
                            ]
                        },
                    ],
                },
            ]
        }
    }
}


# ---------------------------------------------------------------------------
# process_resource_data
# ---------------------------------------------------------------------------

class TestProcessResourceData:
    def test_returns_trunks_dict(self):
        result = process_resource_data(make_args(), RESOURCE_DATA)
        assert isinstance(result, dict)
        assert "100" in result

    def test_trunk_has_alias_and_recid(self):
        result = process_resource_data(make_args(), RESOURCE_DATA)
        assert result["100"]["alias"] == "Carrier In"
        assert result["100"]["recid"] == "1"

    def test_trunk_has_both_direction_tables(self):
        result = process_resource_data(make_args(), RESOURCE_DATA)
        assert "ingress_stat" in result["100"]
        assert "gw_egress_stat" in result["100"]

    def test_returns_none_for_none_input(self):
        assert process_resource_data(make_args(), None) is None

    def test_skips_non_dict_table_entries(self):
        """Regression: HA failover can return 'Max recursion depth reached' strings."""
        malformed = {
            "mysqldump": {
                "database": {
                    "table": [
                        "Max recursion depth reached",
                        "Max recursion depth reached",
                        {
                            "name": "ingress_stat",
                            "row": [_trunk_row("200", "Good Trunk", 5)],
                        },
                    ]
                }
            }
        }
        result = process_resource_data(make_args(), malformed)
        assert "200" in result

    def test_all_string_tables_returns_empty_trunks(self):
        """When all table entries are error strings, no trunks parsed."""
        malformed = {
            "mysqldump": {
                "database": {
                    "table": [
                        "Max recursion depth reached",
                        "Max recursion depth reached",
                    ]
                }
            }
        }
        result = process_resource_data(make_args(), malformed)
        assert result == {}


# ---------------------------------------------------------------------------
# process_realtime_data
# ---------------------------------------------------------------------------

class TestProcessRealtimeData:
    def test_returns_system_stat_and_trunk_data(self):
        system_stat, trunk_data = process_realtime_data(make_args(), REALTIME_DATA)
        assert "system_stat" in system_stat
        assert "100" in trunk_data

    def test_group_fqdn_entries_are_filtered(self):
        _, trunk_data = process_realtime_data(make_args(), REALTIME_DATA)
        assert "GROUP-1" not in trunk_data
        for data in trunk_data.values():
            assert data.get("fqdn") != "Group"

    def test_system_stat_fields_present(self):
        system_stat, _ = process_realtime_data(make_args(), REALTIME_DATA)
        assert system_stat["system_stat"]["cpu_idle_percent"] == 95
        assert system_stat["system_stat"]["ha_current_state"] == "active"

    def test_skips_non_dict_table_entries(self):
        """Regression: HA failover returns error strings as table entries."""
        malformed = {
            "mysqldump": {
                "database": {
                    "table": [
                        "Max recursion depth reached",
                        "Max recursion depth reached",
                        "Max recursion depth reached",
                    ]
                }
            }
        }
        system_stat, trunk_data = process_realtime_data(make_args(), malformed)
        assert system_stat == {}
        assert trunk_data == {}

    def test_empty_realtime_trunk_list(self):
        """XBResourceRealTimeStatList with no rows (no active calls)."""
        data = {
            "mysqldump": {
                "database": {
                    "table": [
                        {
                            "name": "system_stat",
                            "row": {
                                "field": [_field("cpu_idle_percent", 99)]
                            },
                        },
                        {
                            "name": "XBResourceRealTimeStatList",
                            "row": [],
                        },
                    ]
                }
            }
        }
        system_stat, trunk_data = process_realtime_data(make_args(), data)
        assert trunk_data == {}


# ---------------------------------------------------------------------------
# process_realtime_trunk_data
# ---------------------------------------------------------------------------

class TestProcessRealtimeTrunkData:
    def _base_trunks(self):
        return {
            "100": {"alias": "Active Trunk", "recid": "1"},
            "200": {"alias": "Idle Trunk", "recid": "2"},
        }

    def test_active_trunk_gets_realtime_values(self):
        realtime = {
            "100": {
                "numOrig": "5", "numTerm": "10", "cps": "2",
                "numPeak": "15", "totalCLZ": "0", "numCLZCps": "0",
                "totalLimit": "100", "cpsLimit": "10",
            }
        }
        result = process_realtime_trunk_data(self._base_trunks(), realtime)
        assert result["100"]["realtime_stat"]["numOrig"] == "5"
        assert result["100"]["realtime_stat"]["numTerm"] == "10"
        assert result["100"]["realtime_stat"]["totalLimit"] == "100"

    def test_idle_trunk_defaults_to_zero(self):
        result = process_realtime_trunk_data(self._base_trunks(), {})
        assert result["200"]["realtime_stat"]["numOrig"] == 0
        assert result["200"]["realtime_stat"]["numTerm"] == 0
        assert result["200"]["realtime_stat"]["totalLimit"] == 0

    def test_all_trunks_get_realtime_stat_key(self):
        result = process_realtime_trunk_data(self._base_trunks(), {})
        for trunk_id in ["100", "200"]:
            assert "realtime_stat" in result[trunk_id]


# ---------------------------------------------------------------------------
# process_trunk_stats
# ---------------------------------------------------------------------------

class TestProcessTrunkStats:
    def _stats_with_tables(self, ingress_table, egress_table):
        """Build a stats dict with the given raw table names, simulating agent output."""
        trunks = {
            "100": {
                "alias": "Test Trunk",
                "recid": "1",
                ingress_table: {
                    "1st15mins_pdd_ms": "3000",
                    "1st15mins_call_attempt": "10",
                    "1st15mins_call_durationSec": "500",
                    "1st15mins_call_fail": "1",
                    "1st15mins_call_answer": "9",
                },
                egress_table: {
                    "1st15mins_pdd_ms": "2000",
                    "1st15mins_call_attempt": "8",
                    "1st15mins_call_durationSec": "400",
                    "1st15mins_call_fail": "0",
                    "1st15mins_call_answer": "8",
                },
                "realtime_stat": {
                    "numOrig": "3", "numTerm": "5", "cps": "1",
                    "numPeak": "8", "totalCLZ": "0", "numCLZCps": "0",
                    "totalLimit": "100", "cpsLimit": "10",
                },
            }
        }
        return {"trunks": trunks}

    def test_ingress_stat_normalized_to_ingress(self):
        """Regression: ingress_stat must map to 'ingress' key, not remain as 'ingress_stat'."""
        stats = self._stats_with_tables("ingress_stat", "gw_egress_stat")
        result = process_trunk_stats(make_args(), stats)
        assert "ingress" in result["100"]["calculated_stats"]
        assert "ingress_stat" not in result["100"]["calculated_stats"]

    def test_gw_egress_stat_normalized_to_egress(self):
        """Regression: gw_egress_stat must map to 'egress' key, not remain as 'gw_egress_stat'."""
        stats = self._stats_with_tables("ingress_stat", "gw_egress_stat")
        result = process_trunk_stats(make_args(), stats)
        assert "egress" in result["100"]["calculated_stats"]
        assert "gw_egress_stat" not in result["100"]["calculated_stats"]

    def test_no_duplicate_direction_keys(self):
        """Regression: must not have both 'ingress'+'ingress_stat' or 'egress'+'gw_egress_stat'."""
        stats = self._stats_with_tables("ingress_stat", "gw_egress_stat")
        result = process_trunk_stats(make_args(), stats)
        calc = result["100"]["calculated_stats"]
        assert len([k for k in calc if "ingress" in k]) == 1
        assert len([k for k in calc if "egress" in k]) == 1

    def test_calculated_metrics_are_numeric(self):
        stats = self._stats_with_tables("ingress_stat", "gw_egress_stat")
        result = process_trunk_stats(make_args(), stats)
        ingress = result["100"]["calculated_stats"]["ingress"]
        for metric_val in ingress.values():
            assert isinstance(metric_val, float)

    def test_zero_call_attempts_produces_default_zeros(self):
        """When CA == 0, calculated_stats direction should use default zeroed values."""
        trunks = {
            "100": {
                "alias": "Idle Trunk",
                "recid": "1",
                "ingress_stat": {
                    "1st15mins_pdd_ms": "0",
                    "1st15mins_call_attempt": "0",
                    "1st15mins_call_durationSec": "0",
                    "1st15mins_call_fail": "0",
                    "1st15mins_call_answer": "0",
                },
                "gw_egress_stat": {
                    "1st15mins_pdd_ms": "0",
                    "1st15mins_call_attempt": "0",
                    "1st15mins_call_durationSec": "0",
                    "1st15mins_call_fail": "0",
                    "1st15mins_call_answer": "0",
                },
                "realtime_stat": {
                    "numOrig": "0", "numTerm": "0", "cps": "0",
                    "numPeak": "0", "totalCLZ": "0", "numCLZCps": "0",
                    "totalLimit": "0", "cpsLimit": "0",
                },
            }
        }
        result = process_trunk_stats(make_args(), {"trunks": trunks})
        assert result["100"]["calculated_stats"]["ingress"]["avg_postdial_delay"] == 0

    def test_realtime_utilization_calculated(self):
        stats = self._stats_with_tables("ingress_stat", "gw_egress_stat")
        result = process_trunk_stats(make_args(), stats)
        realtime = result["100"]["calculated_stats"]["realtime"]
        assert realtime["origination_sessions"] == 3
        assert realtime["termination_sessions"] == 5
        # 3/100 * 100 = 3.0%
        assert realtime["origination_utilization"] == pytest.approx(3.0)

    def test_returns_none_when_no_trunks_key(self):
        result = process_trunk_stats(make_args(), {})
        assert result is None


# ---------------------------------------------------------------------------
# poll_sansay_vsx — integration of fetch + processing
# ---------------------------------------------------------------------------

class TestPollSansayVsx:
    def test_no_crash_when_resource_returns_none(self):
        """
        Regression: when resource endpoint fails, stats['trunks'] is never set.
        Accessing it for realtime update must not raise KeyError.
        """
        args = make_args()
        with patch(
            "cmk_addons.plugins.sansay_vsx.special_agents.agent_sansay_vsx.fetch_sansay_json"
        ) as mock_fetch:
            mock_fetch.side_effect = [None, REALTIME_DATA, None]
            result = poll_sansay_vsx(args)
        assert "trunks" not in result
        assert "system_stat" in result

    def test_trunks_populated_when_resource_succeeds(self):
        args = make_args()
        with patch(
            "cmk_addons.plugins.sansay_vsx.special_agents.agent_sansay_vsx.fetch_sansay_json"
        ) as mock_fetch:
            mock_fetch.side_effect = [RESOURCE_DATA, REALTIME_DATA, None]
            result = poll_sansay_vsx(args)
        assert "trunks" in result
        assert "100" in result["trunks"]

    def test_all_endpoints_fail_returns_empty_stats(self):
        args = make_args()
        with patch(
            "cmk_addons.plugins.sansay_vsx.special_agents.agent_sansay_vsx.fetch_sansay_json"
        ) as mock_fetch:
            mock_fetch.return_value = None
            result = poll_sansay_vsx(args)
        assert result == {}
