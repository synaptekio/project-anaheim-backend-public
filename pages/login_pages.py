from django.http.request import HttpRequest
from django.shortcuts import redirect, render, reverse
from django.contrib import messages
from authentication import admin_authentication
from database.user_models import Researcher


def login_page(request: HttpRequest):
    if admin_authentication.check_is_logged_in(request):
        return redirect("/choose_study")
    return render(request, 'admin_login.html')


def validate_login(request: HttpRequest):
    """ Authenticates administrator login, redirects to login page if authentication fails. """
    if request.method == 'POST':
        username = request.POST.get("username", None)
        password = request.POST.get("password", None)
        if username and password and Researcher.check_password(username, password):
            admin_authentication.log_in_researcher(request, username)
            return redirect("/choose_study")
        else:
            messages.warning(request, "Incorrect username & password combination; try again.")

    return redirect(reverse("login_pages.login_page"))
