"""FastWS framework. Auto-documentation WebSockets using AsyncAPI around FastAPI."""

__version__ = "0.1.7"

from .application import Client as Client  # type: ignore
from .application import FastWS as FastWS  # type: ignore
from .docs import get_asyncapi as get_asyncapi  # type: ignore
from .docs import get_asyncapi_html as get_asyncapi_html  # type: ignore
from .routing import Message as Message  # type: ignore
from .routing import Operation as Operation  # type: ignore
from .routing import OperationRouter as OperationRouter  # type: ignore
