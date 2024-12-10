#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# (c) Andreas Doehler <andreas.doehler@bechtle.com/andreas.doehler@gmail.com>

# License: GNU General Public License v2

from cmk.agent_based.v2 import (
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
)
from cmk_addons.plugins.sansay_vsx.lib import (
    SansayVSXAPIData,
    sansay_vsx_health_state,
)


def discover_sansay_vsx_summary(section: SansayVSXAPIData) -> DiscoveryResult:
    if len(section) == 1:
        for element in section:
            if "MemorySummary" in element.keys():
                yield Service(item="Summary")
    else:
        for element in section:
            if "MemorySummary" in element.keys():
                item = f"Summary {element.get('Id', '0')}"
                yield Service(item=item)


def check_sansay_vsx_summary(item: str, section: SansayVSXAPIData) -> CheckResult:
    result = None
    if len(section) == 1:
        result = section[0].get("MemorySummary")
    else:
        for element in section:
            if "MemorySummary" in element.keys():
                if item == f"Summary {element.get('Id', '0')}":
                    result = element.get("MemorySummary")
                    break

    if not result:
        return

    state = result.get("Status", {"Health": "Unknown"})
    result_state, state_text = sansay_vsx_health_state(state)
    message = (
        f"Capacity: {result.get('TotalSystemMemoryGiB')}GB, with State: {state_text}"
    )

    yield Result(state=State(result_state), summary=message)


check_plugin_sansay_vsx_summary = CheckPlugin(
    name="sansay_vsx_summary",
    service_name="Memory %s",
    sections=["sansay_vsx_system"],
    discovery_function=discover_sansay_vsx_summary,
    check_function=check_sansay_vsx_summary,
)
