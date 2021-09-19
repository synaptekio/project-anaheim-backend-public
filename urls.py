from pages.admin_pages import choose_study, logout_admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from pages import login_pages, admin_pages
from api import dashboard_api

urlpatterns = [
    path('', login_pages.login_page),
    path('validate_login', login_pages.validate_login),
    path("choose_study", admin_pages.choose_study),
    path("logout", admin_pages.logout_admin),

    path('view_study/<int:study_id>', admin_pages.view_study, name="admin_pages.view_study"),
    # path('manage_credentials', admin_pages.manage_credentials, name=manage_credentials),
    # path('reset_admin_password', admin_pages.reset_admin_password, name=reset_admin_password),
    # path('reset_download_api_credentials', admin_pages.reset_download_api_credentials, name=reset_download_api_credentials),
    # path('new_api_key', admin_pages.new_api_key, name=new_api_key),
    # path('disable_api_key', admin_pages.disable_api_key, name=disable_api_key),

    path("dashboard/<int:study_id>", dashboard_api.dashboard_page, name="dashboard_api.dashboard_page"),
    path("dashboard/<int:study_id>/data_stream/<str:data_stream>", dashboard_api.get_data_for_dashboard_datastream_display, name="dashboard_api.get_data_for_dashboard_datastream_display"),
    path("dashboard/<int:study_id>/patient/<str:patient_id>", dashboard_api.get_data_for_dashboard_patient_display, name="dashboard_api.get_data_for_dashboard_patient_display"),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
