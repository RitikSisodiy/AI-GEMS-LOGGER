
### Setting up Logging for Your  App

#### Step 1: Modify `settings.py`

In your Django project's `settings.py`, add the following configurations:

```python

# Enable or disable CloudWatch logging
ENABLE_CLOUDWATCH_LOGGING = False

# AWS CloudWatch credentials
AWS_CLOUDWATCH_CREDENTIALS = GEMS_GPT_CONFIGURATION["AWS_CLOUDWATCH_CREDENTIALS"]

# Enable outgoing logger
ENABLE_OUTGOING_LOGGER = True

# Set of directories to ignore for logging
IGNORE_LOG_DIRECTORY = set()

# Allowed log prefixes
ALLOWED_LOG_PREFIX = GEMS_GPT_CONFIGURATION["ALLOWED_LOG_PREFIX"]

# Enable logging of Globe requests
ENABLE_GLOBE_REQUEST_LOGS = True

# Number of backup log files to maintain
BACKUP_COUNT = 10` 
```
#### Step 2: Configure Middleware

Add the middleware `SaveRequest` to your Django project's middleware configuration.

```python

MIDDLEWARE = [
    # Other middleware...
    "logger_app.middleware.SaveRequest",
]
```
#### Step 3: Include Installed App

Include the `logger_app` in the list of installed apps in your `settings.py`.

```python

`INSTALLED_APPS = [
    # Other installed apps...
    "logger_app",
]
```

#### Step 4: install requirement
```
boto3==1.34.40
django-log-outgoing-requests==0.6.1
```

#### Step 5: Create Empty Log files
```
logs/outgoing_request_data_logger/outgoing_request_data_logger.log
logs/global_request_logger_exception_logger/global_request_logger_exception_logger.log
logs/global_request/global_request.log
```