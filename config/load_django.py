import builtins
import os

import django
from django.conf import settings

import config.django_settings

builtins = vars(builtins)  # tiny optimization...


try:
    # get all the variables declared in the django settings file, exclude builtins for basic sanity.
    # (unrecognized parameters are ignored, fortunately.)
    django_config = {
        setting_name: setting_value for setting_name, setting_value in
        vars(config.django_settings).items() if setting_name not in builtins
    }

    # django setup file
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.django_settings")
    settings.configure(**django_config)

    django.setup()
except RuntimeError as e:
    pass
