#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2

import time
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


def _check_levels(value: float, level_spec: tuple, bound: str = "upper") -> int:
    """
    Evaluate a value against a SimpleLevels spec, returning 0/1/2.

    Handles both ("fixed", (warn, crit)) and ("no_levels", None) — the latter
    always returns 0, allowing metric collection without alerting.
    """
    if level_spec[0] == "no_levels":
        return 0
    _, (warn, crit) = level_spec
    if bound == "upper":
        if value >= crit:
            return 2
        if value >= warn:
            return 1
    else:  # lower
        if value <= crit:
            return 2
        if value <= warn:
            return 1
    return 0


def _rolling_average(
    current_value: float,
    now: float,
    window_minutes: int,
    value_store: dict,
) -> float:
    """
    Append current_value to a timestamped history list stored in value_store,
    prune entries older than window_minutes, and return the mean of the window.

    Returns current_value unchanged if this is the first sample.
    """
    history = value_store.get("session_util_history", [])
    history.append({"t": now, "v": current_value})
    cutoff = now - (window_minutes * 60)
    history = [s for s in history if s["t"] >= cutoff]
    value_store["session_util_history"] = history
    return sum(s["v"] for s in history) / len(history)


def discovery_sansay_vsx_system(section: Section) -> DiscoveryResult:
    if "cpu_idle_percent" in section.keys():
        yield Service()
    else:
        return


def check_sansay_vsx_system(params, section: Section) -> CheckResult:
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent - check agent connectivity")
        return

    value_store = get_value_store()

    # --- CPU utilization ---
    cpu_utilization = 100.0 - section["cpu_idle_percent"]
    cpu_state = _check_levels(cpu_utilization, params["cpu_levels"])
    yield Result(state=State(cpu_state), summary=f"CPU at {cpu_utilization}%.")
    yield Metric(name="cpu_utilization", value=cpu_utilization, boundaries=(0, 100))

    # --- Session utilization ---
    if not (section["max_session_allowed"] and section["sum_active_session"] is not None):
        return

    session_utilization = round(
        (section["sum_active_session"] / section["max_session_allowed"]) * 100, 1
    )
    yield Metric(name="session_utilization", value=session_utilization, boundaries=(0, 100))

    # Optionally smooth with a rolling average before threshold evaluation.
    # The raw metric is always emitted above; the averaged metric is emitted
    # separately so both can be graphed when rolling average is active.
    use_rolling = params.get("session_rolling_average", "instantaneous") == "rolling_average"
    if use_rolling:
        window = params.get("session_rolling_window", 15)
        eval_utilization = round(
            _rolling_average(session_utilization, time.time(), window, value_store), 1
        )
        yield Metric(name="session_utilization_avg", value=eval_utilization, boundaries=(0, 100))
        util_label = f"{eval_utilization}% ({window}m avg)"
    else:
        eval_utilization = session_utilization
        util_label = f"{session_utilization}%"

    session_state = _check_levels(eval_utilization, params["session_levels"])

    # Drop detection always compares instantaneous values so it reflects actual
    # sudden changes regardless of whether the utilization threshold uses averaging.
    prev = value_store.get("sansay_vsx.session_utilization")
    drop = None
    if prev is not None:
        drop = round(prev - session_utilization, 1)
        drop_state = _check_levels(drop, params["session_drop_levels"])
        session_state = max(session_state, drop_state)
    value_store["sansay_vsx.session_utilization"] = session_utilization

    session_summary = f"Session Utilization at {util_label}."
    if drop is not None:
        session_summary += f" Drop since last: {drop}%."

    yield Result(state=State(session_state), summary=session_summary)
    yield Metric(
        name="session_utilization_drop",
        value=(drop if drop is not None else 0.0),
        boundaries=(None, None),
    )


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
        "session_rolling_average": "instantaneous",
        "session_rolling_window": 15,
    },
)
