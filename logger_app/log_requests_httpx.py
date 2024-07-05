import pdb
from contextlib import contextmanager
from httpx import Request, Response, HTTPError, Client
from typing import Any

from log_outgoing_requests import logger


def hook_httpx_logging(response: Response, *args: Any, **kwargs: Any) -> None:
    """
    A hook for httpx library in order to add extra data to the logs
    """
    # pdb.set_trace()
    request = response.request
    logger.debug(
        "Outgoing request",
        extra={
            "_is_log_outgoing_requests": True,
            "req": request,
            "res": response,
        },
    )


@contextmanager
def log_errors() -> None:
    try:
        yield
    except HTTPError as exc:
        logger.debug(
            "Outgoing request error",
            exc_info=exc,
            extra={"_is_log_outgoing_requests": True},
        )
        raise


def install_outgoing_httpx_logging() -> None:
    """
    Log all outgoing requests which are made by the httpx library during a session.
    """

    if hasattr(Client, "_lor_initial_request"):
        logger.debug(
            "Client is already patched OR has an ``_lor_initial_request`` attribute."
        )
        return

    Client._lor_initial_request = Client.send

    def new_request(self: Client, *args: Any, **kwargs: Any) -> Any:
        if hook_httpx_logging not in self.event_hooks["response"]:
            self.event_hooks["response"].append(hook_httpx_logging)
        with log_errors():
            return self._lor_initial_request(*args, **kwargs)

    Client.send = new_request
