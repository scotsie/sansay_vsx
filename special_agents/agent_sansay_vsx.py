#!/usr/bin/env python3

"""
Special agent for monitoring Sansay VSX devices.
Media Server = stats/media_server
Realtime = stats/realtime
Resource = state/resource
"""

import logging
import re
from collections.abc import Sequence

import requests
from requests.auth import HTTPBasicAuth

from cmk.special_agents.v0_unstable.agent_common import SectionWriter, special_agent_main
from cmk.special_agents.v0_unstable.argument_parsing import Args, create_default_argument_parser
from cmk.utils import password_store
from pathlib import Path


LOGGER = logging.getLogger("agent_sansay_vsx")


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


def fetch_sansay_json(args, report_name):
    if args.debug:
        print(f"{args=}")
    password = None
    if args.password:
        match args.password:
            case str() if re.match(r'^[a-zA-Z0-9-]+:/[a-zA-Z0-9/_]+$', args.password):
                uuid, path = args.password.split(':')
                password = password_store.lookup(pw_file=Path(path), pw_id=uuid)
            case str() if re.match(r'^[a-zA-Z0-9]+$', args.password):
                password = args.password
            case other:
                raise TypeError(other)

    username = args.user
    device = args.host
    protocol = args.proto
    port = args.port
    ssl_verify = args.verify_ssl
    timeout = args.timeout
    # TODO for later implementation
    # sections = [args.sections.split(",")]
    # retries = args.retries

    if args.debug:
        print(f"[{device}] -> fetching Sansay VSX {report_name} stats")

    url = f"{protocol}://{device}:{port}/SSConfig/webresources/stats/{report_name}"
    params = {
        "format": "json"
    }

    if not ssl_verify and args.debug:
        print(f"[{device}] -> WARN: hostname/certificate verification disabled via {args.verify_ssl} parameter.")

    if not username or not password:
        print(f"[{device}] -> ERROR: unable to fetch Sansay report, VSX username/password parameter missing")
        return None

    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(username, password),
            params=params,
            verify=ssl_verify,
            timeout=timeout,
        )
        if ssl_verify and args.debug:
            print(f"[{device}] -> fetching Sansay VSX {report_name} stats (complete)")

        if response.status_code != 200:
            print(f"[{device}] -> ERROR: unable to fetch Sansay '{report_name}' report: {response.status_code} {response.reason}")
            # print(f"[{device}] -> ERROR: parameters used:\n    {url=}\n    {username=}\n   {password=}\n   {HTTPBasicAuth(username, password)=}\n   {params=}\n   {ssl_verify=}\n    {timeout=}")
            return None
        return response.json()
    except requests.RequestException as e:
        print(f"[{device}] -> ERROR: unable to fetch Sansay '{report_name}' report: {e}")
        return None


def poll_sansay_vsx(args):
    """
    Define the framework stats to return and poll the Sansay to retrieve data:
      - resource - all trunks with their ingress and egress data
      - realtime - overall VSX stats plus active trunks realtime data
      - media_server - media server statistics
    """

    stats = {}

    resource_data = fetch_sansay_json(args, "resource")
    if resource_data is not None:
        stats["trunks"] = process_resource_data(args, resource_data)

    realtime_data = fetch_sansay_json(args, "realtime")
    if realtime_data is not None:
        realtime_system_data, realtime_trunk_data = process_realtime_data(args, realtime_data)
        # stats["system_stat"].update(realtime_system_data["system_stat"])
        stats["system_stat"] = realtime_system_data["system_stat"]
        stats["trunks"].update(process_realtime_trunk_data(stats["trunks"], realtime_trunk_data))

    media_data = fetch_sansay_json(args, "media_server")
    if media_data is not None:
        stats["media_stats"] = process_media_data(args, media_data)

    return stats


def process_resource_data(args, data):
    device = args.host
    if data is None:
        print(f"[{device}] -> unable to parse table from json response data.\n{data}")
        return

    trunks = {}
    tables = data["mysqldump"]["database"]["table"]
    for table in tables:
        if args.debug:
            print(f"Processing entries in {table}.")

        for row in table["row"]:
            # Convert the list dictionaries with name and content values into
            # a single dictionary with the name as key and content as value.
            row_dict = {field["name"]: field["content"] for field in row["field"]}
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
            if table["name"] not in trunks[trunk_id].keys():
                if args.debug:
                    print(f"[{device}] -> {table} not found in stats trunks table.")
                trunks[trunk_id][table["name"]] = row_dict
                if args.debug:
                    print(f"[{device}] -> Created key for {table['name']} and value of metrics: {row_dict}.")

    if args.debug:
        print(f"resource {trunks=}")
    return trunks


def process_realtime_data(args, data):
    device = args.host
    if data is None:
        print(f"[{device}] -> unable to parse table from json response data.\n{data}")
        return

    tables = data["mysqldump"]["database"]["table"]
    table_count = 0
    system_stat = {}
    trunk_realtime_data = {}
    for table in tables:
        table_count += 1
        table_name = table["name"]
        if args.debug:
            print(f"[{device}] -> processing table #{table_count} '{table_name}' stats from json response data.")
        if table_name == "system_stat":
            row_dict = {field["name"]: field["content"] for field in table["row"]["field"]}
            system_stat[table_name] = row_dict
        elif table_name == "XBResourceRealTimeStatList":
            # Fetch the row value and if it's not present, return an empty list.
            # This happens due to the device only sending active trunks.
            rows = table.get("row", None)
            if rows:
                for row in rows:
                    realtime_row_dict = {fieldrow["name"]: fieldrow["content"] for fieldrow in row["field"]}
                    # Ignore realtime trunk data that has the FQDN noted as a group
                    if realtime_row_dict["fqdn"] != "Group":
                        trunk_realtime_data[realtime_row_dict["trunkId"]] = {fieldrow["name"]: fieldrow["content"] for fieldrow in row["field"]}
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
        print(f"[{device}] -> unable to parse XBMediaServerRealTimeStat from jsondata: {media_data}")
        return
    media_servers = media_data["XBMediaServerRealTimeStatList"]["XBMediaServerRealTimeStat"]
    return media_servers


def process_media_stats(args, stats):
    device = args.host
    if "media_stats" not in stats:
        print(f"[{device}] -> No media stats found in jsondata: {stats}")
        return None
    return stats["media_stats"]


def process_trunk_stats(args, stats):
    device = args.host
    if "trunks" not in stats:
        print(f"[{device}] -> No trunk stats found in jsondata: {stats}")
        return None

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

        # Realtime stat calculations for the trunk
        origination_sessions = int(data["realtime_stat"].get('numOrig', 0))
        termination_sessions = int(data["realtime_stat"].get('numTerm', 0))
        total_limit = int(data["realtime_stat"].get('totalLimit', 0))
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
        stats["trunks"][trunk].pop("realtime_stat")

        # Ingress and Egress calculations for the trunk
        for direction in ["ingress_stat", "gw_egress_stat"]:
            PDDms = float(data[direction].get('1st15mins_pdd_ms', 0))
            CA = float(data[direction].get('1st15mins_call_attempt', 0))
            CD = float(data[direction].get('1st15mins_call_durationSec', 0))
            FC = float(data[direction].get('1st15mins_call_fail', 0))
            CAns = float(data[direction].get('1st15mins_call_answer', 0))

            if CA > 0:
                calculated_stats[direction] = {
                    'avg_postdial_delay': round((PDDms / CA) / 1000, 1),
                    'avg_call_duration': round(CD / CA, 1),
                    'failed_call_ratio': round((FC / CA) * 100, 1),
                    'answer_seize_ratio': round((CAns / CA) * 100, 1),
                }
            stats["trunks"][trunk].pop(direction)

        stats["trunks"][trunk]["calculated_stats"] = calculated_stats
    return stats["trunks"]


def process_system_stats(args, stats):
    device = args.host
    if "system_stat" not in stats:
        print(f"[{device}] -> No media stats found in jsondata: {stats}")
        return
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
