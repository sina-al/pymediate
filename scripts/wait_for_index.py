#!/usr/bin/env python3
"""Wait until an index's simple API serves a pymediate version, probing with uv itself.

The simple index is CDN-cached and can lag an upload by minutes — and a plain HTTP probe
is not enough: curl fetches the HTML (PEP 503) variant of the index while uv asks for the
JSON (PEP 691) variant via an Accept header, and the CDN caches them separately. v0.3.0
and v0.4.0 both passed a curl probe within seconds of publish and then failed resolution;
the JSON variant caught up after ~4m47s and ~2m21s respectively. Probing with uv means
success guarantees the exact client that resolves next can see the release, and
--no-cache keeps a stale miss from being replayed on later attempts.

release.yml runs this (via `poe release:wait-index`) before each index-mode examples
stage — TestPyPI and PyPI. The default 40 x 15s ceiling is ~2x the worst lag observed.
Also handy when diagnosing index lag locally:

    python3 scripts/wait_for_index.py --version 0.5.0 --index https://pypi.org/simple/
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time


def probe(version: str, index_url: str) -> bool:
    """Return True if uv can resolve pymediate==version from the index right now."""
    result = subprocess.run(
        ["uv", "pip", "compile", "-", "--index-url", index_url, "--no-cache"],
        input=f"pymediate=={version}",
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="Exact version to wait for, e.g. 0.5.0")
    parser.add_argument(
        "--index",
        default="https://test.pypi.org/simple/",
        help="Simple-API index URL to probe (default: TestPyPI)",
    )
    parser.add_argument("--attempts", type=int, default=40, help="Probe attempts (default: 40)")
    parser.add_argument(
        "--delay", type=float, default=15.0, help="Seconds between attempts (default: 15)"
    )
    args = parser.parse_args()

    for attempt in range(1, args.attempts + 1):
        if probe(args.version, args.index):
            print(f"uv resolves pymediate=={args.version} from {args.index} (attempt {attempt}).")
            return 0
        retry = f"; retrying in {args.delay:g}s" if attempt < args.attempts else ""
        print(
            f"uv cannot resolve pymediate=={args.version} from {args.index} yet "
            f"(attempt {attempt}/{args.attempts}){retry}.",
            flush=True,
        )
        if attempt < args.attempts:
            time.sleep(args.delay)

    total = args.attempts * args.delay
    print(
        f"uv never resolved pymediate=={args.version} from {args.index} within ~{total:g}s.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
