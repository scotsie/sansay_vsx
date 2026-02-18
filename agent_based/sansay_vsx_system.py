#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2


from collections.abc import Mapping

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    get_value_store,
    Metric,
    Result,
    Service,
    State,
)

from cmk_addons.plugins.sansay_vsx.lib import parse_sansay_vsx


Section = Mapping[str, object]

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
    parsed_section_name="sansay_vsx_system",
)


def discovery_sansay_vsx_system(section: Section) -> DiscoveryResult:
    if "cpu_idle_percent" in section.keys():
        yield Service()
    else:
        return


def check_sansay_vsx_system(section: Section, params) -> CheckResult:
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent - check agent connectivity")
        return
    _, (cpu_upper_warn, cpu_upper_crit) = params["cpu_levels"]
    _, (session_upper_warn, session_upper_crit) = params["session_levels"]
    _, (session_drop_warn, session_drop_crit) = params["session_drop_levels"]
    value_store = get_value_store()
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

    session_utilization = None
    if section["max_session_allowed"] and section["sum_active_session"] is not None:
        session_utilization = round((section["sum_active_session"] / section["max_session_allowed"]) * 100, 1)
        # determine state based on absolute utilization as before
        session_state = 0
        if session_utilization >= session_upper_warn:
            session_state = 1
        if session_utilization >= session_upper_crit:
            session_state = 2

        # detect drop since last interval using value_store
        prev = value_store.get("sansay_vsx.session_utilization")
        drop = None
        if prev is not None:
            drop = round(prev - session_utilization, 1)
            # if dropped by configured amounts, escalate state
            if drop >= session_drop_warn and session_state < 1:
                session_state = 1
            if drop >= session_drop_crit:
                session_state = 2

        # persist current value for next run
        value_store["sansay_vsx.session_utilization"] = session_utilization

        session_summary = f"Session Utilization at {session_utilization}%."
        if drop is not None:
            session_summary += f" Drop since last: {drop}%."

        yield Result(
            state=State(session_state),
            summary=session_summary
        )
        # also publish drop as metric (0 on first run)
        yield Metric(name="session_utilization_drop", value=(drop if drop is not None else 0.0), boundaries=(None, None))

    yield Metric(name="cpu_utilization", value=cpu_utilization, boundaries=(0, 100))
    if session_utilization is not None:
        yield Metric(name="session_utilization", value=session_utilization, boundaries=(0, 100))


check_plugin_sansay_vsx_system = CheckPlugin(
    name="sansay_vsx_system",
    service_name="VSX System",
    discovery_function=discovery_sansay_vsx_system,
    sections=["sansay_vsx_system"],
    check_function=check_sansay_vsx_system,
    check_ruleset_name="sansay_vsx_system",
    check_default_parameters={
        "cpu_levels": ("fixed", (80.0, 90.0)),
        "session_levels": ("fixed", (80.0, 90.0)),
        "session_drop_levels": ("fixed", (10.0, 20.0)),
    },
)
