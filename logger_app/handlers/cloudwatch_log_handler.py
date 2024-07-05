import time
import logging
import socket
import subprocess
from botocore.exceptions import ClientError
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from threading import Thread
from django.conf import settings
from logger_app.handlers.log_filters import GunicornLogFilter
from logger_app.dispatcher import ServiceDispatcher

LOG_GROUP = settings.AWS_CLOUDWATCH_CREDENTIALS["LOG_GROUP"]
idle_threshold_seconds = 2
machine_name = f"{socket.gethostname()}"
log_directory = "logs"  # Set your log directory
ignore_log_directory = settings.IGNORE_LOG_DIRECTORY

ignore_log_lines = {"info_gunicorn_access": GunicornLogFilter}
# Create the logger
logger = logging.getLogger("api_runtime_exception_logger")

# Create the formatter
formatter = logging.Formatter("%(asctime)s : %(levelname)s - %(message)s")

handler = logging.StreamHandler()
handler.setFormatter(formatter)


def create_log_stream_if_not_exists(log_stream_name):
    response = ServiceDispatcher.get_services("cloudwatch_client").describe_log_streams(
        logGroupName=LOG_GROUP, logStreamNamePrefix=log_stream_name
    )
    log_stream_exists = any(stream["logStreamName"] == log_stream_name for stream in response.get("logStreams", []))

    # If the log stream doesn't exist, create it
    if not log_stream_exists:
        ServiceDispatcher.get_services("cloudwatch_client").create_log_stream(
            logGroupName=LOG_GROUP, logStreamName=log_stream_name
        )


# Function to send log entries to CloudWatch
def send_logs_to_cloudwatch(log_stream_name, log_entries):
    try:
        response = ServiceDispatcher.get_services("cloudwatch_client").put_log_events(
            logGroupName=LOG_GROUP, logStreamName=log_stream_name, logEvents=log_entries
        )
        return response["nextSequenceToken"]
    except ServiceDispatcher.get_services("cloudwatch_client").exceptions.ResourceNotFoundException as error:
        create_log_stream_if_not_exists(log_stream_name)
        send_logs_to_cloudwatch(log_stream_name, log_entries)
    except ClientError as e:
        logger.info(f"Error sending log entries to CloudWatch: {str(e)}")

    return None


# Function to tail a log file and send log entries to CloudWatch
def tail_and_send_logs(log_file_path, log_stream_name, batch_size=100):
    global tail_process
    log_entries = []
    last_activity_time = time.time()
    tail_thread = True
    while tail_thread:
        try:
            tail_process = subprocess.Popen(
                ["tail", "-n", "0", "-F", log_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            handler = False
            if ignore_log_lines.get(log_stream_name):
                handler = ignore_log_lines[log_stream_name]()
            for line in tail_process.stdout:
                line = line.strip()
                if handler:
                    line = handler.run(line)
                if line:
                    log_entry = {
                        "timestamp": int(time.time() * 1000),
                        "message": f"{machine_name} >>>> {line}",
                    }
                    log_entries.append(log_entry)
                if len(log_entries) >= batch_size or (
                    (time.time() - last_activity_time) >= idle_threshold_seconds and log_entries
                ):
                    last_activity_time = time.time()
                    send_logs_to_cloudwatch(log_stream_name, log_entries)
                    log_entries = []
        except KeyboardInterrupt:
            tail_process.kill()
            tail_process.wait()
            tail_thread = False
        except FileNotFoundError as e:
            logger.info(f"Log file not found: {str(e)}")
            # Handle the file not found error.
            open(log_file_path, "a").close()
        except Exception as e:
            logger.info(f"Error tailing log file {log_file_path}: {str(e)}")
            tail_process.kill()
            tail_process.wait()


class CloudWatchThread(Thread):
    def run(self):
        # Discover log files in the specified directory
        all_log_files = {str(path) for path in Path(log_directory).rglob("*.log")}
        # removing ignored dirs
        log_files = all_log_files.difference(ignore_log_directory)
        print(log_files)
        with ProcessPoolExecutor(max_workers=len(log_files)) as executor:
            for log_file in log_files:
                log_stream_name = log_file[log_file.rfind("/") + 1 : -4]
                if log_stream_name not in ignore_log_directory:
                    create_log_stream_if_not_exists(log_stream_name)
                    executor.submit(tail_and_send_logs, log_file, log_stream_name)
