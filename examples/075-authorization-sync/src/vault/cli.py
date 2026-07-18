"""Expose the authorization example through a CLI.

The CLI reads the unsigned demo token from a flag and maps access errors to
exit codes. A production adapter must verify its credential before creating a principal.
"""

import argparse
import sys
from collections.abc import Sequence

from pymediate.sync import Mediator, Request

from .authn import from_cli
from .core import (
    AccessError,
    DocumentNotFoundError,
    EditDocument,
    ListAllDocuments,
    ViewDocument,
    build_mediator,
)

EXIT_OK = 0
EXIT_ACCESS_DENIED = 13
EXIT_NOT_FOUND = 3


def send_as_cli(mediator: Mediator, request: Request[object]) -> int:
    """Dispatch and translate a domain denial into an exit code."""
    try:
        result = mediator.send(request)
    except AccessError as err:
        print(f"denied: {err}", file=sys.stderr)
        return EXIT_ACCESS_DENIED
    except DocumentNotFoundError as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_NOT_FOUND
    print(result)
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``--token`` plus a subcommand and dispatch through the core."""
    parser = argparse.ArgumentParser(prog="vault", description="Vault CLI over the same core.")
    parser.add_argument("--token", help="unsigned demo token: 'id;roles;claims'")
    sub = parser.add_subparsers(dest="command", required=True)

    view_parser = sub.add_parser("view", help="read a document")
    view_parser.add_argument("doc_id", type=int)

    sub.add_parser("list", help="list all documents (admin)")

    edit_parser = sub.add_parser("edit", help="edit a document (owner)")
    edit_parser.add_argument("doc_id", type=int)
    edit_parser.add_argument("body")

    args = parser.parse_args(argv)
    principal = from_cli(args.token)
    mediator = build_mediator()

    if args.command == "view":
        return send_as_cli(mediator, ViewDocument(doc_id=args.doc_id, principal=principal))
    if args.command == "list":
        return send_as_cli(mediator, ListAllDocuments(principal=principal))
    return send_as_cli(
        mediator, EditDocument(doc_id=args.doc_id, new_body=args.body, principal=principal)
    )


def run() -> None:
    """Console-script entry point (``uv run vault``)."""
    sys.exit(main())


if __name__ == "__main__":
    run()
