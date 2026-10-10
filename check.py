# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Notify via ntfy.sh when the Hetzner EX44 becomes orderable in a location.

Mirrors configurator.js: a product is orderable in a datacenter when a key of
live_data_upfront.json contains its numeric ID and lists that datacenter.
"""
import json
import os
import sys
from pathlib import Path

import requests

PAGE = "https://www.hetzner.com/dedicated-rootserver/ex44/configurator/"
LIVE = "https://www.hetzner.com/_resources/app/data/app/live_data_upfront.json"
STATE = Path(__file__).with_name("state.json")
HEADERS = {"User-Agent": "hetzner-ex44-watcher (personal, 1 check per 5 min)"}


def fetch(url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def availability() -> dict[str, bool]:
    config = fetch(PAGE + "getServerConfig/")
    live = fetch(LIVE)
    result: dict[str, bool] = {}
    for variation in config["Variations"]["Items"]:
        limited = variation["Limited"]
        exclusive = limited["LimitedMode"] == "Exclusive"
        ids = []
        if limited["Enabled"] and limited["ProductID"]:
            ids.append(limited["ProductID"])
        if not exclusive:
            ids.append(variation["ProductID"])
        for pid in ids:
            number = pid.removeprefix("ROBOT_")
            open_dcs = {dc for key, dcs in live.items() if number in key for dc in dcs}
            for loc in variation["Locations"]:
                name = f"{variation['Name']} {loc['Name']} ({loc['Datacenter']})"
                result[name] = result.get(name, False) or loc["Datacenter"] in open_dcs
    return result


def notify(name: str) -> None:
    topic = os.environ["NTFY_TOPIC"]
    r = requests.post(
        f"https://ntfy.sh/{topic}",
        data=f"{name} is orderable".encode(),
        headers={
            "Title": "Hetzner EX44 available",
            "Click": PAGE,
            "Priority": "high",
        },
        timeout=30,
    )
    r.raise_for_status()


def main() -> int:
    current = availability()
    previous = json.loads(STATE.read_text()) if STATE.exists() else {}
    for name, ok in current.items():
        print(f"{name}: {'AVAILABLE' if ok else 'unavailable'}")
        if ok and not previous.get(name, False):
            notify(name)
            print(f"  notified: {name}")
    STATE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
