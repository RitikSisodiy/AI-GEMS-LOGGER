from django.conf import settings
import boto3


class ServiceDispatcher:
    service_instance = {}

    def __init__(self):
        print("Loading services...")
        self.service_instance["cloudwatch_client"] = boto3.client(
            settings.AWS_CLOUDWATCH_CREDENTIALS["AWS_SERVICE_NAME"],
            region_name=settings.AWS_CLOUDWATCH_CREDENTIALS["AWS_REGION"],
            aws_access_key_id=settings.AWS_CLOUDWATCH_CREDENTIALS["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=settings.AWS_CLOUDWATCH_CREDENTIALS["AWS_SECRET_ACCESS_KEY"],
        )
        print("cloudwatch_client loaded successfully")

    # This method returns the service that has been deployed under its respective name for usage.
    @classmethod
    def get_services(cls, name):
        try:
            return cls.service_instance[name]
        except Exception as e:
            raise Exception("Service instance could not be found")
