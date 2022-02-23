from datetime import date, datetime, timedelta
from typing import List, Union


def daterange(
    start: datetime, stop: datetime, step: timedelta = timedelta(days=1), inclusive: bool = False
):
    # source: https://stackoverflow.com/a/1060376/1940450
    if step.days > 0:
        while start < stop:
            yield start
            start = start + step
            # not +=! don't modify object passed in if it's mutable
            # since this function is not restricted to
            # only types from datetime module
    elif step.days < 0:
        while start > stop:
            yield start
            start = start + step
    if inclusive and start == stop:
        yield start


def datetime_to_list(datetime_obj: Union[date, datetime]) -> List[int]:
    """ Takes in a date or datetime, returns a list of datetime components. """
    datetime_component_list = [datetime_obj.year, datetime_obj.month, datetime_obj.day]
    if isinstance(datetime_obj, datetime):
        datetime_component_list.extend([
            datetime_obj.hour,
            datetime_obj.minute,
            datetime_obj.second,
            datetime_obj.microsecond,
        ])
    else:
        datetime_component_list.extend([0, 0, 0, 0])
    return datetime_component_list
