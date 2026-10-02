#!/usr/bin/env python3

"""
Special agent for monitoring Sansay VSX devices.
Media Server = stats/media_server
Realtime = stats/realtime
Resource = state/resource
"""

import logging
import re
import time
from collections.abc import Sequence

import requests
from requests.auth import HTTPBasicAuth

from cmk.special_agents.v0_unstable.agent_common import SectionWriter, special_agent_main
from cmk.special_agents.v0_unstable.argument_parsing import Args, create_default_argument_parser
from cmk.utils import password_store
from pathlib import Path


LOGGER = logging.getLogger("agent_sansay_vsx")

# Key used to carry a per-report failure reason from the agent into the section
# payload, so the check plug-in can report *why* data is missing instead of the
# generic "No data from agent".
AGENT_ERROR_KEY = "_agent_error"

# Key under which poll_sansay_vsx collects per-report failure reasons.
ERRORS_KEY = "_errors"

# HTTP statuses worth another attempt: transient server-side or rate limiting.
# 400 is included because clustered VSX pairs are polled twice per cycle (once
# per node's own check, once by the cluster host's cluster_check_function), and
# the device intermittently 400s when two Basic-Auth requests land within
# milliseconds of each other. A short backoff retry clears the race. Anything
# else (401/403/404) will not improve by retrying.
_RETRYABLE_STATUS = frozenset({400, 429, 500, 502, 503, 504})


def parse_arguments(argv: Sequence[str] | None) -> Args:
    """Parse arguments needed to construct an URL and for connection conditions"""
    sections = [
        "media_server",
        "realtime",
        "resource",
    ]

    parser = create_default_argument_parser(description=__doc__)
    # required
    parser.add_argument(
        "--user",
        default=None,
        help="Username for Sansay VSX Login",
        required=True
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--password",
        default=None,
        help="""Password for Sansay VSX API Login. Preferred over --password-id""",
    )
    group.add_argument(
        "--password-id",
        default=None,
        help="""Password store reference to the password for Sansay VSX login""",
    )
    # optional
    parser.add_argument(
        "--proto",
        default="https",
        help="""Use 'http' or 'https' (default=https)""",
    )
    parser.add_argument(
        "--port",
        default=8888,
        type=int,
        help="Use alternative port (default: 8888)",
    )
    parser.add_argument(
        "--sections",
        default=",".join(sections),
        help=f"Comma separated list of data to query. \
               Possible values: {','.join(sections)} (default: all)",
    )
    parser.add_argument(
        "--verify_ssl",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--timeout",
        default=3,
        type=int,
        help="""Timeout in seconds for a connection attempt""",
    )
    parser.add_argument(
        "--retries",
        default=2,
        type=int,
        help="""Number auf connection retries before failing""",
    )
    parser.add_argument(
        "host",
        metavar="HOSTNAME",
        help="""IP address or hostname of your Sansay VSX API""",
    )

    return parser.parse_args(argv)


def _int_arg(args, name, default):
    """Read an int argument defensively (argparse may not have supplied it)."""
    try:
        return int(getattr(args, name, default))
    except (TypeError, ValueError):
        return default


def _record_error(errors, report_name, message):
    """Store a report failure reason for later inclusion in the section data."""
    if errors is not None:
        errors[report_name] = message


def _has_report_tables(data):
    """True when a report response carries at least one table."""
    return bool(_observed_table_names(data))


def fetch_sansay_json(args, report_name, errors=None, is_usable=None):
    """
    Fetch one Sansay report, retrying transient failures up to --retries times.

    A 200 whose JSON fails the optional `is_usable(data)` check is retried like
    any other transient failure: the device sometimes answers a racing request
    with a well-formed but empty body.

    Returns the decoded JSON, or None on failure. Failures are logged to stderr
    and, when an `errors` dict is supplied, recorded under `report_name` so the
    reason can be surfaced in the affected section instead of being lost.
    Diagnostics must never be printed to stdout: these calls happen while a
    section header is already open, and any stray line corrupts the payload.
    """
    if args.debug:
        print(f"{args=}")
    device = args.host
    password = None
    if args.password:
        match args.password:
            case str() if re.match(r'^[a-zA-Z0-9-]+:/[a-zA-Z0-9/_]+$', args.password):
                uuid, path = args.password.split(':')
                try:
                    password = password_store.lookup(pw_file=Path(path), pw_id=uuid)
                except ValueError as e:
                    message = f"{report_name} report unavailable: password store lookup failed: {e}"
                    LOGGER.error("[%s] -> %s", device, message)
                    _record_error(errors, report_name, message)
                    return None
            case str() if re.match(r'^[a-zA-Z0-9]+$', args.password):
                password = args.password
            case other:
                raise TypeError(other)

    username = args.user
    protocol = args.proto
    port = args.port
    ssl_verify = args.verify_ssl
    timeout = _int_arg(args, "timeout", 3)
    attempts = max(1, _int_arg(args, "retries", 2) + 1)
    # TODO for later implementation
    # sections = [args.sections.split(",")]

    if args.debug:
        print(f"[{device}] -> fetching Sansay VSX {report_name} stats")

    url = f"{protocol}://{device}:{port}/SSConfig/webresources/stats/{report_name}"
    params = {
        "format": "json"
    }

    if not ssl_verify and args.debug:
        print(f"[{device}] -> WARN: hostname/certificate verification disabled via {args.verify_ssl} parameter.")

    if not username or not password:
        message = f"{report_name} report unavailable: VSX username/password parameter missing"
        LOGGER.error("[%s] -> %s", device, message)
        _record_error(errors, report_name, message)
        return None

    last_error = "unknown error"
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url,
                auth=HTTPBasicAuth(username, password),
                params=params,
                verify=ssl_verify,
                timeout=timeout,
            )
        except requests.RequestException as e:
            last_error = f"{type(e).__name__}: {e}"
        else:
            if args.debug:
                print(f"[{device}] -> {report_name} HTTP {response.status_code}: {len(response.content)} bytes")
                print(f"[{device}] -> {report_name} raw response:\n{response.text}")

            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    # A 200 carrying a truncated or non-JSON body (device under
                    # load, proxy error page). Keep a snippet: it is the only
                    # evidence left once the next poll overwrites the output.
                    last_error = (
                        f"invalid JSON in response ({e}); "
                        f"first 200 bytes: {response.text[:200]!r}"
                    )
                else:
                    if is_usable is None or is_usable(data):
                        return data
                    last_error = (
                        "response carried no tables "
                        f"(first 200 bytes: {response.text[:200]!r})"
                    )
            else:
                last_error = f"HTTP {response.status_code} {response.reason}"
                if response.status_code not in _RETRYABLE_STATUS:
                    break

        LOGGER.warning(
            "[%s] -> '%s' report attempt %d/%d failed: %s",
            device, report_name, attempt, attempts, last_error,
        )
        if attempt < attempts:
            time.sleep(min(2.0, 0.5 * attempt))

    message = (
        f"{report_name} report unavailable after {attempt} attempt(s) "
        f"(timeout {timeout}s): {last_error}"
    )
    LOGGER.error("[%s] -> %s", device, message)
    _record_error(errors, report_name, message)
    return None


def _observed_table_names(data):
    """Table names present in a report response, for diagnosing partial data."""
    db = data.get("mysqldump", {}).get("database", {}) if isinstance(data, dict) else {}
    tables = db.get("table")
    if not isinstance(tables, list):
        tables = db.get("table_data")
    if isinstance(tables, dict):
        tables = [tables]
    if not isinstance(tables, list):
        return []
    return [t.get("name") for t in tables if isinstance(t, dict)]


def poll_sansay_vsx(args):
    """
    Define the framework stats to return and poll the Sansay to retrieve data:
      - resource - all trunks with their ingress and egress data
      - realtime - overall VSX stats plus active trunks realtime data
      - media_server - media server statistics

    Any report that could not be fetched or did not carry the expected data
    records a reason under stats[ERRORS_KEY]; the section writers turn that
    into an explicit check result rather than an empty section.
    """

    device = args.host
    errors = {}
    stats = {ERRORS_KEY: errors}

    resource_data = fetch_sansay_json(args, "resource", errors)
    if resource_data is not None:
        trunks = process_resource_data(args, resource_data)
        if trunks is None:
            _record_error(errors, "resource", "resource report structure not recognized")
        else:
            stats["trunks"] = trunks

    realtime_data = fetch_sansay_json(args, "realtime", errors, is_usable=_has_report_tables)
    if realtime_data is not None:
        realtime_system_data, realtime_trunk_data = process_realtime_data(args, realtime_data)
        if "system_stat" in realtime_system_data:
            stats["system_stat"] = realtime_system_data["system_stat"]
        else:
            message = (
                "realtime report carried no usable system_stat row "
                f"(tables in response: {_observed_table_names(realtime_data) or 'none'})"
            )
            LOGGER.error("[%s] -> %s", device, message)
            _record_error(errors, "realtime", message)
        if "trunks" in stats:
            stats["trunks"].update(process_realtime_trunk_data(stats["trunks"], realtime_trunk_data))

    media_data = fetch_sansay_json(args, "media_server", errors)
    if media_data is not None:
        media_stats = process_media_data(args, media_data)
        if media_stats is None:
            _record_error(
                errors,
                "media_server",
                "media_server report carried no XBMediaServerRealTimeStat data",
            )
        else:
            stats["media_stats"] = media_stats

    return stats


def process_resource_data(args, data):
    device = args.host
    if data is None:
        LOGGER.error("[%s] -> unable to parse resource table from json response data: %s", device, data)
        return

    trunks = {}
    # Two API response formats have been observed across device generations:
    #   Old response: database.table (list) contains ingress_stat and gw_egress_stat
    #     entries with row data inline. No table_structure key present.
    #   New response: database.table_data (list) contains the same table entries;
    #     database.table_structure (list) carries schema definitions separately.
    #     The table key is absent entirely in the resource response.
    db = data.get("mysqldump", {}).get("database", {})
    tables = db.get("table")
    if not isinstance(tables, list):
        tables = db.get("table_data")
    if not tables:
        LOGGER.error(
            "[%s] -> unable to parse resource 'table'/'table_data' key from json response data: %s",
            device, data,
        )
        return trunks
    for table in tables:
        if not isinstance(table, dict):
            LOGGER.warning("Skipping non-dict resource table entry: %s", table)
            continue
        table_name = table.get("name")
        if table_name is None:
            LOGGER.warning("Skipping resource table entry with no name: %s", table)
            continue
        if args.debug:
            print(f"Processing entries in {table}.")

        rows = table.get("row")
        if not rows:
            LOGGER.warning("[%s] -> Skipping table '%s' with no row data.", device, table_name)
            continue
        for row in rows:
            # Convert the list dictionaries with name and content values into
            # a single dictionary with the name as key and content as value.
            fields = row.get("field")
            if not fields:
                LOGGER.warning("Skipping resource row with no field data: %s", row)
                continue
            row_dict = {field["name"]: field["content"] for field in fields}
            if "id" not in row_dict or "trunk_id" not in row_dict or "alias" not in row_dict:
                LOGGER.warning("Skipping resource row missing id/trunk_id/alias: %s", row_dict)
                continue
            recid = row_dict.pop("id")
            trunk_id = row_dict.pop("trunk_id")
            alias = row_dict.pop("alias")
            if args.debug:
                print(f"[{device}] -> Processing row data {row}")
                print(f"[{device}] -> Conversion to {row_dict=}")

            # If the trunk ID isn't in the stats, add it.
            if trunk_id not in trunks.keys():
                if args.debug:
                    print(f"[{device}] -> {trunk_id} not found in stats table.")
                trunks[trunk_id] = {}
                trunks[trunk_id]["recid"] = recid
                trunks[trunk_id]["alias"] = alias
                if args.debug:
                    print(f"[{device}] -> Created entry for {trunks[trunk_id]} with alias {trunks[trunk_id]['alias']}.")

            # If table name isn't in dictionary keys, add it to separate ingress and egress stats.
            if table_name not in trunks[trunk_id].keys():
                if args.debug:
                    print(f"[{device}] -> {table} not found in stats trunks table.")
                trunks[trunk_id][table_name] = row_dict
                if args.debug:
                    print(f"[{device}] -> Created key for {table_name} and value of metrics: {row_dict}.")

    if args.debug:
        print(f"resource {trunks=}")
    return trunks


def process_realtime_data(args, data):
    device = args.host
    if data is None:
        LOGGER.error("[%s] -> unable to parse realtime table from json response data: %s", device, data)
        return

    # Two API response formats have been observed across device generations:
    #   Old response: database.table (list) contains system_stat (single row),
    #     gw_realtime_stat (always empty), and XBResourceRealTimeStatList (empty
    #     when no active sessions; rows keyed by trunkId when sessions are active,
    #     with fields: trunkId, fqdn, numOrig, numTerm, cps, numPeak, totalCLZ,
    #     numCLZCps, totalLimit, cpsLimit).
    #   New response: database.table_data (list) contains system_stat and
    #     gw_realtime_stat. XBResourceRealTimeStatList is absent from table_data;
    #     database.table is a stray single dict {"name": "XBResourceRealTimeStatList"}
    #     and is NOT a list. When new response devices have active sessions,
    #     gw_realtime_stat rows are expected to appear in table_data with fields:
    #     orig_tid, orig_ip, term_tid, term_ip, num_active_session,
    #     peak_active_session, active_cps. Field mapping to the existing realtime
    #     stat structure is a known gap pending capture from a live device under load.
    db = data.get("mysqldump", {}).get("database", {})
    tables = db.get("table")
    if not isinstance(tables, list):
        tables = db.get("table_data")
    if not tables:
        LOGGER.error(
            "[%s] -> unable to parse realtime 'table'/'table_data' key from json response data: %s",
            device, data,
        )
        return {}, {}
    table_count = 0
    system_stat = {}
    trunk_realtime_data = {}
    for table in tables:
        if not isinstance(table, dict):
            LOGGER.warning("Skipping non-dict table entry: %s", table)
            continue
        table_name = table.get("name")
        if table_name is None:
            LOGGER.warning("Skipping realtime table entry with no name: %s", table)
            continue
        table_count += 1
        if args.debug:
            print(f"[{device}] -> processing table #{table_count} '{table_name}' stats from json response data.")
        if table_name == "system_stat":
            row = table.get("row")
            fields = row.get("field") if isinstance(row, dict) else None
            if not fields:
                LOGGER.warning("Skipping system_stat table with no row/field data: %s", table)
                continue
            row_dict = {field["name"]: field["content"] for field in fields}
            system_stat[table_name] = row_dict
        elif table_name == "XBResourceRealTimeStatList":
            # Fetch the row value and if it's not present, return an empty list.
            # This happens due to the device only sending active trunks.
            rows = table.get("row", None)
            if rows:
                for row in rows:
                    fields = row.get("field")
                    if not fields:
                        LOGGER.warning("Skipping realtime row with no field data: %s", row)
                        continue
                    realtime_row_dict = {fieldrow["name"]: fieldrow["content"] for fieldrow in fields}
                    # Ignore realtime trunk data that has the FQDN noted as a group
                    if realtime_row_dict.get("fqdn") == "Group":
                        continue
                    trunk_id = realtime_row_dict.get("trunkId")
                    if trunk_id is None:
                        LOGGER.warning("Skipping realtime row with no trunkId: %s", realtime_row_dict)
                        continue
                    trunk_realtime_data[trunk_id] = realtime_row_dict
    return system_stat, trunk_realtime_data


def process_realtime_trunk_data(trunks, realtime_data):
    """
    Add a realtime_stat value to every trunk updating any with
    realtime_data provided otherwise default to 0 for the polling
    interval.
    """

    for trunk in trunks.keys():
        trunks[trunk]["realtime_stat"] = {}
        trunks[trunk]["realtime_stat"]["numOrig"] = realtime_data.get(trunk, {}).get("numOrig", 0)
        trunks[trunk]["realtime_stat"]["numTerm"] = realtime_data.get(trunk, {}).get("numTerm", 0)
        trunks[trunk]["realtime_stat"]["cps"] = realtime_data.get(trunk, {}).get("cps", 0)
        trunks[trunk]["realtime_stat"]["numPeak"] = realtime_data.get(trunk, {}).get("numPeak", 0)
        trunks[trunk]["realtime_stat"]["totalCLZ"] = realtime_data.get(trunk, {}).get("totalCLZ", 0)
        trunks[trunk]["realtime_stat"]["numCLZCps"] = realtime_data.get(trunk, {}).get("numCLZCps", 0)
        trunks[trunk]["realtime_stat"]["totalLimit"] = realtime_data.get(trunk, {}).get("totalLimit", 0)
        trunks[trunk]["realtime_stat"]["cpsLimit"] = realtime_data.get(trunk, {}).get("cpsLimit", 0)

    return trunks


def process_media_data(args, media_data):
    device = args.host
    if media_data is None:
        LOGGER.error("[%s] -> unable to parse XBMediaServerRealTimeStat from jsondata: %s", device, media_data)
        return
    stat_list = media_data.get("XBMediaServerRealTimeStatList")
    if not isinstance(stat_list, dict):
        LOGGER.error(
            "[%s] -> unexpected media server response structure "
            "(XBMediaServerRealTimeStatList=%r): %s", device, stat_list, media_data,
        )
        return None
    media_servers = stat_list.get("XBMediaServerRealTimeStat")
    if media_servers is None:
        LOGGER.error("[%s] -> unable to parse 'XBMediaServerRealTimeStat' key from jsondata: %s", device, media_data)
        return None
    return media_servers


def _section_error(args, stats, report_name):
    """
    Build the payload for a section whose source report is unavailable.

    The reason recorded by poll_sansay_vsx names the actual failure (timeout,
    HTTP status, malformed body) instead of leaving the check plug-in to report
    a bare "No data from agent".
    """
    reason = stats.get(ERRORS_KEY, {}).get(report_name) if isinstance(stats, dict) else None
    message = reason or f"{report_name} report returned no data"
    LOGGER.error("[%s] -> %s", args.host, message)
    return {AGENT_ERROR_KEY: message}


def process_media_stats(args, stats):
    if "media_stats" not in stats:
        # Media is a list section; wrap the error so the payload type holds.
        return [_section_error(args, stats, "media_server")]
    return stats["media_stats"]


def process_trunk_stats(args, stats):
    if "trunks" not in stats:
        return _section_error(args, stats, "resource")

    for trunk, data in stats["trunks"].items():
        default_stats = {
            'ingress': {
                'avg_postdial_delay': 0,
                'avg_call_duration': 0,
                'failed_call_ratio': 0,
                'answer_seize_ratio': 0,
            },
            'egress': {
                'avg_postdial_delay': 0,
                'avg_call_duration': 0,
                'failed_call_ratio': 0,
                'answer_seize_ratio': 0,
            },
            'realtime': {
                'origination_sessions': 0,
                'origination_utilization': 0,
                'termination_sessions': 0,
                'termination_utilization': 0,
            },
        }
        calculated_stats = default_stats

        # Realtime stat calculations for the trunk. The "realtime" report may be
        # absent for a given poll (fetch failure, timeout, or a device that
        # returned no matching trunk), so fall back to defaults instead of
        # assuming the key was populated by poll_sansay_vsx.
        realtime_stat = data.get("realtime_stat", {})
        origination_sessions = int(realtime_stat.get('numOrig', 0))
        termination_sessions = int(realtime_stat.get('numTerm', 0))
        total_limit = int(realtime_stat.get('totalLimit', 0))
        origination_utilization = termination_utilization = 0
        if total_limit:
            origination_utilization = round((origination_sessions / total_limit) * 100, 1)
            termination_utilization = round((termination_sessions / total_limit) * 100, 1)

        calculated_stats["realtime"] = {
            'origination_sessions': origination_sessions,
            'origination_utilization': origination_utilization,
            'termination_sessions': termination_sessions,
            'termination_utilization': termination_utilization,
        }
        stats["trunks"][trunk].pop("realtime_stat", None)

        # Ingress and Egress calculations for the trunk
        _direction_name_map = {"ingress_stat": "ingress", "gw_egress_stat": "egress"}
        for direction in ["ingress_stat", "gw_egress_stat"]:
            normalized = _direction_name_map[direction]
            direction_stat = data.get(direction, {})
            PDDms = float(direction_stat.get('1h_pdd_ms', 0))
            CA = float(direction_stat.get('1h_call_attempt', 0))
            CD = float(direction_stat.get('1h_call_durationSec', 0))
            FC = float(direction_stat.get('1h_call_fail', 0))
            CAns = float(direction_stat.get('1h_call_answer', 0))

            if CA > 0:
                calculated_stats[normalized] = {
                    'avg_postdial_delay': round((PDDms / CA) / 1000, 1),
                    'avg_call_duration': round(CD / CA, 1),
                    'failed_call_ratio': round((FC / CA) * 100, 1),
                    'answer_seize_ratio': round((CAns / CA) * 100, 1),
                }
            stats["trunks"][trunk].pop(direction, None)

        stats["trunks"][trunk]["calculated_stats"] = calculated_stats
    return stats["trunks"]


def process_system_stats(args, stats):
    if "system_stat" not in stats:
        return _section_error(args, stats, "realtime")
    return stats["system_stat"]


def agent_sansay_vsx_main(args: Args) -> int:
    device = args.host
    if args.debug:
        print(f'DEBUG: {args.host =}')
        print(f'DEBUG: {args.user =}')
        print(f'DEBUG: {args.password =}')
        print(f'DEBUG: {args.debug =}')
        print(f"DEBUG: {type(device)}\n{device =}")

    stats = poll_sansay_vsx(args)

    with SectionWriter("sansay_vsx_media") as writer:
        writer.append_json(process_media_stats(args, stats))
    with SectionWriter("sansay_vsx_trunks") as writer:
        writer.append_json(process_trunk_stats(args, stats))
    with SectionWriter("sansay_vsx_system") as writer:
        writer.append_json(process_system_stats(args, stats))

    return 0


def main() -> int:
    """Main entry point to be used"""
    return special_agent_main(parse_arguments, agent_sansay_vsx_main)
