#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2


from collections.abc import Mapping
from typing import Any

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
)

from cmk_addons.plugins.sansay_vsx.lib import parse_sansay_vsx


Section = Mapping[str, Any]

# Special Agent Output to Parse for this service
"""
<<<sansay_vsx_trunks:sep(0)>>>
{
    "1": {
        "alias": "ClusterID VSXs",
        "calculated_stats": {
            "egress": {"answer_seize_ratio": 0, "avg_call_duration": 0, "avg_postdial_delay": 0, "failed_call_ratio": 0},
            "gw_egress_stat": {"answer_seize_ratio": 100.0, "avg_call_duration": 275.0, "avg_postdial_delay": 2.3, "failed_call_ratio": 0.0},
            "ingress": {"answer_seize_ratio": 0, "avg_call_duration": 0, "avg_postdial_delay": 0, "failed_call_ratio": 0},
            "realtime": {"origination_sessions": 1, "origination_utilization": 0.1, "termination_sessions": 3, "termination_utilization": 0.1}
        },
      "recid": 1
    },
    "2000": {
        "alias": "Customer Out",
        "calculated_stats": {
            "egress": {"answer_seize_ratio": 0, "avg_call_duration": 0, "avg_postdial_delay": 0, "failed_call_ratio": 0},
            "ingress": {"answer_seize_ratio": 0, "avg_call_duration": 0, "avg_postdial_delay": 0, "failed_call_ratio": 0},
            "realtime": {"origination_sessions": 0, "origination_utilization": 0.0, "termination_sessions": 1, "termination_utilization": 0.1}
        },
        "recid": 3
    },
}
Section comes in as a list within a list containing the dictionary as a string.
Parser 'parse_sansay_vsx' is in sansay_vsx.lib. It filters out the string and performs a json.load.
[['{values above}']]
"""

# Maps (direction_group, metric_name) -> "upper" or "lower" bound direction.
# Metrics absent from this table are emitted as Metrics only with no alerting.
_METRIC_LEVEL_DIRECTION: dict[str, dict[str, str]] = {
    "egress": {
        "failed_call_ratio": "upper",
        "answer_seize_ratio": "lower",
        "avg_postdial_delay": "upper",
    },
    "ingress": {
        "failed_call_ratio": "upper",
        "answer_seize_ratio": "lower",
        "avg_postdial_delay": "upper",
    },
    "gw_egress_stat": {
        "failed_call_ratio": "upper",
        "answer_seize_ratio": "lower",
        "avg_postdial_delay": "upper",
    },
    "realtime": {
        "origination_utilization": "upper",
        "termination_utilization": "upper",
    },
}


agent_section_sansay_vsx_cpu = AgentSection(
    name="sansay_vsx_trunks",
    parse_function=parse_sansay_vsx,
    parsed_section_name="sansay_vsx_trunks",
)


def discovery_sansay_vsx_trunks(section: Section) -> DiscoveryResult:
    for trunk_id, trunk_data in section.items():
        yield Service(item=f"{trunk_id} {trunk_data['alias']}")


def check_sansay_vsx_trunks(item, section: Section, params) -> CheckResult:
    trunk_id = item.split()[0]
    trunk_data = section[trunk_id]
    yield Result(
        state=State.OK,
        summary=f"Trunk {trunk_id} {trunk_data['alias']}",
        details=f"record id {trunk_data['recid']}",
    )

    if "calculated_stats" not in trunk_data:
        return

    for direction, stats in trunk_data["calculated_stats"].items():
        direction_params = params.get(direction, {})
        direction_level_config = _METRIC_LEVEL_DIRECTION.get(direction, {})

        for metric, value in stats.items():
            yield Metric(name=f"{direction}_{metric}", value=value)

            bound = direction_level_config.get(metric)
            if bound is None:
                continue

            level_spec = direction_params.get(f"{metric}_levels", ("no_levels", None))
            if level_spec[0] == "no_levels":
                continue

            warn, crit = level_spec[1]
            if bound == "upper":
                state = 0
                if value >= warn:
                    state = 1
                if value >= crit:
                    state = 2
            else:  # lower
                state = 0
                if value <= warn:
                    state = 1
                if value <= crit:
                    state = 2

            if state > 0:
                label = metric.replace("_", " ").title()
                yield Result(
                    state=State(state),
                    summary=f"{direction.replace('_', ' ').title()} {label}: {value}",
                )


check_plugin_sansay_vsx_trunks = CheckPlugin(
    name="sansay_vsx_trunks",
    service_name="VSX trunk %s",
    discovery_function=discovery_sansay_vsx_trunks,
    sections=["sansay_vsx_trunks"],
    check_function=check_sansay_vsx_trunks,
    check_ruleset_name="sansay_vsx_trunks",
    check_default_parameters={
        "egress": {
            "failed_call_ratio_levels": ("fixed", (5.0, 15.0)),
            "answer_seize_ratio_levels": ("fixed", (70.0, 50.0)),
            "avg_postdial_delay_levels": ("no_levels", None),
        },
        "ingress": {
            "failed_call_ratio_levels": ("fixed", (5.0, 15.0)),
            "answer_seize_ratio_levels": ("fixed", (70.0, 50.0)),
            "avg_postdial_delay_levels": ("no_levels", None),
        },
        "gw_egress_stat": {
            "failed_call_ratio_levels": ("fixed", (5.0, 15.0)),
            "answer_seize_ratio_levels": ("fixed", (70.0, 50.0)),
            "avg_postdial_delay_levels": ("no_levels", None),
        },
        "realtime": {
            "origination_utilization_levels": ("fixed", (80.0, 90.0)),
            "termination_utilization_levels": ("fixed", (80.0, 90.0)),
        },
    },
)
