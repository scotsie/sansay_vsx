#!/usr/bin/env python
# -*- encoding: utf-8; py-indent-offset: 4 -*-

"""
Example output from special agent:
<<<sansay_vsx_media:sep(0)>>>
[
    {'mediaSrvIndex': 1, 'switchType': 'Internal Media Switching', 'alias': 'Internal Media Switching', 'numActiveSessions': 0, 'publicIP': '209.55.10.4', 'priority': 2, 'maxConnections': 3000, 'status': 'up'},
    {'mediaSrvIndex': 2, 'switchType': 'External Advanced Hybrid-Media Switching', 'alias': 'MST3 HA Pair', 'numActiveSessions': 0, 'publicIP': '209.55.10.7', 'priority': 0, 'maxConnections': 8000, 'status': 'up'},
    {'mediaSrvIndex': 3, 'switchType': 'Advanced Hybrid-MLT', 'alias': 'MLT transcoder', 'numActiveSessions': 0, 'publicIP': '209.55.10.7', 'priority': 0, 'maxConnections': 2000, 'status': 'up'}
]
<<<sansay_vsx_trunks:sep(0)>>>
{
    1: {
        'recid': 1,
        'alias': 'ATL-PHL VSXs',
        'realtime_stat': {'numOrig': 0,'numTerm': 0,'cps': 0,'numPeak': 0,'totalCLZ': 0,'numCLZCps': 0,'totalLimit': 0,'cpsLimit': 0},
        'calculated_stats': {
            'ingress': {'avg_postdial_delay': 0,'avg_call_duration': 0,'failed_call_ratio': 0,'answer_seize_ratio': 0},
            'egress': {'avg_postdial_delay': 0,'avg_call_duration': 0,'failed_call_ratio': 0,'answer_seize_ratio': 0},
            'realtime': {'origination_sessions': 0,'origination_utilization': 0,'termination_sessions': 0,'termination_utilization': 0}
        }
    },
    10003: {
        'recid': 2,
        'alias': 'MS OC - Test',
        'realtime_stat': {'numOrig': 0,'numTerm': 0,'cps': 0,'numPeak': 0,'totalCLZ': 0, 'numCLZCps': 0, 'totalLimit': 0, 'cpsLimit': 0},
        'calculated_stats': {
            'ingress': {'avg_postdial_delay': 0,'avg_call_duration': 0,'failed_call_ratio': 0,'answer_seize_ratio': 0},
            'egress': {'avg_postdial_delay': 0, 'avg_call_duration': 0, 'failed_call_ratio': 0, 'answer_seize_ratio': 0},
            'realtime': {'origination_sessions': 0, 'origination_utilization': 0, 'termination_sessions': 0, 'termination_utilization': 0}
        }
    },
}
<<<sansay_vsx_system:sep(0)>>>
{
    'id': 1,
    'sum_active_session': 0,
    'sum_attempt_session': 26722,
    'peak_active_session': 23,
    'max_session_allowed': 19750,
    'max_session_exceed': 0,
    'inbound_sip_leg': 0,
    'outbound_sip_leg': 0,
    'peak_sip_leg': 46,
    'inbound_h323_leg': 0,
    'outbound_h323_leg': 0,
    'peak_h323_leg': 0,
    'cpu_idle_percent': 99,
    'flow_control_lev': 0,
    'cluster_active_session': 0,
    'cluster_peak_session': 23,
    'demo_lic': -1,
    'slave_stat': 64,
    'ha_pre_state': 'standby',
    'ha_current_state': 'active',
    'ha_remote_status': 0,
    'switch_over_flag': 3,
    'ha_local_status': 0,
    'max_cps_allowed': 10000,
    'max_cps_exceed': 0,
    'current_cps': 0
}

Example of string_table input for parsing
TBD

Example of data after parsing
TBD
"""


from cmk.agent_based.v2 import (
    AgentSection,
    check_levels,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    IgnoreResultsError,
    Result,
    Service,
    State,
)
import pprint


def parse_sansay_vsx_trunks(string_table):
    parsed = string_table
    pprint(f"{string_table=}")
    pprint(f"{parsed}")
    return parsed


agent_section_sansay_vsx_trunks = AgentSection(
    name = "sansay_vsx",
    parse_function = parse_sansay_vsx_trunks,
)


def discover_sansay_vsx_trunks(section):
    if section is None:
        raise IgnoreResultsError("No API status data returned.")
    else:
        for trunk in section.keys:
            yield Service(item=f"Sansay VSX Trunk {section[trunk]["recid"]} {section[trunk]["alias"]}")


def check_sansay_vsx_trunks(section):
    if section is None:
        raise IgnoreResultsError("No API status data returned.")
    else:
        yield Result(state=State.OK, summary="Everything is OK")


check_plugin_sansay_vsx_trunks = CheckPlugin(
    name = "sansay_vsx_trunks",
    service_name = "Sansay VSX Overview",
    discovery_function = discover_sansay_vsx_trunks,
    check_function = check_sansay_vsx_trunks,
)
