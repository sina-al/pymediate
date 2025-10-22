"""Void/None responses - should pass mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, SimpleResolver


@dataclass
class DeleteUserRequest(Request[None]):
    user_id: int


class DeleteUserHandler(Handler[DeleteUserRequest]):
    def __call__(self, request: DeleteUserRequest) -> None:
        # Perform deletion
        pass


# Usage
resolver = SimpleResolver()
resolver.register(DeleteUserRequest, DeleteUserHandler())
mediator = Mediator(resolver)

request = DeleteUserRequest(user_id=1)
response = mediator.send(request)

# Response is None
result: None = response
