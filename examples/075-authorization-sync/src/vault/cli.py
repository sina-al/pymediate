"""CLI edge: the *same* core and the *same* authorization, behind a ``--token`` flag.

This is the payoff of putting identity in the request and authorization in the core: the CLI
reuses every behavior and the in-handler ownership check unchanged. Only two things differ
from the HTTP edge — where the principal comes from (a flag, not a header) and how a denial is
reported (an exit code, not a 403).
"""

import argparse
import sys
from collections.abc import Sequence

from pymediate.sync import Mediator, Request

from .authn import from_cli
from .core import (
    AuthorizationError,
    DocumentNotFoundError,
    EditDocument,
    ListAllDocuments,
    ViewDocument,
    build_mediator,
)

EXIT_OK = 0
EXIT_FORBIDDEN = 13
EXIT_NOT_FOUND = 3


def send_as_cli(mediator: Mediator, request: Request[object]) -> int:
    """Dispatch and translate a domain denial into an exit code."""
    try:
        result = mediator.send(request)
    except AuthorizationError as err:
        print(f"denied: {err}", file=sys.stderr)
        return EXIT_FORBIDDEN
    except DocumentNotFoundError as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_NOT_FOUND
    print(result)
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``--token`` plus a subcommand and dispatch through the core."""
    parser = argparse.ArgumentParser(prog="vault", description="Vault CLI over the same core.")
    parser.add_argument("--token", help="fake auth token: 'id;roles;claims'")
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
