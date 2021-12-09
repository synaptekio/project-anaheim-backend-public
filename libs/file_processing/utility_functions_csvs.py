
from datetime import datetime
from typing import Generator, List

from constants.datetime_constants import API_TIME_FORMAT
from libs.file_processing.exceptions import BadTimecodeError


def insert_timestamp_single_row_csv(header: bytes, rows_list: list, time_stamp: bytes) -> bytes:
    """ Inserts the timestamp field into the header of a csv, inserts the timestamp
        value provided into the first column.  Returns the new header string."""
    header_list = header.split(b",")
    header_list.insert(0, b"timestamp")
    rows_list[0].insert(0, time_stamp)
    return b",".join(header_list)


# def csv_to_list(csv_string: bytes) -> (bytes, Generator):
#     """ Grab a list elements from of every line in the csv, strips off trailing whitespace. dumps
#     them into a new list (of lists), and returns the header line along with the list of rows. """
#     # This code is more memory efficient than fast by using a generator
#     # Note that almost all of the time is spent in the per-row for-loop
#     def split_yielder(l):
#         for row in l:
#             yield row.split(b",")
#     header = csv_string[:csv_string.find(b"\n")]
#     lines = csv_string.splitlines()
#     # Remove the header
#     lines.pop(0)  # This line is annoyingly slow, but its fine...
#     del csv_string  # To clear up memory
#     return header, split_yielder(lines)

def csv_to_list(file_contents) -> (bytes, Generator):
    """ Grab a list elements from of every line in the csv, strips off trailing whitespace. dumps
    them into a new list (of lists), and returns the header line along with the list of rows. """

    # This code is more memory efficient than fast by using a generator
    # Note that almost all of the time is spent in the per-row for-loop

    # case: the file coming in is just a single line, e.g. the header.
    # Need to provide the header and an empty iterator.
    if b"\n" not in file_contents:
        return file_contents, (_ for _ in ())

    line_iterator = isplit(file_contents)
    header = b",".join(next(line_iterator))
    header2 = file_contents[:file_contents.find(b"\n")]
    assert header2 == header, f"\n{header}\n{header2}"
    return header, line_iterator


def isplit(source: bytes):
    """
    generator version of str.split()/bytes.split()
    :returns:
        generator yielding elements of string.
    """
    # version using str.find(), less overhead than re.finditer()
    start = 0
    while True:
        # find first split
        idx = source.find(b"\n", start)
        if idx == -1:
            yield source[start:].split(b",")
            return

        yield source[start:idx].split(b",")
        start = idx + 1


def construct_csv_string(header: bytes, rows_list: List[bytes]) -> bytes:
    """ Takes a header list and a csv and returns a single string of a csv.
        Now handles unicode errors.  :D :D :D """
    # The old, compact list comprehension was, it turned out, both nonperformant and of an
    # incomprehensible memory order. This is ~1.5x faster, and has a much clearer memory order.

    def deduplicate(seq):
        # highly optimized order preserving deduplication function.
        seen = set()
        seen_add = seen.add
        return [x for x in seq if not (x in seen or seen_add(x))]

    rows = []
    for row_items in rows_list:
        rows.append(b",".join(row_items))

    del rows_list, row_items

    # we need to ensure no duplicates
    rows = deduplicate(rows)
    ret = header
    for row in rows:
        ret += b"\n" + row
    return ret


def clean_java_timecode(java_time_code_string: bytes or str) -> int:
    """ converts millisecond time (string) to an integer normal unix time. """
    try:
        return int(java_time_code_string[:10])
    except ValueError as e:
        # we need a custom error type to handle this error case
        raise BadTimecodeError(str(e))


def unix_time_to_string(unix_time: int) -> bytes:
    return datetime.utcfromtimestamp(unix_time).strftime(API_TIME_FORMAT).encode()
