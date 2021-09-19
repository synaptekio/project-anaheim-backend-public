from pages.admin_pages import choose_study, logout_admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from pages.login_pages import validate_login, login_page


urlpatterns = [
    path('', login_page),
    path('validate_login', validate_login),
    path("choose_study", choose_study),
    path("logout", logout_admin),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
