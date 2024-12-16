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
    try:
        json_data = json.loads(string_table[0][0])
        #print(f"{json_data}\n{type(json_data)}")
        return json_data
    except (IndexError, json.decoder.JSONDecodeError):
        return {}
