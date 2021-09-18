from pages.login_pages import render_login_page
from django.urls import path

urlpatterns = [
    path('', render_login_page),
    path('validate_login', render_login_page),
]

