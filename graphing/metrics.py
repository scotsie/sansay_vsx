#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
'''Metric definition for Sansay VSX Graphs and collections'''


# License: GNU General Public License v2

from cmk.graphing.v1.metrics import Color, DecimalNotation, Metric, StrictPrecision, Title, Unit, Product
from cmk.graphing.v1.graphs import Graph

unit_percent = Unit(
    DecimalNotation("%"),
    StrictPrecision(0)
)


metric_sansay_cpu_utilization = Metric(
    name="cpu_utilization",
    title=Title("CPU Utilization"),
    unit=unit_percent,
    color=Color.RED,
)

metric_sansay_session_utilization = Metric(
    name="session_utilization",
    title=Title("Session Utilization"),
    unit=unit_percent,
    color=Color.GREEN,
)

metric_sansay_session_utilization_drop = Metric(
    name="session_utilization_drop",
    title=Title("Session Utilization Drop"),
    unit=unit_percent,
    color=Color.YELLOW,
)

metric_sansay_session_utilization_trend = Product(
    title=Title("Session Utilization Trend"),
    unit=unit_percent,
    color=Color.YELLOW,
    factors=[
        "metric_sansay_session_utilization",
        "metric_sansay_session_utilization_drop"
    ],
)


graph_sansay_vsx_system = Graph(
    name="sansay_vsx_system",
    title=Title("Sansay VSX System Metrics"),
    simple_lines=[
        "cpu_utilization",
        "metric_sansay_session_utilization_trend"
    ],
    compound_lines=[
        "session_utilization"
    ],
)
