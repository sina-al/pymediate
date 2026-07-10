"""Void/None responses - should pass mypy."""

from dataclasses import dataclass
from typing import override

from pymediate import Handler, Mediator, Request, Services


@dataclass
class DeleteUserRequest(Request[None]):
    user_id: int


class DeleteUserHandler(Handler[DeleteUserRequest]):
    @override
    def __call__(self, request: DeleteUserRequest) -> None:
        # Perform deletion
        pass


# Usage
provider = Services().add(DeleteUserHandler()).provider()
mediator = Mediator(provider)

request = DeleteUserRequest(user_id=1)
response = mediator.send(request)

# Response is None
result: None = response
