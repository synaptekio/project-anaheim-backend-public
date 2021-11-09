class ForestTree:
    """
    Todo: Once we upgrade to Django 3, use TextChoices
    """
    jasmine = "jasmine"
    willow = "willow"
    
    @classmethod
    def choices(cls):
        return [(choice, choice.title()) for choice in cls.values()]
    
    @classmethod
    def values(cls):
        return [cls.jasmine, cls.willow]


# the following dictionary maps pairs of tree names and CSV fields to summary statistic names

# the first value of the output tuple is the summary statistic field name to be updated based on
# that value
# the second value is none, or a function with two inputs used to interpret that field into the
# summary statistic field. The function should take two parameters: the input field value, and the
# full line of data it appeared on (which should contain that value, among others)

# an example minutes to second conversion --- lambda value, _: value * 60
# an example using multiple fields:       --- lambda _, line: line['a'] * line['b']
#   where a and b are other csv fields

TREE_COLUMN_NAMES_TO_SUMMARY_STATISTICS = {
    (ForestTree.jasmine, 'missing_time'): ('gps_data_missing_duration', None),
    (ForestTree.jasmine, 'home_time'): ('home_duration', None),
    (ForestTree.jasmine, 'max_dist_home'): ('distance_from_home', None),
    (ForestTree.jasmine, 'dist_traveled'): ('distance_traveled', None),
    (ForestTree.jasmine, 'av_flight_length'): ('flight_distance_average', None),
    (ForestTree.jasmine, 'sd_flight_length'): ('flight_distance_standard_deviation', None),
    (ForestTree.jasmine, 'av_flight_duration'): ('flight_duration_average', None),
    (ForestTree.jasmine, 'sd_flight_duration'): ('flight_duration_standard_deviation', None),
    (ForestTree.jasmine, 'diameter'): ('distance_diameter', None),
    
    (ForestTree.willow, "num_in_call"): ("call_incoming_count", None),
    (ForestTree.willow, "num_in_caller"): ("call_incoming_degree", None),
    (ForestTree.willow, "total_mins_in_call"): ("call_incoming_duration", None),
    (ForestTree.willow, "num_out_call"): ("call_outgoing_count", None),
    (ForestTree.willow, "num_out_caller"): ("call_outgoing_degree", None),
    (ForestTree.willow, "total_mins_out_call"): ("call_outgoing_duration", None),
    
    (ForestTree.willow, "num_r"): ("text_incoming_count", None),
    (ForestTree.willow, "num_r_tel"): ("text_incoming_degree", None),
    (ForestTree.willow, "total_char_r"): ("text_incoming_length", None),
    (ForestTree.willow, "num_s"): ("text_outgoing_count", None),
    (ForestTree.willow, "num_s_tel"): ("text_outgoing_degree", None),
    (ForestTree.willow, "total_char_s"): ("text_outgoing_length", None),
}
