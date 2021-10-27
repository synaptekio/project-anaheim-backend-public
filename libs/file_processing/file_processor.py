from collections import defaultdict
from multiprocessing.pool import ThreadPool

from config.settings import CONCURRENT_NETWORK_OPS, FILE_PROCESS_PAGE_SIZE
from database.user_models import Participant


class FileProcessor():

    skip_count = FILE_PROCESS_PAGE_SIZE

    def __init__(self):
        self.all_binified_data = defaultdict(lambda: ([], []))
        self.FFPs_to_remove = set()
        self.pool = ThreadPool(CONCURRENT_NETWORK_OPS)
        self.participants = Participant.objects.filter(files_to_process__isnull=False).distinct()
        self.survey_id_dict = {}

        self.current_location = 0
        self.number_bad_files = 0

    def process(self):
        for participant in self.participants:
            while True:
                previous_number_bad_files = number_bad_files
                starting_length = participant.files_to_process.exclude(deleted=True).count()

                print("%s processing %s, %s files remaining" % (datetime.now(), participant.patient_id, starting_length))

                # Process the desired number of files and calculate the number of unprocessed files
                number_bad_files += do_process_user_file_chunks(
                        count=FILE_PROCESS_PAGE_SIZE,
                        error_handler=error_handler,
                        skip_count=number_bad_files,
                        participant=participant,
                )

                # If no files were processed, quit processing
                if (participant.files_to_process.exclude(deleted=True).count() == starting_length
                        and previous_number_bad_files == number_bad_files):
                    # Cases:
                    #   every file broke, might as well fail here, and would cause infinite loop otherwise.
                    #   no new files.
                    break
