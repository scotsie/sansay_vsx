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
    sections = [
        "media_server",
        "realtime",
        "resource"
    ]
    return Dictionary(
        title=Title("Sansay VSX API"),
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
            "port": DictElement(
                parameter_form=Integer(
                    title=Title("Advanced - TCP Port number"),
                    help_text=Help(
                        "Port number for connection to the Rest API. Usually 8888 (TLS)."
                    ),
                    prefill=DefaultValue(8888),
                    custom_validate=(
                        validators.NumberInRange(min_value=1, max_value=65535),
                    ),
                ),
            ),
            "sections": DictElement(
                parameter_form=MultipleChoice(
                    title=Title("Enabled Sections.... (only use in case of problems)"),
                    help_text=Help(
                        "Sections to retrieve information on"
                    ),
                    elements=[
                        MultipleChoiceElement(
                            name="media_server",
                            title=Title("Media Server"),
                        ),
                        MultipleChoiceElement(
                            name="realtime",
                            title=Title("Realtime"),
                        ),
                        MultipleChoiceElement(
                            name="resource",
                            title=Title("Resource"),
                        ),
                    ],
                    prefill=DefaultValue(sections),
                ),
            ),
            "verify_ssl": DictElement(
                parameter_form=BooleanChoice(
                    title=Title("Enable SSL verification"),
                    label=Label("enabled"),
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
            "retries": DictElement(
                parameter_form=Integer(
                    title=Title("Advanced - Retries for failed connection"),
                    help_text=Help(
                        "Number of times to retry a connection."
                    ),
                    prefill=DefaultValue(4),
                    custom_validate=(
                        validators.NumberInRange(min_value=1, max_value=20),
                    ),
                ),
            )
        }
    )


rule_spec_sansay_vsx_datasource_programs = SpecialAgent(
    name="sansay_vsx",
    title=Title("Sansay VSX via REST API"),
    topic=Topic.SERVER_HARDWARE,
    parameter_form=_valuespec_special_agents_sansay_vsx,
    help_text=(
        "This rule selects the Sansay VSX Agent which collects data "
        "through the Sansay VSX REST API."
    )
)
