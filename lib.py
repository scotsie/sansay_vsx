#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
"""functions for all Sansay VSX components"""

# License: GNU General Public License v2

import json
from typing import Any, Dict, NamedTuple, Optional, Tuple
from cmk.agent_based.v2 import DiscoveryResult, Service, StringTable
import logging


Levels = Optional[Tuple[float, float]]
SansayVSXAPIData = Dict[str, object]


class Perfdata(NamedTuple):
    """normal monitoring performance data"""

    name: str
    value: float
    levels_upper: Levels
    levels_lower: Levels
    boundaries: Optional[Tuple[Optional[float], Optional[float]]]


def sansay_vsx_logger(file_name, log_format, log_level=logging.ERROR):
    formatter = logging.Formatter(log_format)
    fh = logging.FileHandler(file_name)
    fh.setFormatter(formatter)
    logger = logging.getLogger(__name__)
    logger.addHandler(fh)
    logger.setLevel(log_level)
    return logger


def parse_sansay_vsx(string_table: StringTable) -> SansayVSXAPIData:
    """parse one line of data to dictionary"""
    print(f"parse_sansay_vsx data\n{string_table=}")
    try:
        return json.loads(string_table[0][0])
    except (IndexError, json.decoder.JSONDecodeError):
        return {}


def parse_sansay_vsx_multiple(string_table: StringTable) -> SansayVSXAPIData:
    """parse list of device dictionaries to one dictionary"""
    parsed = {}
    print(f"parse_sansay_vsx_multiple data\n{string_table=}")
    for line in string_table:
        entry = json.loads(line[0])
        # error entry
        # {"error": "Storage data could not be fetched\n"}
        if entry.get("error"):
            continue
        if not entry.get("@odata.type"):
            continue
        if "Drive" in entry.get("@odata.type"):
            item = entry.get("@odata.id")
        elif "Power" in entry.get("@odata.type"):
            item = entry.get("@odata.id")
        elif "Thermal" in entry.get("@odata.type"):
            item = entry.get("@odata.id")
        else:
            item = entry.get("Id")
        parsed.setdefault(item, entry)
    return parsed


def discovery_sansay_vsx_multiple(section: SansayVSXAPIData) -> DiscoveryResult:
    """Discovery multiple items from one dictionary"""
    for item in section:
        yield Service(item=item)


def _try_convert_to_float(value: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def sansay_vsx_health_state(state: Dict[str, Any]):
    """Transfer Sansay VSX health to monitoring health state"""
    health_map: Dict[str, Tuple[int, str]] = {
        "OK": (0, "Normal"),
        "Warning": (1, "A condition requires attention."),
        "Critical": (2, "A critical condition requires immediate attention."),
    }

    state_map: Dict[str, Tuple[int, str]] = {
        "Enabled": (0, "This resource is enabled."),
        "Disabled": (1, "This resource is disabled."),
        "StandbyOffline": (
            1,
            "This resource is enabled but awaits an external action to activate it.",
        ),
        "StandbySpare": (
            0,
            "This resource is part of a redundancy set and awaits a \
failover or other external action to activate it.",
        ),
        "InTest": (
            0,
            "This resource is undergoing testing, or is in the process of \
capturing information for debugging.",
        ),
        "Starting": (0, "This resource is starting."),
        "Absent": (1, "This resource is either not present or detected."),
        "Updating": (1, "The element is updating and may be unavailable or degraded"),
        "UnavailableOffline": (
            1,
            "This function or resource is present but cannot be used",
        ),
        "Deferring": (
            0,
            "The element will not process any commands but will queue new requests",
        ),
        "Quiesced": (
            0,
            "The element is enabled but only processes a restricted set of commands",
        ),
        "Present": (0, "Unoffical resource state - device is present"),
    }

    dev_state = 0
    dev_msg = []
    for key in state.keys():
        state_msg = None
        temp_state = 0
        if key in ["Health"]:
            if state[key] is None:
                continue
            temp_state, state_msg = health_map.get(
                state[key], (3, f"Unknown health state: {state[key]}")
            )
            state_msg = f"Component State: {state_msg}"
        elif key == "HealthRollup":
            if state[key] is None:
                continue
            temp_state, state_msg = health_map.get(
                state[key], (3, f"Unknown rollup health state: {state[key]}")
            )
            state_msg = f"Rollup State: {state_msg}"
        elif key == "State":
            if state[key] is None:
                continue
            temp_state, state_msg = state_map.get(
                state[key], (3, f"Unknown state: {state[key]}")
            )
        dev_state = max(dev_state, temp_state)
        if state_msg:
            dev_msg.append(state_msg)

    if not dev_msg:
        dev_msg.append("No state information found")

    return dev_state, ", ".join(dev_msg)


def process_sansay_vsx_perfdata(entry: Dict[str, Any]):
    """Sansay VSX performance data to monitoring performance data"""
    name = entry.get("Name")
    value = None
    if "Reading" in entry.keys():
        value = entry.get("Reading", 0)
    elif "ReadingVolts" in entry.keys():
        value = entry.get("ReadingVolts", 0)
    elif "ReadingCelsius" in entry.keys():
        value = entry.get("ReadingCelsius", 0)
    if value is None:
        return None

    value = _try_convert_to_float(value)
    min_range = _try_convert_to_float(entry.get("MinReadingRange", None))
    max_range = _try_convert_to_float(entry.get("MaxReadingRange", None))
    min_warn = _try_convert_to_float(entry.get("LowerThresholdNonCritical", None))
    min_crit = _try_convert_to_float(entry.get("LowerThresholdCritical", None))
    upper_warn = _try_convert_to_float(entry.get("UpperThresholdNonCritical", None))
    upper_crit = _try_convert_to_float(entry.get("UpperThresholdCritical", None))

    if min_warn is None and min_crit is not None:
        min_warn = min_crit

    if upper_warn is None and upper_crit is not None:
        upper_warn = upper_crit

    if min_warn is not None and min_crit is None:
        min_crit = float("-inf")

    if upper_warn is not None and upper_crit is None:
        upper_crit = float("inf")

    def optional_tuple(warn: Optional[float], crit: Optional[float]) -> Levels:
        assert (warn is None) == (crit is None)
        if warn is not None and crit is not None:
            return ("fixed", (warn, crit))
        return None

    return Perfdata(
        name,
        value,
        levels_upper=optional_tuple(upper_warn, upper_crit),
        levels_lower=optional_tuple(min_warn, min_crit),
        boundaries=(
            min_range,
            max_range,
        ),
    )


def find_key_recursive(d, key):
    """Search multilevel dict for key"""
    if key in d:
        return d[key]
    for _k, v in d.items():
        if isinstance(v, dict):
            value = find_key_recursive(v, key)
            if value:
                return value
    return None


def sansay_vsx_client(base_url=None, username=None, password=None,
                                default_prefix='/SSConfig/webresources/stats/',
                                sessionkey=None, capath=None,
                                cafile=None, timeout=None,
                                max_retry=None, proxies=None):
    """Create and return appropriate Sansay VSX client instance."""
    """ Instantiates appropriate Sansay VSX object based on existing"""
    """ configuration. Use this to retrieve a pre-configured object

    :param base_url: rest host or ip address.
    :type base_url: str.
    :param username: user name required to login to server
    :type: str
    :param password: password credentials required to login
    :type password: str
    :param default_prefix: default root to extract tree
    :type default_prefix: str
    :param sessionkey: session key credential for current login
    :type sessionkey: str
    :param capath: Path to a directory containing CA certificates
    :type capath: str
    :param cafile: Path to a file of CA certs
    :type cafile: str
    :param timeout: Timeout in seconds for the initial connection
    :type timeout: int
    :param max_retry: Number of times a request will retry after a timeout
    :type max_retry: int
    :param proxies: Dictionary containing protocol to proxy URL mappings
    :type proxies: dict
    :returns: a client object.

    """
    if "://" not in base_url:
        warnings.warn("Scheme not specified for '{}'; adding 'https://'".format(base_url))
        base_url = "https://" + base_url
    return HttpClient(base_url=base_url, username=username, password=password,
                        default_prefix=default_prefix, sessionkey=sessionkey,
                        capath=capath, cafile=cafile, timeout=timeout,
                        max_retry=max_retry, proxies=proxies)