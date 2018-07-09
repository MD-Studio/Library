from datetime import datetime, date

from mdstudio.utc import to_utc_string, to_date_string


def convert_obj_to_json(document):
    if isinstance(document, dict):
        iters = document.items()
    elif isinstance(document, list):
        iters = enumerate(document)
    else:
        return

    for key, value in iters:
        if isinstance(value, date) and not isinstance(value, datetime):
            document[key] = to_date_string(value)
        if isinstance(value, datetime):
            document[key] = to_utc_string(value)
        else:
            convert_obj_to_json(value)

    return document
