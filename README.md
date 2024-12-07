# Checkmk extension for Sansay VSX via API

![build](https://github.com/scotsie/sansay_vsx/workflows/build/badge.svg)
![flake8](https://github.com/scotsie/sansay_vsx/workflows/Lint/badge.svg)
![pytest](https://github.com/scotsie/sansay_vsx/workflows/pytest/badge.svg)

## Description

This is an initial attempt to develop a CheckMK "Special Agent" to query a Sansay VSX device using supplied credentials and returns data from the 'stats' endpoint of the API for 'media_server', 'realtime' and 'resource' pages.

## Development

For the best development experience use [VSCode](https://code.visualstudio.com/) with the [Remote Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension. This maps your workspace into a checkmk docker container giving you access to the python environment and libraries the installed extension has.

The current configuration is modified slightly to use podman instead of docker desktop.

I can't take credit for this setup as I used this template by [jiuka](https://github\.com/jiuka/checkmk_template/workflows) to start learning to develop locally using the opensource build of CheckMK.

Also a word of appreciation to [Yogibaer75](https://github.com/Yogibaer75) for his publicly available plugins for 2.3.0pXX releases to help fill in gaps in the documentation (which is good but for a novice like me, still somewhat confusing).


## Directories

The following directories in this repo are getting mapped into the Checkmk site.

* `agents`, `checkman`, `checks`, `doc`, `inventory`, `notifications`, `pnp-templates`, `web` are mapped into `local/share/check_mk/`
* `agent_based` is mapped to `local/lib/check_mk/base/plugins/agent_based`
* `nagios_plugins` is mapped to `local/lib/nagios/plugins`

## Continuous integration
### Local

To build the package hit `Crtl`+`Shift`+`B` to execute the build task in VSCode.

`pytest` can be executed from the terminal or the test ui.

### Github Workflow

The provided Github Workflows run `pytest` and `flake8` in the same checkmk docker conatiner as vscode.
