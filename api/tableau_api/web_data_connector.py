from flask import render_template
from flask.views import MethodView
from flask_cors import cross_origin

from api.tableau_api.constants import FIELD_TYPE_MAP, SERIALIZABLE_FIELD_NAMES
from database.tableau_api_models import SummaryStatisticDaily


class WebDataConnector(MethodView):

    path = '/api/v0/studies/<string:study_object_id>/summary-statistics/daily/wdc'

    def __init__(self, *args, **kwargs):
        """ This endpoint provides a schema to Tableau of the data names and types returned by the
        tableau data endpoint.  This schema is checked asynchronously by tableau (it is a separate
        url) and as far as I could tell the only reliable moment is when the user loads the WDC page
        to enter their credentials.  If this structure is out of date or missing fields / their
        type declaration then Tableau will silently elide those fields from its interface. """
        super().__init__(*args, **kwargs)

        # build the columns datastructure for tableau to enumerate the format of the API data
        fields = (f for f in SummaryStatisticDaily._meta.fields if f.name in SERIALIZABLE_FIELD_NAMES)
        self.cols = '[\n'

        # study_id and participant_id are not part of the SummaryStatisticDaily model, so they
        # aren't populated. They are also related fields that both are proxies for a unique
        # identifier field that has a different name, so we do it manually.
        # TODO: find a good way to not do this manually.
        self.cols += "{id: 'study_id', dataType: tableau.dataTypeEnum.string,},\n"
        self.cols += "{id: 'participant_id', dataType: tableau.dataTypeEnum.string,},\n"

        for field in fields:
            for (py_type, tableau_type) in FIELD_TYPE_MAP:
                if isinstance(field, py_type):
                    self.cols += f"{{id: '{field.name}', dataType: {tableau_type},}},\n"
                    # ex line: {id: 'distance_diameter', dataType: tableau.dataTypeEnum.float,},
                    break
            else:
                # if the field type is not recognized, supply it to tableau as a string type
                self.cols += f"{{id: '{field.name}', dataType: tableau.dataTypeEnum.string,}},\n"

        self.cols += '];'

    @classmethod
    def register_urls(cls, app):
        """
        Register this class' URLs with Flask
        """
        app.add_url_rule(cls.path, view_func=cls.as_view("web_data_connector_view"))

    @cross_origin()
    def get(self, study_object_id):
        # for security reasons, no study_id validation occurs here, and no study info is exposed
        # there is necessarily no validation to get to this page. No information should be exposed here
        return render_template('wdc.html', study_object_id=study_object_id, cols=self.cols)
