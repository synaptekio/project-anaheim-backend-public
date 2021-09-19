from pages.admin_pages import choose_study
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from pages.login_pages import validate_login, login_page


urlpatterns = [
    path('', login_page),
    path('validate_login', validate_login),
    path("choose_study", choose_study)
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
