#!/usr/bin/env python3
"""Tests for the shared parse_sansay_vsx parser in lib.py."""

import json
import pytest

from cmk_addons.plugins.sansay_vsx.lib import agent_error, parse_sansay_vsx


def test_parse_valid_dict():
    data = {"key": "value", "number": 42}
    string_table = [[json.dumps(data)]]
    assert parse_sansay_vsx(string_table) == data


def test_parse_valid_list():
    data = [{"alias": "server1"}, {"alias": "server2"}]
    string_table = [[json.dumps(data)]]
    assert parse_sansay_vsx(string_table) == data


def test_parse_empty_string_table():
    assert parse_sansay_vsx([]) == {}


def test_parse_empty_inner_list():
    assert parse_sansay_vsx([[]]) == {}


def test_parse_malformed_json():
    assert parse_sansay_vsx([["not valid json {"]]) == {}


def test_parse_preserves_numeric_types():
    data = {"cpu_idle_percent": 98, "float_val": 3.14}
    string_table = [[json.dumps(data)]]
    result = parse_sansay_vsx(string_table)
    assert result["cpu_idle_percent"] == 98
    assert result["float_val"] == pytest.approx(3.14)


def test_parse_json_null_section():
    """
    Older agent versions wrote None for an unavailable report, which serializes
    to 'null'. json.loads succeeds and returns None, so the check plug-in was
    handed a non-container section.
    """
    assert parse_sansay_vsx([["null"]]) == {}


def test_agent_error_from_dict_section():
    assert agent_error({"_agent_error": "no system data: HTTP 503"}) == "no system data: HTTP 503"


def test_agent_error_from_list_section():
    assert agent_error([{"_agent_error": "no media data"}]) == "no media data"


def test_agent_error_none_for_healthy_sections():
    assert agent_error({"cpu_idle_percent": 98}) is None
    assert agent_error([{"alias": "Internal"}]) is None
    assert agent_error({}) is None
    assert agent_error(None) is None
