#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-

# License: GNU General Public License v2


import sys
import urllib.parse
from collections.abc import Iterable, Sequence
import requests
import cmk.utils.password_store
from cmk.special_agents.v0_unstable.argument_parsing import (
    Args,
    create_default_argument_parser
)
from cmk.special_agents.v0_unstable.agent_common import (
    SectionManager,
    SectionWriter,
    special_agent_main,
)


class SansayVSXConnection:
    def __init__(
        self,
        *,
        host: str,
        protocol: str,
        port: int,
        user: str,
        password: str,
        verify_ssl: bool
    ) -> None:
        self._base_url = f"{protocol}://{host}:{port}"
        self._user = user
        self._password = password
        self._session = requests.Session()
        # we cannot use self._session.verify because it will be overwritten by
        # the REQUESTS_CA_BUNDLE env variable
        # self._verify_ssl = verify_ssl
        ## TODO Figure out why this isn't working to allow dynamic disabling.
        print(f"{verify_ssl=}")
        self._verify_ssl = False

    def get(self, endpoint: str) -> str | None:
        if not self._verify_ssl:
            requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        try:
            # we must provide the verify keyword to every individual request call!
            url = urllib.parse.urljoin(self._base_url, endpoint)
            # print(f"{url=}")
            response = self._session.get(
                url,
                verify=self._verify_ssl,
                auth=(self._user, self._password),
                params={
                    "format": "json"
                }
            )
        except requests.exceptions.RequestException as e:
            sys.stderr.write(f"ERROR while connecting to {url}: {e}\n")
            return None

        if response.status_code != 200:
            sys.stderr.write(
                f"ERROR while processing request [{response.status_code}]: {response.reason}\n"
            )
        try:
            return response.json()
        except ValueError:
            sys.stderr.write(f"ERROR: Response is not valid JSON: {response.text}\n")
            return None


def parse_arguments(argv: Sequence[str] | None) -> Args:
    """Parse arguments needed to construct an URL and for connection conditions"""
    sections = [
        "media_server",
        "realtime",
        "resource",
    ]

    parser = create_default_argument_parser(description=__doc__)
    parser.add_argument(
        "-u",
        "--user",
        default=None,
        help="Username for Sansay VSX Login",
        required=True
    )
    group = parser.add_mutually_exclusive_group(
        required=True
    )
    group.add_argument(
        "--password",
        default=None,
        help="Password for Sansay VSX Login. Preferred over --password-id",
    )
    group.add_argument(
        "--password-id",
        default=None,
        help="Password store reference to the password for Sansay VSX login",
    )
    parser.add_argument(
        "--protocol",
        default="https",
        help="Use 'http' or 'https' (default=https)",
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
        action="store_false",
        help=f"Optionally force SSL verification"
    )
    parser.add_argument(
        "--timeout",
        default=30,
        type=int,
        help="Timeout in seconds for a connection attempt",
    )
    parser.add_argument(
        "--retries",
        default=2,
        type=int,
        help="Number of connection retries before failing",
    )
    parser.add_argument(
        "host",
        metavar="HOSTNAME",
        help="IP address or hostname of your Sansay VSX device",
    )

    return parser.parse_args(argv)


def process_resource_stats(args, data):
    if data is None:
        print(f"[{args.host}] -> unable to parse table from json response data.\n{data}")
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
                print(f"[{args.host}] -> Processing row data {row}")
                print(f"[{args.host}] -> Conversion to {row_dict=}")
            
            # If the trunk ID isn't in the stats, add it.
            if trunk_id not in trunks.keys():
                if args.debug:
                    print(f"[{args.host}] -> {trunk_id} not found in stats table.")
                trunks[trunk_id] = {}
                trunks[trunk_id]["recid"] = recid
                trunks[trunk_id]["alias"] = alias
                if args.debug:
                    print(f"[{args.host}] -> Created entry for {trunks[trunk_id]} with alias {trunks[trunk_id]['alias']}.")

            # If table name isn't in dictionary keys, add it to separate ingress and egress stats.
            if table["name"] not in trunks[trunk_id].keys():
                if args.debug:
                    print(f"[{args.host}] -> {table} not found in stats trunks table.")
                trunks[trunk_id][table["name"]] = row_dict
                if args.debug:
                    print(f"[{args.host}] -> Created key for {table['name']} and value of metrics: {row_dict}.")

    if args.debug:
        print(f"resource {trunks=}")
    return trunks


def process_realtime_stats(args, data):
    if data is None:
        print(f"[{args.host}] -> unable to parse table from json response data.\n{data}")
        return

    tables = data["mysqldump"]["database"]["table"]
    table_count = 0
    system_stat = {}
    trunk_realtime_stats = {}
    for table in tables:
        table_count += 1
        table_name = table["name"]
        if args.debug:
            print(f"[{args.host}] -> processing table #{table_count} '{table_name}' stats from json response data.")
        if table_name == "system_stat":
            row_dict = {field["name"]: field["content"] for field in table["row"]["field"]}
            system_stat[table_name] = row_dict
        elif table_name == "XBResourceRealTimeStatList":
            # Fetch the row value and if it's not present, return an empty list.
            # This happens due to the device only sending active trunks.
            # rows = table.get("row",list())
            rows = table.get("row", None)
            if rows:
                for row in rows:
                    realtime_row_dict = {fieldrow["name"]: fieldrow["content"] for fieldrow in row["field"]}
                    ## Ignore realtime trunk data that has the FQDN noted as a group
                    if realtime_row_dict["fqdn"] != "Group":
                        trunk_realtime_stats[realtime_row_dict["trunkId"]] = {fieldrow["name"]: fieldrow["content"] for fieldrow in row["field"]}
    return system_stat, trunk_realtime_stats


def process_realtime_trunk_stats(trunks, realtime_stats):
    """
    Add a realtime_stat value to every trunk updating any with 
    realtime_stats provided otherwise default to 0 for the polling
    interval.
    """

    for trunk in trunks.keys():
        trunks[trunk]["realtime_stat"] = {}
        trunks[trunk]["realtime_stat"]["numOrig"] = realtime_stats.get(trunk, {}).get("numOrig", 0)
        trunks[trunk]["realtime_stat"]["numTerm"] = realtime_stats.get(trunk, {}).get("numTerm", 0)
        trunks[trunk]["realtime_stat"]["cps"] = realtime_stats.get(trunk, {}).get("cps", 0)
        trunks[trunk]["realtime_stat"]["numPeak"] = realtime_stats.get(trunk, {}).get("numPeak", 0)
        trunks[trunk]["realtime_stat"]["totalCLZ"] = realtime_stats.get(trunk, {}).get("totalCLZ", 0)
        trunks[trunk]["realtime_stat"]["numCLZCps"] = realtime_stats.get(trunk, {}).get("numCLZCps", 0)
        trunks[trunk]["realtime_stat"]["totalLimit"] = realtime_stats.get(trunk, {}).get("totalLimit", 0)
        trunks[trunk]["realtime_stat"]["cpsLimit"] = realtime_stats.get(trunk, {}).get("cpsLimit", 0)

    return trunks


def process_media_stats(args, media_data):
    if media_data is None:
        print(f"[{args.host}] -> unable to parse XBMediaServerRealTimeStat from jsondata: {media_data}")
        return
    media_servers = media_data["XBMediaServerRealTimeStatList"]["XBMediaServerRealTimeStat"]
    return media_servers


def agent_sansay_vsx_main(sys_argv: Sequence[str] | None = None) -> int:
    """
    Define the framework stats to return and poll the Sansay to retrieve data:
      - resource - all trunks with their ingress and egress data
      - realtime - overall VSX stats plus active trunks realtime data
      - media_server - media server statistics
    """
    stats = {
        "media_stats": {},
        "system_stat": {},
        "trunks": {},
    }
    if sys_argv is None:
        cmk.utils.password_store.replace_passwords()
        sys_argv = sys.argv[1:]
    args = parse_arguments(sys_argv)
    if args.debug:
        print(f"{sys_argv=}\n{args=}")
    connection = SansayVSXConnection(
        host=args.host,
        protocol=args.protocol,
        port=args.port,
        user=args.user,
        password=args.password,
        verify_ssl=args.verify_ssl,
    )

    sections = args.sections.split(",")

    for section in sections:
        if args.debug:
            print(f"Processing {section=}")
        response = connection.get(f"/SSConfig/webresources/stats/{section}")
        if response is None:
            print("error getting site response")
            return 1
        else:
            if section == "media_server":
                stats["media_stats"] = process_media_stats(args, response)
            if section == "resource":
                stats["trunks"] = process_resource_stats(args, response)
            if section == "realtime":
                realtime_system_stats, realtime_trunk_stats = process_realtime_stats(args, response)
                stats["system_stat"].update(realtime_system_stats["system_stat"])
                stats["trunks"].update(process_realtime_trunk_stats(stats["trunks"],realtime_trunk_stats))

    if args.debug:
        # sys.stdout.write("<<<sansay_vsx:sep(0)>>>")
        print("<<<sansay_vsx:sep(0)>>>")
        # sys.stdout.write(stats)
        print(stats)
        print("Writing the following data to section using SectionWrite.")
    with SectionWriter("sansay_vsx") as writer:
        writer.append_json(stats)
    return 0


def main() -> int:
    """Main entry point to be used"""
    return special_agent_main(parse_arguments, agent_sansay_vsx_main)


if __name__ == "__main__":
    sys.exit(main())
