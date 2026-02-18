#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2


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


Section = list[dict[str, Any]]

# Special Agent Output to Parse for this service
"""
<<<sansay_vsx_media:sep(0)>>>
[
    {'mediaSrvIndex': 1, 'switchType': 'Internal Media Switching', 'alias': 'Internal Media Switching', 'numActiveSessions': 0, 'publicIP': '1.2.3.4', 'priority': 2, 'maxConnections': 3000, 'status': 'up'},
    {'mediaSrvIndex': 2, 'switchType': 'External Advanced Hybrid-Media Switching', 'alias': 'MST3 HA Pair', 'numActiveSessions': 4, 'publicIP': '1.2.3.4', 'priority': 0, 'maxConnections': 8000, 'status': 'up'},
    {'mediaSrvIndex': 3, 'switchType': 'Advanced Hybrid-MLT', 'alias': 'MLT transcoder', 'numActiveSessions': 0, 'publicIP': '1.2.3.4', 'priority': 0, 'maxConnections': 2000, 'status': 'up'}
]

Section comes in as a list within a list containing the dictionary as a string.
[['{values above}']]
Parser 'parse_sansay_vsx' is in sansay_vsx.lib. It filters out the string and performs a json.load.
"""


agent_section_sansay_vsx_cpu = AgentSection(
    name="sansay_vsx_media",
    parse_function=parse_sansay_vsx,
    parsed_section_name="sansay_vsx_media",
)


def discovery_sansay_vsx_media(section: Section) -> DiscoveryResult:
    # print(f"discover media {section=}\n{type(section)}")
    for media_server in section:
        yield Service(item=f"{media_server["alias"]}")


def check_sansay_vsx_media(item, params, section: Section) -> CheckResult:
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent - check agent connectivity")
        return
    media = [d for d in section if d.get("alias") == item]
    if len(media) == 0:
        yield Result(state=State.UNKNOWN, summary=f"No media entry found for item '{item}'")
        return
    if len(media) > 1:
        indices = [e["mediaSrvIndex"] for e in media]
        yield Result(
            state=State.UNKNOWN,
            summary=f"Multiple media entries matched '{item}'",
            details=f"Matched mediaSrvIndex values: {indices}",
        )
        return
    media = media[0]

    yield Result(
        state=State.OK,
        summary=f"{media['alias']} ({media['publicIP']})",
        details=f"{media['alias']} is showing status as {media['status']} with {media['numActiveSessions']} active sessions.",
    )
    if media["status"] != "up":
        yield Result(
            state=State.CRIT,
            summary=f"{media['alias']} ({media['publicIP']}) is not in an up state.",
        )

    max_connections = media["maxConnections"]
    num_active = media["numActiveSessions"]
    yield Metric(name="num_active_sessions", value=num_active, boundaries=(0, max_connections))

    if max_connections > 0:
        _, (session_warn, session_crit) = params["session_levels"]
        session_utilization = round((num_active / max_connections) * 100, 1)
        session_state = 0
        if session_utilization >= session_warn:
            session_state = 1
        if session_utilization >= session_crit:
            session_state = 2
        yield Result(
            state=State(session_state),
            summary=f"Session utilization: {session_utilization}% ({num_active}/{max_connections})",
        )


check_plugin_sansay_vsx_media = CheckPlugin(
    name="sansay_vsx_media",
    service_name="VSX Media Server %s",
    discovery_function=discovery_sansay_vsx_media,
    sections=["sansay_vsx_media"],
    check_function=check_sansay_vsx_media,
    check_ruleset_name="sansay_vsx_media",
    check_default_parameters={
        "session_levels": ("fixed", (80.0, 90.0)),
    },
)
