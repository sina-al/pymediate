"""Tests for the message-design example.

These assert the design choices actually hold: validation fails at *construction* (not in a
handler), a frozen request is immutable and usable as a cache key, and the secret stays out
of the repr.
"""

from dataclasses import FrozenInstanceError

import pytest
from pymediate import Mediator

from taskboard.app import build_mediator
from taskboard.domain import TaskStore
from taskboard.handlers import SearchByTagHandler
from taskboard.messages import CreateTask, RegisterWebhook, SearchByTag


@pytest.fixture
def store() -> TaskStore:
    return TaskStore()


@pytest.fixture
def search(store: TaskStore) -> SearchByTagHandler:
    return SearchByTagHandler(store)


@pytest.fixture
def mediator(store: TaskStore, search: SearchByTagHandler) -> Mediator:
    return build_mediator(store=store, search=search)


# ---- Validation happens at construction, before dispatch ----


def test_invalid_request_fails_at_construction_not_in_a_handler() -> None:
    # No mediator, no handler — the error is raised the moment the request is built.
    with pytest.raises(ValueError, match="title cannot be empty"):
        CreateTask(title="   ")


def test_priority_out_of_range_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="priority must be between 1 and 5"):
        CreateTask(title="ok", priority=9)


def test_mixin_validation_runs_too() -> None:
    # PaginationMixin.__post_init__ runs via super() — a bad page fails at construction.
    with pytest.raises(ValueError, match="page must be >= 1"):
        SearchByTag(tag="work", page=0)


def test_post_init_normalizes_fields() -> None:
    task = CreateTask(title="  Tidy up  ")
    assert task.title == "Tidy up"  # stripped

    search = SearchByTag(tag="  WORK ")
    assert search.tag == "work"  # stripped and lowercased


# ---- Frozen: immutable, and hashable enough to be a cache key ----


def test_frozen_request_is_immutable() -> None:
    task = CreateTask(title="immutable")
    with pytest.raises(FrozenInstanceError):
        task.title = "changed"  # type: ignore[misc]


def test_equal_frozen_requests_are_equal_and_hash_equal() -> None:
    a = SearchByTag(tag="work")
    b = SearchByTag(tag="WORK")  # normalizes to the same value
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}  # collapse to one in a set — same key


async def test_frozen_request_used_as_cache_key(
    mediator: Mediator, store: TaskStore, search: SearchByTagHandler
) -> None:
    store.add("a", ("work",), 3)

    first = await mediator.send(SearchByTag(tag="work"))
    second = await mediator.send(SearchByTag(tag="work"))

    assert first == second
    assert search.hits == 1  # the second search hit the cache keyed by the request itself


# ---- Secrets stay out of the repr ----


def test_secret_is_hidden_from_repr() -> None:
    request = RegisterWebhook(url="https://example.com/hook", secret="topsecret")
    text = repr(request)
    assert "topsecret" not in text
    assert "example.com/hook" in text  # the non-secret field is still there


def test_webhook_validates_url_and_secret_at_construction() -> None:
    with pytest.raises(ValueError, match="url must be http"):
        RegisterWebhook(url="ftp://nope", secret="longenough")
    with pytest.raises(ValueError, match="secret must be at least 8"):
        RegisterWebhook(url="https://ok.com", secret="short")
