
## Survey Question Types
FREE_RESPONSE = "free_response"
CHECKBOX = "checkbox"
RADIO_BUTTON = "radio_button"
SLIDER = "slider"
INFO_TEXT_BOX = "info_text_box"

ALL_QUESTION_TYPES = {
    FREE_RESPONSE,
    CHECKBOX,
    RADIO_BUTTON,
    SLIDER,
    INFO_TEXT_BOX
}

NUMERIC_QUESTIONS = {
    RADIO_BUTTON,
    SLIDER,
    FREE_RESPONSE
}

## Free Response text field types (answer types)
FREE_RESPONSE_NUMERIC = "NUMERIC"
FREE_RESPONSE_SINGLE_LINE_TEXT = "SINGLE_LINE_TEXT"
FREE_RESPONSE_MULTI_LINE_TEXT = "MULTI_LINE_TEXT"

TEXT_FIELD_TYPES = {
    FREE_RESPONSE_NUMERIC,
    FREE_RESPONSE_SINGLE_LINE_TEXT,
    FREE_RESPONSE_MULTI_LINE_TEXT
}

## Comparators
COMPARATORS = {
    "<",
    ">",
    "<=",
    ">=",
    "==",
    "!="
}

NUMERIC_COMPARATORS = {
    "<",
    ">",
    "<=",
    ">="
}
