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
<<<sansay_vsx_system:sep(0)>>>
{"cluster_active_session": 0,"cluster_peak_session": 23,"cpu_idle_percent": 98,"current_cps": 0,
"demo_lic": -1,"flow_control_lev": 0,"ha_current_state": "active","ha_local_status": 0,"ha_pre_state": "standby",
"ha_remote_status": 0,"id": 1,"inbound_h323_leg": 0,"inbound_sip_leg": 0,"max_cps_allowed": 10000,
"max_cps_exceed": 0,"max_session_allowed": 19750,"max_session_exceed": 0,"outbound_h323_leg": 0,
"outbound_sip_leg": 0,"peak_active_session": 23,"peak_h323_leg": 0,"peak_sip_leg": 46,"slave_stat": 64,
"sum_active_session": 0,"sum_attempt_session": 27412,"switch_over_flag": 3}

section comes in as a list within a list containing the dictionary as a string.
Parser 'parse_sansay_vsx' is in sansay_vsx.lib. It filters out the string and performs a json.load.
[['{values above}']]
"""


agent_section_sansay_vsx_cpu = AgentSection(
    name="sansay_vsx_system",
    parse_function=parse_sansay_vsx,
    parsed_section_name="sansay_vsx_cpu",
)


def discovery_sansay_vsx_cpu(section: Section) -> DiscoveryResult:
    if "cpu_idle_percent" in section.keys():
        yield Service()
    else:
        return


def check_sansay_vsx_cpu(section: Section) -> CheckResult:
    # Static placeholders until I figure out how to incorporate thresholding into the UI
    # if (data := section.get(item)) is None:
    #     return
    
    #check_cpu_util(
    #    util=data.cpu_utilization(),
    #    params=params,
    #    value_store=get_value_store(),
    #    this_time=time.time(),
    #)
    cpu_upper_crit = 90
    cpu_upper_warn = .1
    session_upper_crit = 90
    session_upper_warn = 80
    cpu_utilization = 100.0 - section["cpu_idle_percent"]
    cpu_summary = f"CPU at {cpu_utilization}%."
    state = 0
    if cpu_utilization >= cpu_upper_warn:
        state = 1
    if cpu_utilization >= cpu_upper_crit:
        state = 2

    yield Result(
        state=State(state),
        summary=cpu_summary
    )

#    yield from check_levels(
#        cpu_utilization,
#        levels_lower= cpu_upper_warn,
#        levels_upper= cpu_upper_crit,
#        metric_name= "cpu_utilization",
#        label= "CPU Utilization",
#        boundaries= (0.0, 100.0),
#        notice_only= True
#    )
    session_utilization = None
    if section["max_session_allowed"]:
        session_utilization = round((section["sum_active_session"] / section["max_session_allowed"]) * 100, 1)
        if session_utilization >= session_upper_warn:
            state = 1
        if session_utilization >= session_upper_crit:
            state = 2
        session_summary = f"Session Utilization at {session_utilization}%."
        yield Result(
            state=State(state),
            summary=session_summary
        )

    
#    yield from check_levels(
#        session_utilization,
#        levels_lower= session_upper_warn,
#        levels_upper= session_upper_crit,
#        metric_name= "session_utilization",
#        label= "Session Utilization",
#        boundaries= (0.0, 100.0),
#        notice_only= True      
#    )
    
    # content += f"CPU utilization {cpu_utilization}\n"
    # content += f"Session utilization {session_utilization}"

    yield Metric(name="cpu_utilization", value=cpu_utilization, boundaries=(0, 100))
    #yield Metric(name="session_utilization", value=session_utilization, boundaries=(0, 100))


check_plugin_sansay_vsx_cpu = CheckPlugin(
    name="sansay_vsx_cpu",
    service_name="VSX CPU",
    discovery_function=discovery_sansay_vsx_cpu,
    sections=["sansay_vsx_cpu"],
    check_function=check_sansay_vsx_cpu,
    #check_ruleset_name="cpu_utilization_multiitem",
    #check_default_parameters={"levels": (90.0, 95.0)},
)
