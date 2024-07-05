import re
from django.conf import settings


class GunicornLogFilter:
    allowed_prefix = settings.ALLOWED_LOG_PREFIX

    def extract_endpoint_from_log(self, log_line):
        """
        Extract the endpoint (URL path) from a log line in Common Log Format (CLF).

        Args:
            log_line (str): The log line to extract the endpoint from.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating whether the log line
                             matches the CLF format and the extracted endpoint (or an empty string).
        """
        # Define a regular expression pattern to match the CLF format
        clf_pattern = r'^(\S+) (\S+) (\S+) \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\d+) "([^"]*)" "([^"]*)"$'

        # Use re.match to check if the log line matches the pattern
        match = re.match(clf_pattern, log_line)

        if match:
            endpoint = match.group(6)  # Extract the 6th captured group (URL path)
            return True, endpoint
        else:
            return False, ""

    def run(self, log):
        is_matched, endpoint = self.extract_endpoint_from_log(log)
        pattern = r"^(\/|\[|Not Found: \/|Execution of job)"
        if re.match(pattern, log):
            return None
        elif is_matched and not any(endpoint.startswith(prefix) for prefix in self.allowed_prefix):
            return None
        if is_matched:
            return log
        else:
            return log and f"print-statements >>> {log}"
