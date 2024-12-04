#!/usr/bin/env python
# -*- encoding: utf-8; py-indent-offset: 4 -*-

"""
Example output from special agent:
<<<sansay_vsx:sep(0)>>>
{
    'media_stats': [{'mediaSrvIndex': 1, 'switchType': 'Internal Media Switching', 'alias': 'Internal Media Switching', 'numActiveSessions': 0, 'publicIP': '209.55.10.4', 'priority': 2, 'maxConnections': 3000, 'status': 'up'},],
    'system_stat': {id': 1,'sum_active_session': 4,'sum_attempt_session': 23748,'peak_active_session': 23,'max_session_allowed': 19750,'max_session_exceed': 0,'inbound_sip_leg': 4, 'outbound_sip_leg': 4, 'peak_sip_leg': 46, 'inbound_h323_leg': 0, 'outbound_h323_leg': 0, 'peak_h323_leg': 0, 'cpu_idle_percent': 99, 'flow_control_lev': 0, 'cluster_active_session': 4, 'cluster_peak_session': 23, 'demo_lic': -1, 'slave_stat': 64, 'ha_pre_state': 'standby', 'ha_current_state': 'active', 'ha_remote_status': 0, 'switch_over_flag': 3, 'ha_local_status': 0, 'max_cps_allowed': 10000, 'max_cps_exceed': 0, 'current_cps': 0},
    'trunks': {
        1: {
            'recid': 1,
            'alias': 'ATL-PHL VSXs',
            'ingress_stat': {'1st15mins_call_attempt': 0, '1st15mins_call_answer': 0, '1st15mins_call_fail': 0, '1h_call_attempt': 0, '1h_call_answer': 0, '1h_call_fail': 0, '24h_call_attempt': 9, '24h_call_answer': 0, '24h_call_fail': 9, '1st15mins_call_durationSec': 0, '1h_call_durationSec': 0, '24h_call_durationSec': 0, '1st15mins_pdd_ms': 0, '1h_pdd_ms': 0, '24h_pdd_ms': 0},
            'gw_egress_stat': { '1st15mins_call_attempt': 4, '1st15mins_call_answer': 3, '1st15mins_call_fail': 0, '1h_call_attempt': 12, '1h_call_answer': 10, '1h_call_fail': 0, '24h_call_attempt': 194, '24h_call_answer': 151, '24h_call_fail': 13, '1st15mins_call_durationSec': 272, '1h_call_durationSec': 4858, '24h_call_durationSec': 50323, '1st15mins_pdd_ms': 11560, '1h_pdd_ms': 27440, '24h_pdd_ms': 510510},
            'realtime_stat': { 'numOrig': 0, 'numTerm': 2, 'cps': 0, 'numPeak': 3, 'totalCLZ': 2, 'numCLZCps': 0, 'totalLimit': 2000, 'cpsLimit': 100}
        },
        10003: {
            'recid': 2,
            'alias': 'MS OC - Test',
            'ingress_stat': { '1st15mins_call_attempt': 0, '1st15mins_call_answer': 0, '1st15mins_call_fail': 0, '1h_call_attempt': 0, '1h_call_answer': 0, '1h_call_fail': 0, '24h_call_attempt': 0, '24h_call_answer': 0, '24h_call_fail': 0, '1st15mins_call_durationSec': 0, '1h_call_durationSec': 0, '24h_call_durationSec': 0, '1st15mins_pdd_ms': 0, '1h_pdd_ms': 0, '24h_pdd_ms': 0},
            'gw_egress_stat': { '1st15mins_call_attempt': 0, '1st15mins_call_answer': 0, '1st15mins_call_fail': 0, '1h_call_attempt': 0, '1h_call_answer': 0, '1h_call_fail': 0, '24h_call_attempt': 0, '24h_call_answer': 0, '24h_call_fail': 0, '1st15mins_call_durationSec': 0, '1h_call_durationSec': 0, '24h_call_durationSec': 0, '1st15mins_pdd_ms': 0, '1h_pdd_ms': 0, '24h_pdd_ms': 0},
            'realtime_stat': { 'numOrig': 0, 'numTerm': 0, 'cps': 0, 'numPeak': 0, 'totalCLZ': 0, 'numCLZCps': 0, 'totalLimit': 0, 'cpsLimit': 0}
        },
    }
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


def parse_sansay_vsx_status(string_table):
    parsed = []
    pprint(f"{string_table=}")
    pprint(f"{parsed}")
    return parsed


agent_section_sansay_vsx_status = AgentSection(
    name = "sansay_vsx",
    parse_function = parse_sansay_vsx_status,
)


def discover_sansay_vsx_status(section):
    if section is None:
        raise IgnoreResultsError("No API status data returned.")
    else:
        yield Service(item="Sansay VSX Overview")


def check_sansay_vsx_status(section):
    if section is None:
        raise IgnoreResultsError("No API status data returned.")
    else:
        yield Result(state=State.OK, summary="Everything is OK")


check_plugin_sansay_vsx_status = CheckPlugin(
    name = "sansay_vsx",
    service_name = "Sansay VSX Overview",
    discovery_function = discover_sansay_vsx_status,
    check_function = check_sansay_vsx_status,
)
