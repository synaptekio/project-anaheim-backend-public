# from django.contrib import messages
from django.http.request import HttpRequest
from django.shortcuts import redirect, render, reverse

from authentication import admin_authentication
from database.user_models import Researcher


def render_login_page(request: HttpRequest):
    if admin_authentication.is_logged_in(request):
        return redirect("/choose_study")
    return render(request, 'admin_login.html')


def login(request: HttpRequest):
    """ Authenticates administrator login, redirects to login page if authentication fails. """
    if request.method == 'POST':
        username = request.POST.get("username", None)
        password = request.POST.get("password", None)
        if username and password and Researcher.check_password(username, password):
            admin_authentication.log_in_researcher(request, username)
            return redirect("/choose_study")
        else:
            # convert to django messages?
            flash("Incorrect username & password combination; try again.", 'danger')

    # return redirect("/")
    return reverse('/validate_login')
