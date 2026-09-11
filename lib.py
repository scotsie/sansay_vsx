#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
"""functions for all Sansay VSX components"""

# License: GNU General Public License v2

import json
import logging
from typing import Dict, NamedTuple, Optional, Tuple

from cmk.agent_based.v2 import StringTable


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


AGENT_ERROR_KEY = "_agent_error"


def parse_sansay_vsx(string_table: StringTable) -> SansayVSXAPIData:
    """parse one line of data to dictionary"""
    try:
        json_data = json.loads(string_table[0][0])
    except (IndexError, TypeError, json.decoder.JSONDecodeError):
        return {}
    # A section may legitimately carry JSON 'null' from older agent versions
    # that wrote None when a report was unavailable. Normalize it so check
    # plug-ins only ever see a container.
    if json_data is None:
        return {}
    return json_data


def agent_error(section) -> str | None:
    """
    Return the failure reason the special agent recorded for a section.

    The agent writes {"_agent_error": "..."} (or a single-entry list of it for
    list sections) when a report could not be fetched or was missing data, so a
    check can name the cause instead of reporting a bare missing section.
    """
    if isinstance(section, dict):
        error = section.get(AGENT_ERROR_KEY)
        return error if isinstance(error, str) else None
    if isinstance(section, list):
        for entry in section:
            if isinstance(entry, dict) and isinstance(entry.get(AGENT_ERROR_KEY), str):
                return entry[AGENT_ERROR_KEY]
    return None
