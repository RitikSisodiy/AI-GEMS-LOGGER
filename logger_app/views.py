import json
from django.shortcuts import render
from django.conf import settings
from .dispatcher import ServiceDispatcher
import pandas as pd
LOG_GROUP = settings.AWS_CLOUDWATCH_CREDENTIALS["LOG_GROUP"]
from datetime import datetime, timedelta
import  time
import pytz

# AWS CloudWatch Client Configuration


def extract_logs(query_string, log_group_name, start_time, end_time, limit=10000):
    all_results = []
    next_start_time = start_time

    while next_start_time < end_time:
        query_parameters = {
            'logGroupName': log_group_name,
            'startTime': next_start_time,
            'endTime': end_time,
            'queryString': query_string,
            'limit': limit
        }

        query_response = ServiceDispatcher.get_services("cloudwatch_client").start_query(**query_parameters)
        query_id = query_response['queryId']

        while True:
            time.sleep(1)
            query_status = ServiceDispatcher.get_services("cloudwatch_client").get_query_results(queryId=query_id)
            results = query_status['results']
            all_results += results
            if query_status['status'] == 'Complete':
                if len(results) < limit:
                    next_start_time = end_time  # No more logs to fetch
                else:
                    last_timestamp_str = results[-1][0]['value']  # Assuming the first field is @timestamp
                    last_timestamp = int(
                        datetime.strptime(last_timestamp_str, '%Y-%m-%d %H:%M:%S.%f').timestamp() * 1000)
                    next_start_time = last_timestamp + 1  # Move to the next millisecond

                break
            elif query_status['status'] == 'Failed':
                raise Exception(f"Query failed: {query_status['errorMessage']}")
    return all_results
def get_global_logs(start_time,end_time):
    # start_time = int(datetime(1999, 5, 11, 0, 0, 0).timestamp()) * 1000
    # # end_time = int(datetime(2024, 6, 14, 0, 0, 0).timestamp()) * 1000
    # end_time = int((datetime.now() + timedelta(days=7)).timestamp()) * 1000
    query_string = ">>>> GLOBAL ||"
    log_group_name = LOG_GROUP
    globle_logs = extract_logs(query_string, log_group_name, start_time, end_time)
    globle_logs = [log[1]["value"] for log in globle_logs]
    globle_logs = [log for log in globle_logs if ">>>> GLOBAL " in log]
    globle_logs = [log.split("  ||  ") for log in globle_logs]
    globle_logs_df = []
    for _, timestamp, content in globle_logs:
        try:
            content = json.loads(content)
        except:
            content = eval(content)
        req_body_str = content.get("body_request", "{}")
        req_body = {}
        if req_body_str not in ['["error"]', "['error']"]:
            try:
                req_body = json.loads(req_body_str)
            except:
                try:
                    req_body = eval(req_body_str)
                except:
                    req_body = {"error": "Bad request"}
        globle_logs_df.append(
            {
                "timestamp": timestamp,
                **content,
                **req_body
            }
        )

    g_df = pd.DataFrame(globle_logs_df)
    g_df = g_df.drop_duplicates("timestamp").reset_index()
    return g_df


def fetch_logs(request):
    # Default start and end times (past 7 days to next 7 days)
    default_start_time = datetime.now() - timedelta(days=7)
    default_end_time = datetime.now()

    # Get start_time and end_time from request if available, else set default values
    start_time_str = request.GET.get('start_time')
    end_time_str = request.GET.get('end_time')

    if start_time_str and end_time_str:
        try:
            # Parse the date and time strings
            start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            # If there's an issue with the parsing, fall back to defaults
            start_time = default_start_time
            end_time = default_end_time
    else:
        start_time = default_start_time
        end_time = default_end_time

    # Fetch log entries based on start_time and end_time
    # Replace the following line with the actual log fetching logic

    gmt = pytz.timezone('GMT')
    start_time, end_time = start_time.astimezone(gmt), end_time.astimezone(gmt)
    start_time, end_time = int(start_time.timestamp()) * 1000,int(end_time.timestamp()) * 1000
    log_entries = get_global_logs(start_time,end_time)

    return render(request, 'logs/logs.html', {'logs': log_entries, 'start_time': start_time, 'end_time': end_time})
