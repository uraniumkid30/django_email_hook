import base64
import logging
from abc import ABC, ABCMeta, abstractmethod
from typing import Tuple, Union, Optional, List


import boto3
from django.conf import settings
from postmarker.core import PostmarkClient
from botocore.exceptions import ClientError
from django.template.loader import render_to_string
from django.core.mail import send_mail, EmailMultiAlternatives


class EmailEngine(metaclass=ABCMeta):
    ERRORS = []
    FROM_EMAIL = getattr("EMAIL_HOST_USER", settings, None)

    @abstractmethod
    @classmethod
    def get_configurations(cls):
        pass

    @abstractmethod
    @classmethod
    def get_email_sending_parameters(
        cls, to_email: str, from_email: str = "", **kwargs
    ):
        pass

    @abstractmethod
    @classmethod
    def __send_mail(cls, to_email: str, from_email: str = "", **kwargs):
        pass

    @classmethod
    def send_mail(cls, to_email: str, from_email: str = "", **kwargs):
        can_send_emails = cls.get_email_status()
        if can_send_emails:
            cls.__send_mail(to_email, from_email, **kwargs)
        else:
            print(f"Fix the following ERRORS : {cls.ERRORS} ")

    @staticmethod
    def get_html_message(template_path: str, template_parameters: dict = {}):
        msg_html = render_to_string(template_path, template_parameters)
        return msg_html

    @classmethod
    def __is_sufficient(cls, resource: dict = {}, marker: str = ""):
        if all(resource.values()):
            return True
        else:
            for _key in resource:
                cls.ERRORS.append(f"{_key} is missing in {marker}")
            else:
                return False

    @classmethod
    def is_configuration_sufficient(cls):
        configurations = cls.get_configuration()
        return cls.__is_sufficient(resource=configurations, marker="Settings")

    @classmethod
    def is_email_sending_parameters_sufficient(cls):
        email_sending_parameters = cls.get_email_sending_parameters()
        return cls.__is_sufficient(
            resource=email_sending_parameters, marker="Email sending parameters"
        )

    @classmethod
    def get_email_status(cls):
        cls.is_configuration_sufficient()
        cls.is_email_sending_parameters_sufficient()
        if len(cls.ERRORS):
            return False
        return True


class AWSSESEmailEngine(EmailEngine):
    @classmethod
    def get_configuration(cls):
        configurations: dict = {
            "AWS_SES_ACCESS_KEY_ID": (
                getattr(settings, "AWS_SES_ACCESS_KEY_ID", None)
                or getattr(settings, "AWS_ACCESS_KEY_ID", None)
            ),
            "AWS_SES_SECRET_ACCESS_KEY": (
                getattr(settings, "AWS_SES_SECRET_ACCESS_KEY", None)
                or getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
            ),
            "AWS_SES_REGION": (
                getattr(settings, "AWS_SES_REGION", None)
                or getattr(settings, "AWS_DEFAULT_REGION", "us-east-1")
            ),
            #             "AWS_SES_CONFIGURATION_SET_NAME": getattr(settings, "AWS_SES_CONFIGURATION_SET_NAME", None),
            #             "AWS_SES_TAGS": getattr(settings, "AWS_SES_TAGS", None),
        }

        return configurations

    @classmethod
    def get_email_sending_parameters(
        cls, to_email: str, from_email: str = "", **kwargs
    ):
        email_parameters = {
            "Source": from_email or cls.FROM_EMAIL,
            "Destination": {
                "ToAddresses": to_email
                if isinstance(to_email, list)
                else [
                    to_email,
                ],
                "CcAddresses": kwargs.get("ccs", ""),
                "BccAddresses": kwargs.get("bccs", ""),
            },
            "Message": {
                "Body": {
                    "Html": {
                        "Charset": "UTF-8",
                        "Data": kwargs.get("HtmlBody", ""),
                    }
                },
                "Subject": {
                    "Charset": "UTF-8",
                    "Data": kwargs.get("Subject", ""),
                },
            },
        }
        return email_parameters

    @staticmethod
    def get_aws_ses_client(cls):
        try:
            config = cls.get_configuration()
            access_key_id = config["AWS_SES_ACCESS_KEY_ID"]
            secret_access_key = config["AWS_SES_SECRET_ACCESS_KEY"]
            region_name = config["AWS_SES_REGION"]
            client = boto3.client(
                "ses",
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region_name,
            )
        except Exception as e:
            client = None
            print(f"{e} prevented aws ses client instantiation")
        finally:
            return client

    @classmethod
    def __send_mail(cls, to_email: str, from_email: str = "", **kwargs):
        email_parameters = cls.get_email_sending_parameters(
            to_email, from_email, **kwargs
        )
        try:
            aws_client = cls.get_aws_ses_client()
            aws_client.send_email(**email_parameters)
        except Exception as Err:
            print(f"Email Sending Error {Err}")
        else:
            print("Email Sent")


class PostmarkEmailEngine(EmailEngine):
    @classmethod
    def get_configuration(cls):
        configurations: dict = {
            "POSTMARK_API_KEY": getattr("POSTMARK_API_KEY", settings, None),
        }
        return configurations

    @classmethod
    def get_email_sending_parameters(
        cls, to_email: str, from_email: str = "", **kwargs
    ):
        email_parameters = {
            "From": from_email or cls.FROM_EMAIL,
            "To": to_email,
            "Subject": kwargs.get("Subject", ""),
            "HtmlBody": kwargs.get("HtmlBody", ""),
        }
        return email_parameters

    @staticmethod
    def get_postmark_client(cls):
        try:
            client = PostmarkClient(server_token=settings.POSTMARK_API_KEY)
        except Exception as e:
            client = None
            print(f"{e} prevented postmark client instantiation")
        finally:
            return client

    @classmethod
    def __send_mail(cls, to_email: str, from_email: str = "", **kwargs):
        email_parameters = cls.get_email_sending_parameters(
            to_email, from_email, **kwargs
        )
        try:
            postmark = PostmarkEmailEngine.get_postmark_client()
            postmark.emails.send(**email_parameters)
        except Exception as Err:
            print(f"Email Sending Error {Err}")
        else:
            print("Email Sent")


class DjangoEmailEngine(EmailEngine):
    @classmethod
    def get_configuration(cls):
        configurations: dict = {}
        return configurations

    @classmethod
    def get_email_sending_parameters(
        cls, to_email: str, from_email: str = "", **kwargs
    ):
        email_parameters = {
            "from_email": from_email or cls.FROM_EMAIL,
            "recipient_list": [
                to_email,
            ],
            "message": kwargs.get("message", ""),
            "subject": kwargs.get("subject", ""),
            "html_message": kwargs.get("html_message", ""),
        }
        return email_parameters

    @classmethod
    def __send_mail(cls, to_email: str, from_email: str = "", **kwargs):
        email_parameters = cls.get_email_sending_parameters(
            to_email, from_email, **kwargs
        )
        try:
            send_mail(**email_parameters)
        except Exception as Err:
            print(f"Email Sending Error {Err}")
        else:
            print("Email Sent")

