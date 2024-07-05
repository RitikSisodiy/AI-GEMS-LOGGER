from log_outgoing_requests.apps import LogOutgoingRequestsConfig
from django.conf import settings
from .dispatcher import (
    ServiceDispatcher,
    # AttributeTracker
)
def ready(LogOutgoingRequestsConfig):
    from log_outgoing_requests.log_requests import install_outgoing_requests_logging
    from .log_requests_httpx import install_outgoing_httpx_logging
    install_outgoing_requests_logging()
    install_outgoing_httpx_logging()
    from logger_app.logger_setup import update_logging_settings
    update_logging_settings()
    ServiceDispatcher()
    if settings.ENABLE_CLOUDWATCH_LOGGING:
        from .handlers.cloudwatch_log_handler import CloudWatchThread

        CloudWatchThread().start()
    print("++++++++++++++++==Logger App ready+++++++++++++++++++++++++")

LogOutgoingRequestsConfig.ready = ready