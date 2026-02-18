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
    SimpleLevels,
    validators,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostCondition, Topic


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
