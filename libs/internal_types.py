from typing import List, Union

from django.db.models import QuerySet
from django.http.request import HttpRequest

from database.dashboard_models import DashboardColorSetting, DashboardGradient, DashboardInflection
from database.data_access_models import (ChunkRegistry, FileToProcess, PipelineRegistry,
    PipelineUpload, PipelineUploadTags)
from database.profiling_models import (DecryptionKeyError, EncryptionErrorMetadata,
    LineEncryptionError, UploadTracking)
from database.schedule_models import (AbsoluteSchedule, ArchivedEvent, Intervention,
    InterventionDate, RelativeSchedule, ScheduledEvent, WeeklySchedule)
from database.security_models import ApiKey
from database.study_models import DeviceSettings, Study
from database.survey_models import Survey, SurveyArchive, SurveyBase
from database.system_models import FileAsText, FileProcessLock
from database.tableau_api_models import ForestParam, ForestTask, SummaryStatisticDaily
from database.user_models import (AbstractPasswordUser, Participant, ParticipantFCMHistory,
    ParticipantFieldValue, PushNotificationDisabledEvent, Researcher, StudyRelation)


""" This file includes types and typing information that may be missing from your
developmentenvironment or your IDE, as well as some useful type hints. """

#
## Request objects
#

class ResearcherRequest(HttpRequest):
    # these attributes are present on the normal researcher endpoints
    session_researcher: Researcher


class ApiStudyResearcherRequest(HttpRequest):
    api_researcher: Researcher
    api_study: Study


class ApiResearcherRequest(HttpRequest):
    api_researcher: Researcher


class ParticipantRequest(HttpRequest):
    session_participant: Participant


class TableauRequest(HttpRequest):
    pass

#
## Other classes
#

StrOrBytes = Union[str, bytes]

# to generate the below list run this little script.  Don't use * imports.
# from django.db.models.base import ModelBase
# 
# from database import models as database_models
# from database.common_models import TimestampedModel, UtilityModel
# 
# for name, database_model in vars(database_models).items():
#     if (
#         isinstance(database_model, ModelBase) and UtilityModel in database_model.mro() and
#         database_model is not UtilityModel and database_model is not TimestampedModel
#     ):
#        print(f"{name}QuerySet = Union[QuerySet, List[{name}]]")

AbsoluteScheduleQuerySet = Union[QuerySet, List[AbsoluteSchedule]]
AbstractPasswordUserQuerySet = Union[QuerySet, List[AbstractPasswordUser]]
ApiKeyQuerySet = Union[QuerySet, List[ApiKey]]
ArchivedEventQuerySet = Union[QuerySet, List[ArchivedEvent]]
ChunkRegistryQuerySet = Union[QuerySet, List[ChunkRegistry]]
DashboardColorSettingQuerySet = Union[QuerySet, List[DashboardColorSetting]]
DashboardGradientQuerySet = Union[QuerySet, List[DashboardGradient]]
DashboardInflectionQuerySet = Union[QuerySet, List[DashboardInflection]]
DecryptionKeyErrorQuerySet = Union[QuerySet, List[DecryptionKeyError]]
DeviceSettingsQuerySet = Union[QuerySet, List[DeviceSettings]]
EncryptionErrorMetadataQuerySet = Union[QuerySet, List[EncryptionErrorMetadata]]
FileAsTextQuerySet = Union[QuerySet, List[FileAsText]]
FileProcessLockQuerySet = Union[QuerySet, List[FileProcessLock]]
FileToProcessQuerySet = Union[QuerySet, List[FileToProcess]]
ForestParamQuerySet = Union[QuerySet, List[ForestParam]]
ForestTaskQuerySet = Union[QuerySet, List[ForestTask]]
InterventionDateQuerySet = Union[QuerySet, List[InterventionDate]]
InterventionQuerySet = Union[QuerySet, List[Intervention]]
LineEncryptionErrorQuerySet = Union[QuerySet, List[LineEncryptionError]]
ParticipantFCMHistoryQuerySet = Union[QuerySet, List[ParticipantFCMHistory]]
ParticipantFieldValueQuerySet = Union[QuerySet, List[ParticipantFieldValue]]
ParticipantQuerySet = Union[QuerySet, List[Participant]]
PipelineRegistryQuerySet = Union[QuerySet, List[PipelineRegistry]]
PipelineUploadQuerySet = Union[QuerySet, List[PipelineUpload]]
PipelineUploadTagsQuerySet = Union[QuerySet, List[PipelineUploadTags]]
PushNotificationDisabledEventQuerySet = Union[QuerySet, List[PushNotificationDisabledEvent]]
RelativeScheduleQuerySet = Union[QuerySet, List[RelativeSchedule]]
ResearcherQuerySet = Union[QuerySet, List[Researcher]]
ScheduledEventQuerySet = Union[QuerySet, List[ScheduledEvent]]
StudyQuerySet = Union[QuerySet, List[Study]]
StudyRelationQuerySet = Union[QuerySet, List[StudyRelation]]
SummaryStatisticDailyQuerySet = Union[QuerySet, List[SummaryStatisticDaily]]
SurveyArchiveQuerySet = Union[QuerySet, List[SurveyArchive]]
SurveyBaseQuerySet = Union[QuerySet, List[SurveyBase]]
SurveyQuerySet = Union[QuerySet, List[Survey]]
UploadTrackingQuerySet = Union[QuerySet, List[UploadTracking]]
WeeklyScheduleQuerySet = Union[QuerySet, List[WeeklySchedule]]
