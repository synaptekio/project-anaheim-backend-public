from config.settings import IS_STAGING
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from api import admin_api, dashboard_api
from pages import admin_pages, data_access_web_form, login_pages, system_admin_pages


urlpatterns = [
    # session and login
    path("", login_pages.login_page, name="login_pages.login_page"),
    path("validate_login", login_pages.validate_login, name="login_pages.validate_login"),
    path("choose_study", admin_pages.choose_study, name="admin_pages.choose_study"),
    path("logout", admin_pages.logout_admin, name="admin_pages.logout_admin"),

    # Admin
    path(
        "view_study/<int:study_id>",
        admin_pages.view_study,
        name="admin_pages.view_study",
    ),
    path("manage_credentials",
         admin_pages.manage_credentials,
         name="admin_pages.manage_credentials"),
    path(
        "reset_admin_password",
        admin_pages.reset_admin_password,
        name="admin_pages.reset_admin_password",
    ),
    path(
        "reset_download_api_credentials",
        admin_pages.reset_download_api_credentials,
        name="admin_pages.reset_download_api_credentials",
    ),
    path("new_api_key", admin_pages.new_api_key, name="admin_pages.new_api_key"),
    path("disable_api_key", admin_pages.disable_api_key, name="admin_pages.disable_api_key"),

    # Dashboard
    path(
        "dashboard/<int:study_id>",
        dashboard_api.dashboard_page,
        name="dashboard_api.dashboard_page",
    ),
    path(
        "dashboard/<int:study_id>/data_stream/<str:data_stream>",
        dashboard_api.get_data_for_dashboard_datastream_display,
        name="dashboard_api.get_data_for_dashboard_datastream_display",
    ),
    path(
        "dashboard/<int:study_id>/patient/<str:patient_id>",
        dashboard_api.get_data_for_dashboard_patient_display,
        name="dashboard_api.get_data_for_dashboard_patient_display",
    ),

    # system admin pages
    path(
        "manage_researchers",
        system_admin_pages.manage_researchers,
        name="system_admin_pages.manage_researchers",
    ),
    path(
        "edit_researcher/<int:researcher_pk>",
        system_admin_pages.edit_researcher_page,
        name="system_admin_pages.edit_researcher",
    ),
    path(
        "elevate_researcher",
        system_admin_pages.elevate_researcher_to_study_admin,
        name="system_admin_pages.elevate_researcher",
    ),
    path(
        "demote_researcher",
        system_admin_pages.demote_study_admin,
        name="system_admin_pages.demote_researcher",
    ),
    path(
        "create_new_researcher",
        system_admin_pages.create_new_researcher,
        name="system_admin_pages.create_new_researcher",
    ),
    path(
        "manage_studies",
        system_admin_pages.manage_studies,
        name="system_admin_pages.manage_studies",
    ),
    path(
        "edit_study/<int:study_id>",
        system_admin_pages.edit_study,
        name="system_admin_pages.edit_study",
    ),
    path(
        "create_study",
        system_admin_pages.create_study,
        name="system_admin_pages.create_study",
    ),
    path(
        "toggle_study_forest_enabled/<int:study_id>",
        system_admin_pages.toggle_study_forest_enabled,
        name="system_admin_pages.toggle_study_forest_enabled",
    ),
    path(
        "delete_study/<int:study_id>",
        system_admin_pages.delete_study,
        name="system_admin_pages.delete_study",
    ),
    path(
        "device_settings/<int:study_id>",
        system_admin_pages.device_settings,
        name="system_admin_pages.device_settings",
    ),
    path(
        "manage_firebase_credentials",
        system_admin_pages.manage_firebase_credentials,
        name="system_admin_pages.manage_firebase_credentials",
    ),
    path(
        "upload_backend_firebase_cert",
        system_admin_pages.upload_backend_firebase_cert,
        name="system_admin_pages.upload_backend_firebase_cert",
    ),
    path(
        "upload_android_firebase_cert",
        system_admin_pages.upload_android_firebase_cert,
        name="system_admin_pages.upload_android_firebase_cert",
    ),
    path(
        "upload_ios_firebase_cert",
        system_admin_pages.upload_ios_firebase_cert,
        name="system_admin_pages.upload_ios_firebase_cert",
    ),
    path(
        "delete_backend_firebase_cert",
        system_admin_pages.delete_backend_firebase_cert,
        name="system_admin_pages.delete_backend_firebase_cert",
    ),
    path(
        "delete_android_firebase_cert",
        system_admin_pages.delete_android_firebase_cert,
        name="system_admin_pages.delete_android_firebase_cert",
    ),
    path(
        "delete_ios_firebase_cert",
        system_admin_pages.delete_ios_firebase_cert,
        name="system_admin_pages.delete_ios_firebase_cert",
    ),

    # data access web form
    path(
        "data_access_web_form",
        data_access_web_form.data_api_web_form_page,
        name="data_access_web_form.data_access_web_form"
    ),
    path(
        "pipeline_access_web_form",
        data_access_web_form.pipeline_download_page,
        name="data_access_web_form.pipeline_download_page"
    ),

    # admin api
    path(
        'set_study_timezone/<str:study_id>',
        admin_api.set_study_timezone,
        name="admin_api.set_study_timezone"
    ),
    path(
        'add_researcher_to_study',
        admin_api.add_researcher_to_study,
        name="admin_api.add_researcher_to_study"
    ),
    path(
        'remove_researcher_from_study',
        admin_api.remove_researcher_from_study,
        name="admin_api.remove_researcher_from_study"
    ),
    path(
        'delete_researcher/<str:researcher_id>',
        admin_api.delete_researcher,
        name="admin_api.delete_researcher"
    ),
    path(
        'set_researcher_password',
        admin_api.set_researcher_password,
        name="admin_api.set_researcher_password"
    ),
    path(
        'rename_study/<str:study_id>',
        admin_api.rename_study,
        name="admin_api.rename_study"
    ),
    path(
        "downloads",
        admin_api.download_page,
        name="admin_api.download_page"
    ),
    path(
        "download",
        admin_api.download_current,
        name="admin_api.download_current"
    ),
    path(
        "download_debug",
        admin_api.download_current_debug,
        name="admin_api.download_current_debug"
    ),
    path(
        "download_beta",
        admin_api.download_beta,
        name="admin_api.download_beta"
    ),
    path(
        "download_beta_debug",
        admin_api.download_beta_debug,
        name="admin_api.download_beta_debug"
    ),
    path(
        "download_beta_release",
        admin_api.download_beta_release,
        name="admin_api.download_beta_release"
    ),
    path(
        "privacy_policy",
        admin_api.download_privacy_policy,
        name="admin_api.download_privacy_policy"
    ),


] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if IS_STAGING:
    urlpatterns.append(
        path(
            "is_staging",
            admin_api.is_staging,
            name="admin_api.is_staging"
        ),
    )
    