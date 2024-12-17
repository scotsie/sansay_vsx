#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2


from collections.abc import Mapping

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    # get_value_store,
    Result,
    Service,
    State,
)
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


def check_sansay_vsx_media(item, section: Section) -> CheckResult:
    media = [d for d in section if d.get("alias") == item]
    if len(media) == 1:
        media = media[0]
    else:
        yield Result(
            state = State.UNKNOWN,
            summary = f"{media['alias']} ({media['publicIP']}) had more than one match.",
            details = f"{[e["mediaSrvIndex"] for e in media]}"
        )
    
    yield Result(
        state = State.OK,
        summary = f"{media['alias']} ({media['publicIP']})",
        details = f"{media['alias']} is showing status as {media["status"]} with {media["numActiveSessions"]}."
        )
    if media["status"] != 'up':
        yield Result(
            state = State.CRIT,
            summary= f"{media['alias']} ({media['publicIP']}) is not in an up state."
        )
    yield Metric(
        name = f"numActiveSessionsdirection",
        value = media["numActiveSessions"],
        boundaries = (0, media["maxConnections"])
    )


check_plugin_sansay_vsx_media = CheckPlugin(
    name="sansay_vsx_media",
    service_name="VSX Media Server %s",
    discovery_function=discovery_sansay_vsx_media,
    sections=["sansay_vsx_media"],
    check_function=check_sansay_vsx_media,
)
