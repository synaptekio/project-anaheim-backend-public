import json

from django.db.models import QuerySet
from django.shortcuts import render
from django.views.decorators.http import require_GET
from rest_framework.renderers import JSONRenderer

from authentication.tableau_authentication import authenticate_tableau
from constants.tableau_api_constants import FIELD_TYPE_MAP, SERIALIZABLE_FIELD_NAMES
from database.tableau_api_models import SummaryStatisticDaily
from forms.django_forms import ApiQueryForm
from libs.internal_types import TableauRequest
from serializers.tableau_serializers import SummaryStatisticDailySerializer


FINAL_SERIALIZABLE_FIELD_NAMES = (
    f for f in SummaryStatisticDaily._meta.fields if f.name in SERIALIZABLE_FIELD_NAMES
)


@require_GET
@authenticate_tableau
def get_tableau_daily(request: TableauRequest):
    form = ApiQueryForm(data=request.POST)
    if not form.is_valid():
        return format_errors(form.errors.get_json_data())
    query = tableau_query_database(study_object_id=form.get_study_id(), **form.cleaned_data)
    serializer = SummaryStatisticDailySerializer(
        query, fields=form.cleaned_data["fields"], many=True,
    )
    return JSONRenderer().render(serializer.data)


@require_GET
def web_data_connector(request: TableauRequest, study_object_id: str):
    # build the columns datastructure for tableau to enumerate the format of the API data
    columns = ['[\n']
    # study_id and participant_id are not part of the SummaryStatisticDaily model, so they
    # aren't populated. They are also related fields that both are proxies for a unique
    # identifier field that has a different name, so we do it manually.
    # TODO: this could be less messy.
    columns.append("{id: 'study_id', dataType: tableau.dataTypeEnum.string,},\n")
    columns.append("{id: 'participant_id', dataType: tableau.dataTypeEnum.string,},\n")
    for field in FINAL_SERIALIZABLE_FIELD_NAMES:
        for (py_type, tableau_type) in FIELD_TYPE_MAP:
            if isinstance(field, py_type):
                columns.append(f"{{id: '{field.name}', dataType: {tableau_type},}},\n")
                # ex line: {id: 'participant_id', dataType: tableau.dataTypeEnum.int,},
                break
        else:
            # if the field is not recognized, supply it to tableau as a string type
            columns.append(f"{{id: '{field.name}', dataType: tableau.dataTypeEnum.string,}},\n")
    columns.append('];')
    return render(
        request,
        'wdc.html', context={"study_object_id": study_object_id, "cols": "".join(columns)}
    )


def format_errors(errors: dict) -> str:
    """ Flattens a django validation error dictionary into a json string. """
    messages = []
    for field, field_errs in errors.items():
        messages.extend([err["message"] for err in field_errs])
    return json.dumps({"errors": messages})


def tableau_query_database(
    study_object_id, participant_ids=None, limit=None,       # basics
    end_date=None, start_date=None,                          # time
    order_by="date", order_direction="descending",           # sort
    **_   # Because Whimsy is important.                     # ignore everything else
) -> QuerySet:
    """
    Args:
        study_object_id (str): study in which to find data
        end_date (optional[date]): last date to include in search
        start_date (optional[date]): first date to include in search
        limit (optional[int]): maximum number of data points to return
        order_by (str): parameter to sort output by. Must be one in the list of fields to return
        order_direction (str): order to sort in, either "ascending" or "descending"
        participant_ids (optional[list[str]]): a list of participants to limit the search to

    Returns (queryset[SummaryStatisticsDaily]):
            the SummaryStatisticsDaily objects specified by the parameters
    """
    if order_direction == "descending":
        order_by = "-" + order_by
    queryset = SummaryStatisticDaily.objects.filter(participant__study__object_id=study_object_id)
    if participant_ids:
        queryset = queryset.filter(participant__patient_id__in=participant_ids)
    if end_date:
        queryset = queryset.filter(date__lte=end_date)
    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    queryset = queryset.order_by(order_by)
    if limit:
        queryset = queryset[:limit]
    return queryset
