""" Document sourced from https://samuh.medium.com/using-jinja2-with-django-1-8-onwards-9c58fe1204dc """

from jinja2 import Environment
from django.urls import reverse
from django.contrib.staticfiles.storage import staticfiles_storage

# for more later django installations use:
# from django.templatetags.static import static


def environment(**options):
    """ This enables us to use Django template tags like
    {% url “index” %} or {% static “path/to/static/file.js” %}
    in our Jinja2 templates.  """
    env = Environment(**options)
    env.globals.update({
        "static": staticfiles_storage.url,
        "url": reverse,
        "easy_url": easy_url,
    })
    return env


def easy_url(url: str, *args, **kwargs):
    """ Shortcut for use in Jinja templates, useful in the django port, mimics syntax of Flask. """
    return reverse(url, args=args, kwargs=kwargs)
