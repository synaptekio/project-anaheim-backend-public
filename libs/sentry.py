# NOTE: THIS FILE IS IMPORTED IN THE DJANGO CONF FILE.


from cronutils.error_handler import ErrorSentry, null_error_handler
from raven import Client as SentryClient
from raven.exceptions import InvalidDsn
from raven.transport import HTTPTransport

from config.settings import (SENTRY_DATA_PROCESSING_DSN, SENTRY_ELASTIC_BEANSTALK_DSN,
    SENTRY_JAVASCRIPT_DSN)
from constants.common_constants import RUNNING_TEST_OR_IN_A_SHELL


# when running in a shell we force sentry off and force the use of the null_error_handler


class SentryTypes:
    data_processing = "data_processing"
    elastic_beanstalk = "elastic_beanstalk"
    javascript = "javascript"


def normalize_sentry_dsn(dsn: str):
    if not dsn:
        return dsn
    # "https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "sub.domains.sentry.io/yyyyyy"
    prefix, sentry_io = dsn.split("@")
    if sentry_io.count(".") > 1:
        # sub.domains.sentry.io/yyyyyy -> sentry.io/yyyyyy
        sentry_io = ".".join(sentry_io.rsplit(".", 2)[-2:])
    # https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx + @ + sentry.io/yyyyyy"
    return prefix + "@" + sentry_io


def get_dsn_from_string(sentry_type: str):
    """ Returns a DSN, even if it is incorrectly formatted. """
    if sentry_type == SentryTypes.data_processing:
        return normalize_sentry_dsn(SENTRY_DATA_PROCESSING_DSN)
    elif sentry_type == SentryTypes.elastic_beanstalk:
        return normalize_sentry_dsn(SENTRY_ELASTIC_BEANSTALK_DSN)
    elif sentry_type == SentryTypes.javascript:
        return normalize_sentry_dsn(SENTRY_JAVASCRIPT_DSN)
    else:
        raise Exception(f'Invalid sentry type, use {SentryTypes.__module__}.SentryTypes')


def make_sentry_client(sentry_type: str, tags=None):
    dsn = get_dsn_from_string(sentry_type)
    tags = tags or {}
    tags["sentry_type"] = sentry_type
    return SentryClient(dsn=dsn, tags=tags, transport=HTTPTransport)


def make_error_sentry(sentry_type:str, tags:dict=None):
    """ Creates an ErrorSentry, defaults to error limit 10.
    If the applicable sentry DSN is missing will return an ErrorSentry,
    but if null truthy a NullErrorHandler will be returned instead. """
    
    if RUNNING_TEST_OR_IN_A_SHELL:
        return null_error_handler
    
    tags = tags or {}
    tags["sentry_type"] = sentry_type
    
    try:
        return ErrorSentry(
            get_dsn_from_string(sentry_type),
            sentry_client_kwargs={'tags': tags, 'transport': HTTPTransport},
            sentry_report_limit=10
        )
    except InvalidDsn:
        return null_error_handler
