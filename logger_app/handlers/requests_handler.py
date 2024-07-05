import types
import httpx
from log_outgoing_requests.handlers import DatabaseOutgoingRequestsHandler
import logging
import time
import json
from typing import Optional, cast
from urllib.parse import urlparse
from contextlib import contextmanager
from requests import PreparedRequest, RequestException, Response
from django.utils import timezone
from datetime import datetime
from datetime import timedelta
from log_outgoing_requests.compat import format_exception
from log_outgoing_requests.typing import (
    AnyLogRecord,
    ErrorRequestLogRecord,
    RequestLogRecord,
    is_request_log_record,
)
from django.conf import settings
import traceback
from urllib3.exceptions import (
    DecodeError,
    ProtocolError,
    ReadTimeoutError,
    SSLError,
)
from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    ContentDecodingError,
)
from requests.exceptions import SSLError as RequestsSSLError
from requests.exceptions import StreamConsumedError
from requests.utils import (
    iter_slices,
    stream_decode_response_unicode,
)

logger = logging.getLogger("log_outgoing_requests")
outgoing_logger = logging.getLogger("outgoing_request_data_logger")


def iter_content(self, chunk_size=1, decode_unicode=False):
    """Iterates over the response data.  When stream=True is set on the
    request, this avoids reading the content at once into memory for
    large responses.  The chunk size is the number of bytes it should
    read into memory.  This is not necessarily the length of each item
    returned as decoding can take place.

    chunk_size must be of type int or None. A value of None will
    function differently depending on the value of `stream`.
    stream=True will read data as it arrives in whatever size the
    chunks are received. If stream=False, data is returned as
    a single chunk.

    If decode_unicode is True, content will be decoded using the best
    available encoding based on the response.
    """

    def generate():
        # Special case for urllib3.
        if hasattr(self.raw, "stream"):
            try:
                for chunk in self.raw.stream(chunk_size, decode_content=True):
                    self.stream_data += chunk
                    yield chunk
            except ProtocolError as e:
                raise ChunkedEncodingError(e)
            except DecodeError as e:
                raise ContentDecodingError(e)
            except ReadTimeoutError as e:
                raise ConnectionError(e)
            except SSLError as e:
                raise RequestsSSLError(e)
        else:
            # Standard file-like object.
            while True:
                chunk = self.raw.read(chunk_size)
                if not chunk:
                    break
                self.stream_data += chunk
                yield chunk
        self._content_consumed = True
        if self.callback:
            self.callback(self)

    if self._content_consumed and isinstance(self._content, bool):
        raise StreamConsumedError()
    elif chunk_size is not None and not isinstance(chunk_size, int):
        raise TypeError(f"chunk_size must be an int, it is instead a {type(chunk_size)}.")
    # simulate reading small chunks of the content
    reused_chunks = iter_slices(self._content, chunk_size)

    stream_chunks = generate()

    chunks = reused_chunks if self._content_consumed else stream_chunks

    if decode_unicode:
        chunks = stream_decode_response_unicode(chunks, self)

    return chunks



@contextmanager
def supress_errors():
    try:
        yield
    except Exception as exc:
        logger.error("Could not persist log record to DB", exc_info=exc)


class RequestsLogConfig:
    save_to_db = "yes"
    save_body = "yes"
    max_content_length = 1000000
    save_logs_enabled = True
    save_body_enabled = True


class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def iter_fun(generator_func, request):
    def iter():
        func = generator_func()
        for data in func:
            request.stream_data += data
            yield data
        if request.callback:
            request.callback(request)
    return iter


class RequestOutgoingHandler(DatabaseOutgoingRequestsHandler):
    def log_request(self, response):
        try:
            from log_outgoing_requests.utils import parse_content_type_header

            content_type, encoding = parse_content_type_header(response)
            response.kwarg["res_content_type"] = content_type
            response.kwarg["res_body_encoding"] = encoding
            timestamp = datetime.now()
            response.kwarg["res_body"] = None
            response_str = response.stream_data.decode(encoding or "utf8")
            response.kwarg["response_ms"] = int(response.elapsed.total_seconds() * 1000) if response else 0
            if content_type.lower() in ["application/json", "text/event-stream"]:
                try:
                    if response_str and response_str[:6] == "data: ":
                        stream_data_li = response_str.split("\n\n")
                        for stream in stream_data_li:
                            stream_json = json.loads(stream[6:])
                            if not stream_json.get("choices"):
                                continue
                            if not response.kwarg["res_body"] and stream_json["choices"][0].get("delta", {}).get(
                                    "content", {}):
                                response.kwarg["res_body"] = stream_json
                            elif not stream_json["choices"][0].get("finish_reason") and response.kwarg["res_body"]:
                                response.kwarg["res_body"]["choices"][0]["delta"]["content"] += stream_json["choices"][
                                    0
                                ]["delta"]["content"]
                            elif stream_json["choices"][0].get("finish_reason"):
                                break
                            else:
                                continue
                    else:
                        response.kwarg["res_body"] = json.loads(response_str)
                except Exception as e:
                    print("OUTGOING-LOGGING-ERROR : ", traceback.format_exception(type(e), e, e.__traceback__))
                    response.kwarg["res_body"] = response_str
            if not response.kwarg["res_body"]:
                response.kwarg["res_body"] = response_str
            outgoing_logger.info(
                f"REQUESTS-HANDLER || {response.kwarg['temp_token']} || {timestamp} || {json.dumps(response.kwarg)}"
            )
        except Exception as e:
            print("OUTGOING-LOGGING-ERROR : ", traceback.format_exception(type(e), e, e.__traceback__))

    def process_request(self, response, kwarg):
        if isinstance(response, httpx.Response):
            response.iter_bytes = iter_fun(response.iter_bytes, response)
            response.callback = self.log_request
        else:
            response.iter_content = types.MethodType(iter_content, response)
            response.callback = self.log_request
        response.stream_data = b""
        response.kwarg = kwarg

    @supress_errors()
    def emit(self, record: AnyLogRecord):
        if not settings.ENABLE_OUTGOING_LOGGER:
            return
        from .utils import process_body

        # skip requests not coming from the library requests
        if not record or not is_request_log_record(record):
            return

        config = RequestsLogConfig()
        assert isinstance(config, RequestsLogConfig)
        if not config.save_logs_enabled:
            return

        # Python 3.10 TypeGuard can be useful here
        record = cast(RequestLogRecord, record)
        # check if we're dealing with success or error state
        exception = record.exc_info[1] if record.exc_info else None
        if (response := getattr(record, "res", None)) is not None:
            # we have a response - this is the 'happy' flow (connectivity is okay)
            record = cast(RequestLogRecord, record)
            request = record.req
        elif isinstance(exception, RequestException):
            record = cast(ErrorRequestLogRecord, record)
            # we have an requests-specific exception
            request: Optional[PreparedRequest] = exception.request
            response: Optional[Response] = exception.response  # likely None
        else:  # pragma: no cover
            logger.debug("Received log record that cannot be handled %r", record)
            return
        temp_token = "NO_TOKEN"
        scrubbed_req_headers = request.headers.copy() if request else {}
        if "Authorization" in scrubbed_req_headers:
            temp_token = "..." + scrubbed_req_headers["Authorization"][-10:]
            scrubbed_req_headers["Authorization"] = "***hidden***"
        parsed_url = urlparse(str(request.url)) if request else None

        # ensure we have a timezone aware timestamp. time.time() is platform dependent
        # about being UTC or a local time. A robust way is checking how many seconds ago
        # this record was created, and subtracting that from the current tz aware time.
        time_delta_logged_seconds = time.time() - record.created
        timestamp = timezone.now() - timedelta(seconds=time_delta_logged_seconds)
        processed_request_body = process_body(request, config)

        if processed_request_body.content_type == "application/json":
            try:
                req_body = json.loads(processed_request_body.content.decode(processed_request_body.encoding))
            except Exception:
                req_body = processed_request_body.content.decode(processed_request_body.encoding)
        else:
            req_body = processed_request_body.content.decode(processed_request_body.encoding)

        kwargs = {
            "timestamp": f"{timestamp}",
            "status_code": response.status_code,
            "url": str(request.url) if request else "(unknown)",
            "hostname": parsed_url.netloc if parsed_url else "(unknown)",
            "params": parsed_url.params if parsed_url else "(unknown)",
            "method": request.method if request else "(unknown)",
            "req_headers": self.format_headers(scrubbed_req_headers),
            "req_content_type": processed_request_body.content_type,
            "req_body_encoding": processed_request_body.encoding,
            "req_body": req_body,
            "res_headers": self.format_headers(response.headers if response else {}),
            "trace": "\n".join(format_exception(exception)) if exception else "",
            "temp_token": temp_token,
        }
        self.process_request(response, kwargs)
