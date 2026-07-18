"""Dependency Injector markers shared by HTTP route modules."""

from typing import Annotated

from dependency_injector.wiring import Provide
from fastapi import Depends
from pymediate import Mediator

MediatorDependency = Annotated[Mediator, Depends(Provide["mediator"])]

__all__ = ["MediatorDependency"]
