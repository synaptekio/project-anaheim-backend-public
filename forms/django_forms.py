import bleach
from django import forms
from django.utils.datastructures import MultiValueDict

from constants.forest_constants import ForestTaskStatus, ForestTree
from constants.tableau_api_constants import (HEADER_IS_REQUIRED, SERIALIZABLE_FIELD_NAMES,
    SERIALIZABLE_FIELD_NAMES_DROPDOWN, VALID_QUERY_PARAMETERS, X_ACCESS_KEY_ID, X_ACCESS_KEY_SECRET)
from database.tableau_api_models import ForestTask
from database.user_models import Participant
from forms.django_form_fields import CommaSeparatedListCharField, CommaSeparatedListChoiceField


class NewApiKeyForm(forms.Form):
    readable_name = forms.CharField(required=False)
    
    def clean(self):
        super().clean()
    
    def clean_readable_name(self):
        return bleach.clean(self.cleaned_data["readable_name"])


class DisableApiKeyForm(forms.Form):
    api_key_id = forms.CharField()


class AuthenticationForm(forms.Form):
    """ Form for fetching request headers """
    
    def __init__(self, *args, **kwargs):
        """ Define authentication form fields since the keys contain illegal characters for variable
        names. """
        super().__init__(*args, **kwargs)
        self.fields[X_ACCESS_KEY_ID] = forms.CharField(
            error_messages={"required": HEADER_IS_REQUIRED}
        )
        self.fields[X_ACCESS_KEY_SECRET] = forms.CharField(
            error_messages={"required": HEADER_IS_REQUIRED}
        )


class CreateTasksForm(forms.Form):
    date_start = forms.DateField()
    date_end = forms.DateField()
    participant_patient_ids = CommaSeparatedListCharField()
    trees = CommaSeparatedListChoiceField(choices=ForestTree.choices())
    
    def __init__(self, *args, **kwargs):
        self.study = kwargs.pop("study")
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data["date_end"] < cleaned_data["date_start"]:
            error_message = "Start date must be before or the same as end date."
            self.add_error("date_start", error_message)
            self.add_error("date_end", error_message)
    
    def clean_participant_patient_ids(self):
        """
        Filter participants to those who are registered in this study and specified in this field
        (instead of raising a ValidationError if an invalid or non-study patient id is specified).
        """
        patient_ids = self.cleaned_data["participant_patient_ids"]
        participants = (
            Participant
                .objects
                .filter(patient_id__in=patient_ids, study=self.study)
                .values("id", "patient_id")
        )
        self.cleaned_data["participant_ids"] = [participant["id"] for participant in participants]
        
        return [participant["patient_id"] for participant in participants]
    
    def save(self):
        forest_tasks = []
        for participant_id in self.cleaned_data["participant_ids"]:
            for tree in self.cleaned_data["trees"]:
                forest_tasks.append(
                    ForestTask(
                        participant_id=participant_id,
                        forest_tree=tree,
                        data_date_start=self.cleaned_data["date_start"],
                        data_date_end=self.cleaned_data["date_end"],
                        status=ForestTaskStatus.queued,
                        forest_param=self.study.forest_param,
                    )
                )
        ForestTask.objects.bulk_create(forest_tasks)


class ApiQueryForm(forms.Form):
    end_date = forms.DateField(
        required=False,
        error_messages={
            "invalid": "end date could not be interpreted as a date. Dates should be "
                       "formatted as YYYY-MM-DD"
        },
    )
    
    start_date = forms.DateField(
        required=False,
        error_messages={
            "invalid": "start date could not be interpreted as a date. Dates should be "
                       "formatted as YYYY-MM-DD"
        },
    )
    
    limit = forms.IntegerField(
        required=False,
        error_messages={"invalid": "limit value could not be interpreted as an integer value"},
    )
    order_by = forms.ChoiceField(
        choices=SERIALIZABLE_FIELD_NAMES_DROPDOWN,
        required=False,
        error_messages={
            "invalid_choice": "%(value)s is not a field that can be used to sort the output"
        },
    )
    
    order_direction = forms.ChoiceField(
        choices=[("ascending", "ascending"), ("descending", "descending")],
        required=False,
        error_messages={
            "invalid_choice": "If provided, the order_direction parameter "
                              "should contain either the value 'ascending' or 'descending'"
        },
    )
    
    participant_ids = CommaSeparatedListCharField(required=False)
    
    fields = CommaSeparatedListChoiceField(
        choices=SERIALIZABLE_FIELD_NAMES_DROPDOWN,
        default=SERIALIZABLE_FIELD_NAMES,
        required=False,
        error_messages={"invalid_choice": "%(value)s is not a valid field"},
    )
    
    def clean(self) -> dict:
        """ Retains only members of VALID_QUERY_PARAMETERS and non-falsey-but-not-False objects """
        super().clean()
        return {
            k: v for k, v in self.cleaned_data.items()
            if k in VALID_QUERY_PARAMETERS and (v or v is False)
        }
