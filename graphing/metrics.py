#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
'''Metric definition for Sansay VSX Graphs and collections'''


# License: GNU General Public License v2

from cmk.graphing.v1.metrics import Color, DecimalNotation, Metric, StrictPrecision, Title, Unit, Product
from cmk.graphing.v1.graphs import Graph

unit_percent = Unit(
    DecimalNotation("%"),
    StrictPrecision(1)
)

unit_count = Unit(
    DecimalNotation(""),
    StrictPrecision(0)
)

unit_seconds = Unit(
    DecimalNotation("s"),
    StrictPrecision(1)
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

metric_sansay_session_utilization_avg = Metric(
    name="session_utilization_avg",
    title=Title("Session Utilization (Rolling Avg)"),
    unit=unit_percent,
    color=Color.CYAN,
)

metric_sansay_session_utilization_trend = Product(
    title=Title("Session Utilization Trend"),
    unit=unit_percent,
    color=Color.YELLOW,
    factors=[
        "session_utilization",
        "session_utilization_drop",
    ],
)


metric_sansay_num_active_sessions = Metric(
    name="num_active_sessions",
    title=Title("Active Sessions"),
    unit=unit_count,
    color=Color.BLUE,
)


graph_sansay_vsx_media = Graph(
    name="sansay_vsx_media",
    title=Title("Sansay VSX Media Server Active Sessions"),
    compound_lines=[
        "num_active_sessions",
    ],
)


graph_sansay_vsx_system = Graph(
    name="sansay_vsx_system",
    title=Title("Sansay VSX System Metrics"),
    simple_lines=[
        "cpu_utilization",
        "metric_sansay_session_utilization_trend",
    ],
    compound_lines=[
        "session_utilization",
    ],
    optional=[
        # Only emitted when rolling average mode is enabled in check parameters
        "session_utilization_avg",
    ],
)


# =============================================================================
# Trunk metrics — Ingress direction
# =============================================================================

metric_ingress_answer_seize_ratio = Metric(
    name="ingress_answer_seize_ratio",
    title=Title("Ingress Answer Seize Ratio"),
    unit=unit_percent,
    color=Color.BLUE,
)

metric_ingress_avg_call_duration = Metric(
    name="ingress_avg_call_duration",
    title=Title("Ingress Avg Call Duration"),
    unit=unit_seconds,
    color=Color.BLUE,
)

metric_ingress_avg_postdial_delay = Metric(
    name="ingress_avg_postdial_delay",
    title=Title("Ingress Avg Post-Dial Delay"),
    unit=unit_seconds,
    color=Color.BLUE,
)

metric_ingress_failed_call_ratio = Metric(
    name="ingress_failed_call_ratio",
    title=Title("Ingress Failed Call Ratio"),
    unit=unit_percent,
    color=Color.BLUE,
)


# =============================================================================
# Trunk metrics — Egress direction
# =============================================================================

metric_egress_answer_seize_ratio = Metric(
    name="egress_answer_seize_ratio",
    title=Title("Egress Answer Seize Ratio"),
    unit=unit_percent,
    color=Color.GREEN,
)

metric_egress_avg_call_duration = Metric(
    name="egress_avg_call_duration",
    title=Title("Egress Avg Call Duration"),
    unit=unit_seconds,
    color=Color.GREEN,
)

metric_egress_avg_postdial_delay = Metric(
    name="egress_avg_postdial_delay",
    title=Title("Egress Avg Post-Dial Delay"),
    unit=unit_seconds,
    color=Color.GREEN,
)

metric_egress_failed_call_ratio = Metric(
    name="egress_failed_call_ratio",
    title=Title("Egress Failed Call Ratio"),
    unit=unit_percent,
    color=Color.GREEN,
)


# =============================================================================
# Trunk metrics — Realtime
# =============================================================================

metric_realtime_origination_sessions = Metric(
    name="realtime_origination_sessions",
    title=Title("Origination Sessions"),
    unit=unit_count,
    color=Color.ORANGE,
)

metric_realtime_termination_sessions = Metric(
    name="realtime_termination_sessions",
    title=Title("Termination Sessions"),
    unit=unit_count,
    color=Color.PURPLE,
)

metric_realtime_origination_utilization = Metric(
    name="realtime_origination_utilization",
    title=Title("Origination Utilization"),
    unit=unit_percent,
    color=Color.ORANGE,
)

metric_realtime_termination_utilization = Metric(
    name="realtime_termination_utilization",
    title=Title("Termination Utilization"),
    unit=unit_percent,
    color=Color.PURPLE,
)


# =============================================================================
# Trunk graph groupings
# =============================================================================

graph_sansay_vsx_trunk_answer_seize_ratio = Graph(
    name="sansay_vsx_trunk_answer_seize_ratio",
    title=Title("Trunk Answer Seize Ratio"),
    simple_lines=[
        "ingress_answer_seize_ratio",
        "egress_answer_seize_ratio",
    ],
)

graph_sansay_vsx_trunk_avg_call_duration = Graph(
    name="sansay_vsx_trunk_avg_call_duration",
    title=Title("Trunk Avg Call Duration"),
    simple_lines=[
        "ingress_avg_call_duration",
        "egress_avg_call_duration",
    ],
)

graph_sansay_vsx_trunk_avg_postdial_delay = Graph(
    name="sansay_vsx_trunk_avg_postdial_delay",
    title=Title("Trunk Avg Post-Dial Delay"),
    simple_lines=[
        "ingress_avg_postdial_delay",
        "egress_avg_postdial_delay",
    ],
)

graph_sansay_vsx_trunk_failed_call_ratio = Graph(
    name="sansay_vsx_trunk_failed_call_ratio",
    title=Title("Trunk Failed Call Ratio"),
    simple_lines=[
        "ingress_failed_call_ratio",
        "egress_failed_call_ratio",
    ],
)

graph_sansay_vsx_trunk_realtime_sessions = Graph(
    name="sansay_vsx_trunk_realtime_sessions",
    title=Title("Trunk Realtime Sessions"),
    compound_lines=[
        "realtime_origination_sessions",
        "realtime_termination_sessions",
    ],
)

graph_sansay_vsx_trunk_realtime_utilization = Graph(
    name="sansay_vsx_trunk_realtime_utilization",
    title=Title("Trunk Realtime Utilization"),
    simple_lines=[
        "realtime_origination_utilization",
        "realtime_termination_utilization",
    ],
)
