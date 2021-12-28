from typing import Union

import boto3
from botocore.client import BaseClient, ClientMeta
from botocore.session import Session as IDEResourceType
from deployment_helpers.constants import get_aws_credentials, get_global_config


# IDE does not understand boto3 because the types themselves are generated at runtime.  These typing
# hints gives the IDE some idea, but tbh not much.
IDEBotoClientType = Union[BaseClient, ClientMeta]

AWS_CREDENTIALS = get_aws_credentials()
GLOBAL_CONFIGURATION = get_global_config()

def _get_client(client_type):
    """ connect to a boto3 CLIENT in the appropriate type and region. """
    return boto3.client(
            client_type,
            aws_access_key_id=AWS_CREDENTIALS["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=AWS_CREDENTIALS["AWS_SECRET_ACCESS_KEY"],
            region_name=GLOBAL_CONFIGURATION["AWS_REGION"],
    )

def _get_resource(client_type):
    """ connect to a boto3 RESOURCE in the appropriate type and region. """
    return boto3.resource(
            client_type,
            aws_access_key_id=AWS_CREDENTIALS["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=AWS_CREDENTIALS["AWS_SECRET_ACCESS_KEY"],
            region_name=GLOBAL_CONFIGURATION["AWS_REGION"],
    )

def create_s3_resource() -> IDEResourceType:
    return _get_resource("s3")


def create_ec2_client() -> IDEBotoClientType:
    return _get_client('ec2')


def create_eb_client() -> IDEBotoClientType:
    return _get_client('elasticbeanstalk')


def create_iam_client() -> IDEBotoClientType:
    return _get_client('iam')


def create_rds_client() -> IDEBotoClientType:
    return _get_client('rds')


def create_batch_client() -> IDEBotoClientType:
    return _get_client('batch')


def create_s3_client() -> IDEBotoClientType:
    return _get_client('s3')


def create_sts_client() -> IDEBotoClientType:
    return _get_client('sts')


# Resources.
def create_ec2_resource() -> IDEResourceType:
    return _get_resource('ec2')


def create_iam_resource() -> IDEResourceType:
    return _get_resource('iam')
