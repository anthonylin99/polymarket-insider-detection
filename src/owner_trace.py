"""
owner_trace.py
--------------
Minimal public Polygon node owner trace for a Polymarket proxy wallet.

Polymarket proxy wallets expose a Gnosis Safe-compatible getOwners() method.
This script calls it over a public Polygon node and writes a small JSON
artifact for the report. It does not require an Etherscan key and does not
attempt a full funder graph.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
DEFAULT_PROXY = "0xee50a31c3f5a7c77824b12a941a54388a2827ed6"
GET_OWNERS_SELECTOR = "0xa0e67e2b"
POLYGON_NODES = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
]


def polygon_node_call(url: str, method: str, params: list) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


def decode_address_array(hex_data: str) -> list[str]:
    if not hex_data or hex_data == "0x":
        return []
    raw = hex_data[2:] if hex_data.startswith("0x") else hex_data
    # ABI dynamic array: offset, length, then one 32-byte word per address.
    if len(raw) < 128:
        return []
    count = int(raw[64:128], 16)
    owners = []
    pos = 128
    for _ in range(count):
        word = raw[pos:pos + 64]
        owners.append("0x" + word[-40:].lower())
        pos += 64
    return owners


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--out", default=str(DATA / "owner_trace.json"))
    args = ap.parse_args()

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "proxy_wallet": args.proxy.lower(),
        "method": "Called the getOwners() selector 0xa0e67e2b through a public Polygon node.",
        "owner_wallets": [],
        "polygon_node_endpoint": "",
        "errors": [],
        "notes": [
            "This is owner attribution for the Polymarket proxy wallet only.",
            "A full funder graph still requires an explorer key or indexed transaction dataset.",
        ],
    }

    for polygon_node in POLYGON_NODES:
        try:
            code = polygon_node_call(polygon_node, "eth_getCode", [args.proxy, "latest"])["result"]
            owners_hex = polygon_node_call(
                polygon_node,
                "eth_call",
                [{"to": args.proxy, "data": GET_OWNERS_SELECTOR}, "latest"],
            )["result"]
            owners = decode_address_array(owners_hex)
            result.update({
                "polygon_node_endpoint": polygon_node,
                "contract_code_present": bool(code and code != "0x"),
                "owner_wallets": owners,
                "polygonscan_proxy_url": f"https://polygonscan.com/address/{args.proxy.lower()}",
                "polygonscan_owner_urls": [f"https://polygonscan.com/address/{owner}" for owner in owners],
            })
            break
        except Exception as exc:  # public nodes can be flaky; preserve the failure.
            result["errors"].append({"polygon_node_endpoint": polygon_node, "error": str(exc)})

    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    return 0 if result["owner_wallets"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
