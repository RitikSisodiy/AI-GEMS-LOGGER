import time
import json, types
from .handlers.log_handlers import log_global, log_global_request_data_exceptions
from datetime import datetime
from django.conf import settings
# List of URL paths to be logged



# Generator function to process data and yield results
def custom_streaming_content(self, func, iterator):
    for data in iterator:
        yield func(data)
    self.callback_func(self.request_data, self.streamd_li, self.request_log_data)


# Custom make_bytes function to handle byte conversion and JSON parsing
def custom_make_bytes(self, value):
    res = None

    if isinstance(value, (bytes, memoryview)):
        res = bytes(value)
    elif isinstance(value, str):
        res = bytes(value.encode(self.charset))
    else:
        res = str(value).encode(self.charset)

    try:
        decoded_data = res.decode('utf-8')
        json_data = decoded_data.split(': ', 1)[1]
        json_data = json.loads(json_data)
        text = json_data.get("response", "")
        self.streamd_li["response_type"] = self.streamd_li.get("response_type", json_data.get("response_type"))
        self.streamd_li["response"] += text
        if json_data.get("end_stream"):
            self.streamd_li["redirect_keyword"] = json_data.get("redirect_keyword", "")
    except Exception as e:
        log_global_request_data_exceptions(
            {"message": "Unable to json dump the response of the request"}, e
        )

    return res


# Middleware class for logging requests and responses
class SaveRequest:
    def __init__(self, get_response):
        self.get_response = get_response
        self.prefixs =  settings.ALLOWED_LOG_PREFIX # URL prefixes to log

    # Fetch request body
    @staticmethod
    def get_request_body(request, response):
        try:
            request_body = ["%s: %s" % (k, v) for k, v in request.POST.items()]
        except Exception as e:
            request_body = None
            log_global_request_data_exceptions(
                {"message": "Unable to fetch request.POST.items() during middleware operations"},
                e,
            )

        if not request_body:
            try:
                request_body = str(response.renderer_context["request"].data)
            except Exception as e:
                log_global_request_data_exceptions(
                    {"message": "Unable to perform str(response.renderer_context['request'].data) to get request body"},
                    e,
                )
                request_body = json.dumps(["error"])

        return request_body

    # Process and log request response
    @staticmethod
    def get_request_response(request, response, request_log={}, callback=None):
        if hasattr(response, "streaming_content"):
            response.streamd_li = {
                "response": ""  # inicial value
            }
            response.request_data = request
            response.response_data = response
            response.callback_func = callback
            response.request_log_data = request_log
            response.streaming_content = custom_streaming_content(response,
                                                                  types.MethodType(custom_make_bytes, response),
                                                                  response.streaming_content)
            return response.streaming_content
        else:
            response_body = response.content

        if callback:
            callback(request, response_body, request_log)

        return response_body

    # Log response data
    def log_response(self, request, response_body, request_log):
        request_log["body_response"] = response_body

        if not request.user.is_anonymous:
            request_log["authorized_username"] = request.user.username
            request_log["token_passed"] = request.META.get("HTTP_AUTHORIZATION")


        log_global(request_log)

    # Middleware entry point
    def __call__(self, request):
        _t = time.time()  # Calculate execution time
        response = self.get_response(request)
        _t = int((time.time() - _t) * 1000)

        # Skip logging if URL doesn't match prefixes
        if not any(request.get_full_path().startswith(prefix) for prefix in self.prefixs):
            return response

        request_log = {
            "endpoint": request.get_full_path(),
            "response_code": response.status_code,
            "method": request.method,
            "remote_address": self.get_client_ip(request),
            "exec_time": _t,
            "body_request": self.get_request_body(request, response),
            "body_response": {},
        }

        self.get_request_response(request, response, request_log, self.log_response)
        return response

    # Get client's IP address
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            _ip = x_forwarded_for.split(",")[0]
        else:
            _ip = request.META.get("REMOTE_ADDR")
        return _ip