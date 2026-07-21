"""Per-checker expected diagnostics for the errors/ snippet corpus.

Each errors/ snippet exists to prove that a specific typing mistake is caught.
This table pins *which* diagnostic each checker must raise for each snippet, so
a checker upgrade that silently stops catching a case fails the suite instead
of passing vacuously. Keys are snippet file stems.

Both checkers run the same shared corpus (tests/typing/snippets/); only the
expected diagnostic identifiers differ, because mypy error codes and pyright
rule names have no 1:1 mapping.
"""

# mypy error codes (the `[code]` suffix in mypy output) per errors/ snippet.
EXPECTED_MYPY_CODES: dict[str, set[str]] = {
    "async_missing_await_on_send": {"unused-coroutine"},
    "async_pipeline_missing_await": {"attr-defined"},
    "async_wrong_response_attribute": {"attr-defined"},
    "mediator_send_wrong_expectation": {"assignment"},
    "notification_handler_non_notification_type_argument": {"type-var"},
    "optional_without_none_check": {"union-attr"},
    "pipeline_wrong_response_attribute": {"attr-defined"},
    "pipeline_wrong_response_type": {"assignment"},
    "publish_non_notification": {"arg-type"},
    "send_stream_request": {"arg-type"},
    "stream_chunk_wrong_type": {"assignment"},
    "stream_handler_non_stream_request_type_argument": {"type-var"},
    "stream_normal_request": {"arg-type"},
    "union_type_without_narrowing": {"union-attr"},
    "wrong_response_attribute": {"attr-defined"},
    "wrong_response_type_assignment": {"assignment"},
}

# basedpyright rule names per errors/ snippet (same rules in both checking modes).
EXPECTED_BASEDPYRIGHT_RULES: dict[str, set[str]] = {
    "async_missing_await_on_send": {"reportUnusedCoroutine"},
    "async_pipeline_missing_await": {"reportAttributeAccessIssue"},
    "async_wrong_response_attribute": {"reportAttributeAccessIssue"},
    "mediator_send_wrong_expectation": {"reportAssignmentType"},
    "notification_handler_non_notification_type_argument": {"reportInvalidTypeArguments"},
    "optional_without_none_check": {"reportOptionalMemberAccess"},
    "pipeline_wrong_response_attribute": {"reportAttributeAccessIssue"},
    "pipeline_wrong_response_type": {"reportAssignmentType"},
    "publish_non_notification": {"reportArgumentType"},
    "send_stream_request": {"reportArgumentType"},
    "stream_chunk_wrong_type": {"reportAssignmentType"},
    "stream_handler_non_stream_request_type_argument": {"reportInvalidTypeArguments"},
    "stream_normal_request": {"reportArgumentType"},
    "union_type_without_narrowing": {"reportAttributeAccessIssue"},
    "wrong_response_attribute": {"reportAttributeAccessIssue"},
    "wrong_response_type_assignment": {"reportAssignmentType"},
}

# Deliberately pinned divergence: basedpyright's "recommended" mode demotes
# reportUnusedCoroutine from error to warning severity (reportUnusedCallResult
# already fires on the same expression there). The snippet still fails in
# "standard" mode at error severity, and mypy catches it as unused-coroutine,
# so the mistake is never silent for any checker - only the severity differs.
RECOMMENDED_MODE_WARNING_ONLY: frozenset[str] = frozenset({"async_missing_await_on_send"})
