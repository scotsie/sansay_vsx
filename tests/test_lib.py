#!/usr/bin/env python3
"""Tests for the shared parse_sansay_vsx parser in lib.py."""

import json
import pytest

from cmk_addons.plugins.sansay_vsx.lib import parse_sansay_vsx


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
