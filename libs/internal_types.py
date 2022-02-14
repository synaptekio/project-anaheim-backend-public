from typing import List, Union

from django.db.models import Manager, QuerySet
from django.http.request import HttpRequest

from database.dashboard_models import DashboardColorSetting, DashboardGradient, DashboardInflection
from database.data_access_models import (ChunkRegistry, FileToProcess, PipelineRegistry,
    PipelineUpload, PipelineUploadTags)
from database.profiling_models import (DecryptionKeyError, EncryptionErrorMetadata,
    LineEncryptionError, UploadTracking)
from database.schedule_models import (AbsoluteSchedule, ArchivedEvent, Intervention,
    InterventionDate, RelativeSchedule, ScheduledEvent, WeeklySchedule)
from database.security_models import ApiKey
from database.study_models import DeviceSettings, Study, StudyField
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


# Generated with scripts/generate_typing_hax.py on 2022-02-13
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

AbsoluteScheduleManager = Union[Manager, List[AbsoluteSchedule]]
ApiKeyManager = Union[Manager, List[ApiKey]]
ArchivedEventManager = Union[Manager, List[ArchivedEvent]]
ChunkRegistryManager = Union[Manager, List[ChunkRegistry]]
DashboardColorSettingManager = Union[Manager, List[DashboardColorSetting]]
DashboardGradientManager = Union[Manager, List[DashboardGradient]]
DashboardInflectionManager = Union[Manager, List[DashboardInflection]]
DecryptionKeyErrorManager = Union[Manager, List[DecryptionKeyError]]
DeviceSettingsManager = Union[Manager, List[DeviceSettings]]
FileToProcessManager = Union[Manager, List[FileToProcess]]
InterventionDateManager = Union[Manager, List[InterventionDate]]
InterventionManager = Union[Manager, List[Intervention]]
ParticipantFCMHistoryManager = Union[Manager, List[ParticipantFCMHistory]]
ParticipantFieldValueManager = Union[Manager, List[ParticipantFieldValue]]
ParticipantManager = Union[Manager, List[Participant]]
PipelineRegistryManager = Union[Manager, List[PipelineRegistry]]
PipelineUploadManager = Union[Manager, List[PipelineUpload]]
PipelineUploadTagsManager = Union[Manager, List[PipelineUploadTags]]
RelativeScheduleManager = Union[Manager, List[RelativeSchedule]]
ScheduledEventManager = Union[Manager, List[ScheduledEvent]]
StudyFieldManager = Union[Manager, List[StudyField]]
StudyRelationManager = Union[Manager, List[StudyRelation]]
SummaryStatisticDailyManager = Union[Manager, List[SummaryStatisticDaily]]
SurveyArchiveManager = Union[Manager, List[SurveyArchive]]
SurveyManager = Union[Manager, List[Survey]]
UploadTrackingManager = Union[Manager, List[UploadTracking]]
WeeklyScheduleManager = Union[Manager, List[WeeklySchedule]]
