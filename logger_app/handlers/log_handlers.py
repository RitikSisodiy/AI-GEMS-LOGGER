import logging
from datetime import datetime
import json
import traceback

logger = logging.getLogger('global_request_logger')
exception_logger = logging.getLogger('global_request_logger_exception')


def log_global(data):
    timestamp = datetime.now()
    try:
        logger.info(f"GLOBAL  ||  {timestamp}  ||  {json.dumps(data)}")
    except:
        logger.info(f"GLOBAL  ||  {timestamp}  ||  {data}")


def log_global_request_data_exceptions(data, e):
    timestamp = datetime.now()
    try:
        exception_logger.info(f"GLOBAL-REQUEST-DATA-EXCEPTION  ||  {timestamp}  ||  {json.dumps(data)}  || "
                              f"{json.dumps(traceback.format_exception(type(e), e, e.__traceback__))}")
    except:
        exception_logger.info(f"GLOBAL-REQUEST-DATA-EXCEPTION  ||  {timestamp}  ||  {data}  ||  "
                              f"{str(traceback.format_exception(type(e), e, e.__traceback__))}")
