#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
"""Check parameter rulesets for Sansay VSX check plugins."""

# License: GNU General Public License v2

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Float,
    LevelDirection,
    Levels,
    SimpleLevels,
    validators,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostAndItemCondition, HostCondition, Topic


def _parameter_form_sansay_vsx_system() -> Dictionary:
    return Dictionary(
        title=Title("Sansay VSX System Thresholds"),
        elements={
            "cpu_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("CPU Utilization"),
                    help_text=Help(
                        "Upper warning and critical thresholds for CPU utilization."
                    ),
                    form_spec_template=Float(
                        custom_validate=(
                            validators.NumberInRange(min_value=0.0, max_value=100.0),
                        ),
                    ),
                    level_direction=LevelDirection.UPPER,
                    prefill_fixed_levels=DefaultValue((80.0, 90.0)),
                ),
            ),
            "session_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("Session Utilization"),
                    help_text=Help(
                        "Upper warning and critical thresholds for cluster-wide session "
                        "utilization as a percentage of max_session_allowed."
                    ),
                    form_spec_template=Float(
                        custom_validate=(
                            validators.NumberInRange(min_value=0.0, max_value=100.0),
                        ),
                    ),
                    level_direction=LevelDirection.UPPER,
                    prefill_fixed_levels=DefaultValue((80.0, 90.0)),
                ),
            ),
            "session_drop_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("Session Utilization Drop"),
                    help_text=Help(
                        "Upper warning and critical thresholds for a sudden drop in session "
                        "utilization between check intervals (measured in percentage points). "
                        "Useful for detecting unexpected call drops or failover events."
                    ),
                    form_spec_template=Float(
                        custom_validate=(
                            validators.NumberInRange(min_value=0.0),
                        ),
                    ),
                    level_direction=LevelDirection.UPPER,
                    prefill_fixed_levels=DefaultValue((10.0, 20.0)),
                ),
            ),
        },
    )


rule_spec_sansay_vsx_system = CheckParameters(
    name="sansay_vsx_system",
    title=Title("Sansay VSX System"),
    topic=Topic.NETWORKING,
    parameter_form=_parameter_form_sansay_vsx_system,
    condition=HostCondition(),
)


def _parameter_form_sansay_vsx_media() -> Dictionary:
    return Dictionary(
        title=Title("Sansay VSX Media Server Thresholds"),
        elements={
            "session_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("Session Utilization"),
                    help_text=Help(
                        "Upper warning and critical thresholds for media server session "
                        "utilization as a percentage of maxConnections."
                    ),
                    form_spec_template=Float(
                        custom_validate=(
                            validators.NumberInRange(min_value=0.0, max_value=100.0),
                        ),
                    ),
                    level_direction=LevelDirection.UPPER,
                    prefill_fixed_levels=DefaultValue((80.0, 90.0)),
                ),
            ),
        },
    )


rule_spec_sansay_vsx_media = CheckParameters(
    name="sansay_vsx_media",
    title=Title("Sansay VSX Media Server"),
    topic=Topic.NETWORKING,
    parameter_form=_parameter_form_sansay_vsx_media,
    condition=HostAndItemCondition(item_title=Title("Media Server")),
)


def _trunk_stat_direction_dictionary(title_str: str) -> Dictionary:
    """Shared threshold form for egress, ingress, and gw_egress_stat direction groups."""
    return Dictionary(
        title=Title(title_str),
        elements={
            "failed_call_ratio_levels": DictElement(
                parameter_form=Levels(
                    title=Title("Failed Call Ratio"),
                    help_text=Help(
                        "Upper warning and critical thresholds for the failed call ratio (%). "
                        "Select 'No levels' to collect this metric without alerting."
                    ),
                    form_spec_template=Float(
                        custom_validate=(
                            validators.NumberInRange(min_value=0.0, max_value=100.0),
                        ),
                    ),
                    level_direction=LevelDirection.UPPER,
                    prefill_fixed_levels=DefaultValue((5.0, 15.0)),
                ),
            ),
            "answer_seize_ratio_levels": DictElement(
                parameter_form=Levels(
                    title=Title("Answer Seize Ratio"),
                    help_text=Help(
                        "Lower warning and critical thresholds for the answer seize ratio (%). "
                        "Alerts when ASR drops below the configured values. "
                        "Select 'No levels' to collect this metric without alerting."
                    ),
                    form_spec_template=Float(
                        custom_validate=(
                            validators.NumberInRange(min_value=0.0, max_value=100.0),
                        ),
                    ),
                    level_direction=LevelDirection.LOWER,
                    prefill_fixed_levels=DefaultValue((70.0, 50.0)),
                ),
            ),
            "avg_postdial_delay_levels": DictElement(
                parameter_form=Levels(
                    title=Title("Average Post-Dial Delay"),
                    help_text=Help(
                        "Upper warning and critical thresholds for average post-dial delay (seconds). "
                        "High PDD indicates upstream routing latency or SIP signaling issues. "
                        "Select 'No levels' to collect this metric without alerting."
                    ),
                    form_spec_template=Float(
                        custom_validate=(
                            validators.NumberInRange(min_value=0.0),
                        ),
                    ),
                    level_direction=LevelDirection.UPPER,
                    prefill_fixed_levels=DefaultValue((3.0, 5.0)),
                ),
            ),
        },
    )


def _parameter_form_sansay_vsx_trunks() -> Dictionary:
    return Dictionary(
        title=Title("Sansay VSX Trunk Thresholds"),
        elements={
            "egress": DictElement(
                parameter_form=_trunk_stat_direction_dictionary("Egress"),
            ),
            "ingress": DictElement(
                parameter_form=_trunk_stat_direction_dictionary("Ingress"),
            ),
            "gw_egress_stat": DictElement(
                parameter_form=_trunk_stat_direction_dictionary("Gateway Egress"),
            ),
            "realtime": DictElement(
                parameter_form=Dictionary(
                    title=Title("Realtime"),
                    elements={
                        "origination_utilization_levels": DictElement(
                            parameter_form=Levels(
                                title=Title("Origination Utilization"),
                                help_text=Help(
                                    "Upper warning and critical thresholds for trunk outbound "
                                    "capacity utilization (%). Select 'No levels' to collect "
                                    "this metric without alerting."
                                ),
                                form_spec_template=Float(
                                    custom_validate=(
                                        validators.NumberInRange(min_value=0.0, max_value=100.0),
                                    ),
                                ),
                                level_direction=LevelDirection.UPPER,
                                prefill_fixed_levels=DefaultValue((80.0, 90.0)),
                            ),
                        ),
                        "termination_utilization_levels": DictElement(
                            parameter_form=Levels(
                                title=Title("Termination Utilization"),
                                help_text=Help(
                                    "Upper warning and critical thresholds for trunk inbound "
                                    "capacity utilization (%). Select 'No levels' to collect "
                                    "this metric without alerting."
                                ),
                                form_spec_template=Float(
                                    custom_validate=(
                                        validators.NumberInRange(min_value=0.0, max_value=100.0),
                                    ),
                                ),
                                level_direction=LevelDirection.UPPER,
                                prefill_fixed_levels=DefaultValue((80.0, 90.0)),
                            ),
                        ),
                    },
                ),
            ),
        },
    )


rule_spec_sansay_vsx_trunks = CheckParameters(
    name="sansay_vsx_trunks",
    title=Title("Sansay VSX Trunk"),
    topic=Topic.NETWORKING,
    parameter_form=_parameter_form_sansay_vsx_trunks,
    condition=HostAndItemCondition(item_title=Title("Trunk")),
)
