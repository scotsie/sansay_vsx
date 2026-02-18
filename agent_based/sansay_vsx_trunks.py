#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2


import time
import json
from collections.abc import Mapping
from typing import Any

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    get_value_store,
    Result,
    Service,
    State,
    StringTable,
)
from cmk.plugins.lib.cpu_util import check_cpu_util
from cmk.plugins.netapp import models

from cmk.agent_based.v2 import (
    Metric,
    check_levels,
)

from cmk_addons.plugins.sansay_vsx.lib import (
    parse_sansay_vsx,
    SansayVSXAPIData
)


Section = Mapping[str, models.NodeModel]

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


agent_section_sansay_vsx_cpu = AgentSection(
    name="sansay_vsx_trunks",
    parse_function=parse_sansay_vsx,
    parsed_section_name="sansay_vsx_trunks",
)


def discovery_sansay_vsx_trunks(section: Section) -> DiscoveryResult:
    # print(f"discover trunks {section=}\n{type(section)}")
    for trunk_id, trunk_data in section.items():
        yield Service(item=f"{trunk_id} {trunk_data["alias"]}")


def check_sansay_vsx_trunks(item, section: Section) -> CheckResult:
    trunk_id = item.split()[0]
    # print(f"{trunk_id=}")
    trunk_data = section[trunk_id]
    # print(f"{trunk_data=}")
    yield Result(
        state=State.OK,
        summary=f"Trunk {trunk_id} {trunk_data["alias"]}",
        details = f"record id {trunk_data["recid"]}"
    )
    
    if "calculated_stats" in trunk_data.keys():
        # print(trunk_data["calculated_stats"])
        for direction, stats in trunk_data["calculated_stats"].items():
            for metric, value in stats.items():
                yield Metric(name=f"{direction}_{metric}", value=value)


check_plugin_sansay_vsx_trunks = CheckPlugin(
    name="sansay_vsx_trunks",
    service_name="VSX trunk %s",
    discovery_function=discovery_sansay_vsx_trunks,
    sections=["sansay_vsx_trunks"],
    check_function=check_sansay_vsx_trunks,
)
