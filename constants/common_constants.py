from sys import argv as _argv

BEIWE_PROJECT_ROOT = __file__.rsplit("/", 2)[0] + "/"
PROJECT_PARENT_FOLDER = BEIWE_PROJECT_ROOT.rsplit("/", 2)[0] + "/"

RUNNING_TEST_OR_IN_A_SHELL = any(key in _argv for key in ("shell_plus", "--ipython", "ipython", "test"))
