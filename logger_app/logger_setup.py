from django.conf import settings
import logging.config
from django.utils.log import DEFAULT_LOGGING

def update_logging_settings():
    print("Updating logging settings...")
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {},
        "loggers": {}
    }

    if settings.ENABLE_GLOBE_REQUEST_LOGS:
        LOGGING['handlers'] = {
            **LOGGING['handlers'],
            **{
                'global_logger_log_schema': {
                    'level': 'INFO',
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': settings.BASE_DIR / 'logs/global_request/global_request.log',
                    'when': 'midnight',
                    'interval': 1,
                    'backupCount': settings.BACKUP_COUNT,
                },
                'global_request_logger_exception_logger': {
                    'level': 'INFO',
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': settings.BASE_DIR / 'logs/global_request_logger_exception_logger/global_request_logger_exception_logger.log',
                    'when': 'midnight',
                    'interval': 1,
                    'backupCount': settings.BACKUP_COUNT,
                },
            }
        }
        LOGGING['loggers'] = {
            **LOGGING['loggers'],
            **{
                'global_request_logger': {
                    'handlers': ['global_logger_log_schema'],
                    'level': 'INFO',
                },
                'global_request_logger_exception': {
                    'handlers': ['global_request_logger_exception_logger'],
                    'level': 'INFO',
                }
            }
        }
    if settings.ENABLE_OUTGOING_LOGGER:
        LOGGING['handlers'] = {
            **LOGGING['handlers'],
            **{
                'log_outgoing_requests': {
                    'level': 'DEBUG',
                    'class': 'logger_app.handlers.requests_handler.NullHandler'
                },
                'save_outgoing_requests': {
                    'level': 'DEBUG',
                    'class': 'logger_app.handlers.requests_handler.RequestOutgoingHandler',
                },
                'outgoing_request_data_logger': {
                    'level': 'DEBUG',
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': settings.BASE_DIR / 'logs/outgoing_request_data_logger/outgoing_request_data_logger.log',
                    'when': 'midnight',
                    'interval': 1,
                    'backupCount': settings.BACKUP_COUNT,
                },
            }
        }
        LOGGING['loggers'] = {
            **LOGGING['loggers'],
            **{
                'log_outgoing_requests': {
                    'handlers': ['log_outgoing_requests', 'save_outgoing_requests'],
                    'level': 'DEBUG',
                    'propagate': True,
                },
                'outgoing_request_data_logger': {
                    'handlers': ['outgoing_request_data_logger'],
                    'level': 'INFO',
                }
            }
        }
    logging.config.dictConfig({**DEFAULT_LOGGING, **LOGGING})
