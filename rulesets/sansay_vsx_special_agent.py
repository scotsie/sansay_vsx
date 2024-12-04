#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
"""rule for assinging the special agent to host objects"""

# License: GNU General Public License v2

from cmk.rulesets.v1 import Title, Help, Label
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    CascadingSingleChoice,
    CascadingSingleChoiceElement,
    DefaultValue,
    DictElement,
    Dictionary,
    FixedValue,
    Integer,
    MultipleChoice,
    MultipleChoiceElement,
    Password,
    String,
    migrate_to_password,
    validators,
)
from cmk.rulesets.v1.rule_specs import Topic, SpecialAgent


def _valuespec_special_agents_sansay_vsx() -> Dictionary:
    return Dictionary(
        title=Title("Sansay VSX REST API"),
        help_text=Help(
            "This rule set selects the Sansay VSX special agent instead of the normal Checkmk Agent "
            "and allows monitoring via the Sansay VSX REST API."
        ),
        elements={
            "user": DictElement(
                parameter_form=String(
                    title=Title("Username"),
                ),
                required=True,
            ),
            "password": DictElement(
                parameter_form=Password(
                    title=Title("Password"),
                    custom_validate=(validators.LengthInRange(min_value=1),),
                    migrate=migrate_to_password,
                ),
                required=True,
            ),
            "sections": DictElement(
                parameter_form=MultipleChoice(
                    title=Title("Sections..."),
                    help_text=Help("These are the sections to gather information from."),
                    elements=[
                        MultipleChoiceElement(
                            name="media_server",
                            title=Title("Media Server Stats")
                        ),
                        MultipleChoiceElement(
                            name="realtime",
                            title=Title("Realtime Stats")
                        ),
                        MultipleChoiceElement(
                            name="resource",
                            title=Title("Resource Stats")
                        ),
                    ],
                    prefill=DefaultValue([
                        "media_server",
                        "realtime",
                        "resource"
                    ]),
                    show_toggle_all=True,
                ),
            ),
            "port": DictElement(
                parameter_form=Integer(
                    title=Title("Advanced - TCP Port number"),
                    help_text=Help(
                        "Port number for connection to the Rest API. Usually 8888 (TLS)"
                    ),
                    prefill=DefaultValue(8888),
                    custom_validate=(
                        validators.NumberInRange(min_value=1, max_value=65535),
                    ),
                ),
            ),
            "proto": DictElement(
                parameter_form=CascadingSingleChoice(
                    title=Title("Advanced - Protocol"),
                    prefill=DefaultValue("https"),
                    help_text=Help(
                        "Protocol for the connection to the Rest API."
                    ),
                    elements=[
                        CascadingSingleChoiceElement(
                            name="http",
                            title=Title("http"),
                            parameter_form=FixedValue(value=None),
                        ),
                        CascadingSingleChoiceElement(
                            name="https",
                            title=Title("https"),
                            parameter_form=FixedValue(value=None),
                        ),
                    ],
                ),
            ),
            "retries": DictElement(
                parameter_form=Integer(
                    title=Title("Advanced - Number of retries"),
                    help_text=Help(
                        "Number of retry attempts made by the special agent."
                    ),
                    prefill=DefaultValue(10),
                    custom_validate=(
                        validators.NumberInRange(min_value=1, max_value=20),
                    ),
                ),
            ),
            "timeout": DictElement(
                parameter_form=Integer(
                    title=Title("Advanced - Timeout for connection"),
                    help_text=Help(
                        "Number of seconds for a single connection attempt before timeout occurs."
                    ),
                    prefill=DefaultValue(10),
                    custom_validate=(
                        validators.NumberInRange(min_value=1, max_value=20),
                    ),
                ),
            ),
            "debug": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Debug mode"),
                    label=Label("enabled"),
                ),
            ),
        },
    )


rule_spec_sansay_vsx = SpecialAgent(
    name="sansay_vsx",
    title=Title("Sansay VSX via REST API"),
    topic=Topic.APPLICATIONS,
    parameter_form=_valuespec_special_agents_sansay_vsx,
    help_text=(
        "This rule selects the Sansay VSX Agent which collects data "
        "through the Sansay VSX REST API."
    )
)
