from datetime import datetime, date

from django.utils import timezone

from constants.celery_constants import ScheduleTypes
from constants.researcher_constants import ResearcherRole
from constants.testing_constants import REAL_ROLES, SITE_ADMIN
from database.common_models import generate_objectid_string
from database.schedule_models import ArchivedEvent, Intervention, InterventionDate
from database.study_models import DeviceSettings, Study, StudyField
from database.survey_models import Survey
from database.tableau_api_models import ForestParam
from database.user_models import Participant, Researcher, StudyRelation
from libs.security import generate_easy_alphanumeric_string


class ReferenceObjectMixin:
    """ This class implements DB object creation.  Some objects have convenience property wrappers
    because they are so common. """
    
    DEFAULT_RESEARCHER_NAME = "session_researcher"
    DEFAULT_RESEARCHER_PASSWORD = "abcABC123!@#"
    DEFAULT_STUDY_NAME = "session_study"
    DEFAULT_SURVEY_OBJECT_ID = 'u1Z3SH7l2xNsw72hN3LnYi96'
    
    # For all defaults make sure to maintain the pattern that includes the use of the save function,
    # this codebase implements a special save function that validates before passing through.
    
    #
    ## Study objects
    #
    @property
    def session_study(self) -> Study:
        """ Gets or creates a default study object.  Note that this has the side effect of creating
        a study settings db object as well.  This is a default object, and will be auto-populated
        in scenarios where such an object is required but not provided. """
        try:
            return self._default_study
        except AttributeError:
            pass
        study = Study(
            name=self.DEFAULT_STUDY_NAME,
            encryption_key="thequickbrownfoxjumpsoverthelazy",
            object_id="2Mwjb91zSWzHgOrQahEvlu5v",
            is_test=True,
            timezone_name="America/New_York",
            deleted=False,
            forest_enabled=True,
            forest_param=self.default_forest_params,
        )
        study.save()
        self._default_study = study
        return study
    
    def set_session_study_relation(self, relation: str = ResearcherRole.researcher) -> StudyRelation:
        """ Applies the study relation to the session researcher to the session study. """
        if hasattr(self, "_default_study_relation"):
            raise Exception("can only be called once per test (currently?)")
        
        self._default_study_relation = self.generate_study_relation(
            self.session_researcher, self.session_study, relation
        )
        return self._default_study_relation
    
    def generate_study_relation(self, researcher: Researcher, study: Study, relation: str) -> StudyRelation:
        """ Creates a study relation based on the input values, returns it. """
        if relation == SITE_ADMIN:
            self.session_researcher.update(site_admin=True)
            return SITE_ADMIN
        self.assertIn(relation, REAL_ROLES)  # assertIn is part of TestCase.
        relation = StudyRelation(researcher=researcher, study=study, relationship=relation)
        relation.save()
        return relation
    
    #
    ## Researcher objects
    #
    @property
    def session_researcher(self) -> Researcher:
        """ Gets or creates the session researcher object.  This is a default object, and will be
        auto-populated in scenarios where such an object is required but not provided.  """
        try:
            return self._default_researcher
        except AttributeError:
            pass
        self._default_researcher = self.generate_researcher(self.DEFAULT_RESEARCHER_NAME)
        return self._default_researcher
    
    def generate_researcher(
        self, name: str = None, relation_to_session_study: str = None
    ) -> Researcher:
        """ Generate a researcher based on the parameters provided, relation_to_session_study is
        optional. """
        researcher = Researcher(
            username=name or generate_easy_alphanumeric_string(),
            password='zsk387ts02hDMRAALwL2SL3nVHFgMs84UcZRYIQWYNQ=',
            salt='hllJauvRYDJMQpXQKzTdwQ==',  # these will get immediately overwritten
            site_admin=relation_to_session_study == SITE_ADMIN,
            is_batch_user=False,
        )
        # set password saves...
        researcher.set_password(self.DEFAULT_RESEARCHER_PASSWORD)
        if relation_to_session_study not in (None, SITE_ADMIN):
            self.generate_study_relation(researcher, self.session_study, relation_to_session_study)
        
        return researcher
    
    #
    ## Objects for Studies
    #
    
    @property
    def default_survey(self) -> Survey:
        """ Creates a survey with no content attached to the session study. """
        try:
            return self._default_survey
        except AttributeError:
            pass
        self._default_survey = self.generate_survey(
            self.session_study, Survey.TRACKING_SURVEY, self.DEFAULT_SURVEY_OBJECT_ID,
        )
        return self._default_survey
    
    def generate_survey(self, study: Study, survey_type: str, object_id: str = None, **kwargs) -> Survey:
        survey = Survey(
            study=study,
            survey_type=survey_type,
            object_id=object_id or generate_objectid_string(),
            **kwargs
        )
        survey.save()
        return survey
    
    @property
    def session_device_settings(self) -> DeviceSettings:
        """ Providing the comment about using the save() pattern is observed, this cannot fail. """
        return self.session_study.device_settings
    
    def generate_intervention(self, study: Study, name: str) -> Intervention:
        intervention = Intervention(study=study, name=name)
        intervention.save()
        return intervention
    
    def generate_study_field(self, study: Study, name: str) -> StudyField:
        study_field = StudyField(study=study, field_name=name)
        study_field.save()
        return study_field
    
    #
    ## Participant objects
    #
    
    @property
    def default_participant(self) -> Participant:
        """ Creates a participant object on the session study.  This is a default object, and will
        be auto-populated in scenarios where such an object is required but not provided. """
        try:
            return self._default_participant
        except AttributeError:
            pass
        self._default_participant = self.generate_participant(self.session_study, "particip")
        return self._default_participant
    
    def generate_participant(self, study: Study, patient_id: str = None, ios=False):
        participant = Participant(
            patient_id=patient_id or generate_easy_alphanumeric_string(),
            os_type=Participant.IOS_API if ios else Participant.ANDROID_API,
            study=study,
            device_id='_xjeWARoRevoDoL9OKDwRMpYcDhuAxm4nwedUgABxWA=',
            password='2oWT7-6Su2WMDRWpclT0q2glam7AD5taUzHIWRnO490=',
            salt='1NB2kCxOOYzayIYGZYlhHw==',
        )
        participant.save()
        return participant
    
    def generate_intervention_date(
        self, participant: Participant, intervention: Intervention, date: date = None
    ) -> InterventionDate:
        intervention_date = InterventionDate(
            participant=participant, intervention=intervention, date=date or timezone.now().today()
        )
        intervention_date.save()
        return intervention_date
    
    # def generate_scheduled_event(self, survey: Survey, participant: Participant, schedule_type: str) -> ScheduledEvent:
    #     ScheduledEvent(
    #         survey_archive
    #         weekly_schedule
    #         relative_schedule
    #         absolute_schedule
    #         scheduled_time
    #     )
    
    def generate_archived_event(
        self, survey: Survey, participant: Participant, schedule_type: str = None,
        scheduled_time: datetime = None, response_time: datetime = None, status: str = None
    ):
        archived_event = ArchivedEvent(
            survey_archive=survey.archives.first(),
            participant=participant,
            schedule_type=schedule_type or ScheduleTypes.weekly,
            scheduled_time=scheduled_time or timezone.now(),
            response_time=response_time or None,
            status=status or ArchivedEvent.SUCCESS,
        )
        archived_event.save()
        return archived_event
    
    #
    ## Forest objects
    #
    
    @property
    def default_forest_params(self) -> ForestParam:
        """ Creates a default forest params object.  This is a default object, and will be
        auto-populated in scenarios where such an object is required but not provided. """
        try:
            return self._default_forest_params
        except AttributeError:
            pass
        # there is an actual default ForestParams defined in a migration.
        self._default_forest_params = ForestParam.objects.get(default=True)
        return self._default_forest_params


def compare_dictionaries(reference, comparee, ignore=None):
    """ Compares two dictionary objects and displays the differences in a useful fashion. """
    
    if not isinstance(reference, dict):
        raise Exception("reference was %s, not dictionary" % type(reference))
    if not isinstance(comparee, dict):
        raise Exception("comparee was %s, not dictionary" % type(comparee))
    
    if ignore is None:
        ignore = []
    
    b = set((x, y) for x, y in comparee.items() if x not in ignore)
    a = set((x, y) for x, y in reference.items() if x not in ignore)
    differences_a = a - b
    differences_b = b - a
    
    if len(differences_a) == 0 and len(differences_b) == 0:
        return True
    
    try:
        differences_a = sorted(differences_a)
        differences_b = sorted(differences_b)
    except Exception:
        pass
    
    print("These dictionaries are not identical:")
    if differences_a:
        print("in reference, not in comparee:")
        for x, y in differences_a:
            print("\t", x, y)
    if differences_b:
        print("in comparee, not in reference:")
        for x, y in differences_b:
            print("\t", x, y)
    
    return False
