#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
"""server side component to create the special agent call"""

# License: GNU General Public License v2

from collections.abc import Iterator, Mapping, Sequence
from pydantic import BaseModel

from cmk.server_side_calls.v1 import (
    HostConfig,
    Secret,
    SpecialAgentCommand,
    SpecialAgentConfig,
)


class SansayVSXParams(BaseModel):
    """params validator"""
    #host: str | None = None
    user: str | None = None
    password: Secret | None = None
    proto: tuple[str, str | None] = ("https", None)
    port: int | None = 8888
    sections: list | None = ["media_server","realtime","resource"]
    verify_ssl: bool | None = False
    timeout: int | None = 30
    retries: int | None = 3
    debug: bool | None = False


def _agent_sansay_vsx_arguments(
    params: SansayVSXParams, host_config: HostConfig
) -> Iterator[SpecialAgentCommand]:
    command_arguments: list[str | Secret] = []
    if params.user is not None:
        command_arguments += ["--user", params.user]
    if params.password is not None:
        command_arguments += ["--password", params.password]
    if params.port is not None:
        command_arguments += ["--port", str(params.port)]
    if params.proto is not None:
        command_arguments += ["-proto", params.proto[0]]
    if params.sections is not None:
        command_arguments += ["--sections", ",".join(params.sections)]
    if params.timeout is not None:
        command_arguments += ["--timeout", str(params.timeout)]
    if params.retries is not None:
        command_arguments += ["--retries", str(params.retries)]
    if params.debug:
        command_arguments += ["--debug"]
    
    command_arguments.append(host_config.primary_ip_config.address or host_config.name)
    yield SpecialAgentCommand(command_arguments=command_arguments)


special_agent_sansay_vsx = SpecialAgentConfig(
    name="sansay_vsx",
    parameter_parser=SansayVSXParams.model_validate,
    commands_function=_agent_sansay_vsx_arguments,
)
