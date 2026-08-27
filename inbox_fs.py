import os
import re
from datetime import datetime


def first_line_slug(text):
    line = text.splitlines()[0].strip() if text else ""
    line = re.sub(r"^#+\s*", "", line)
    line = re.sub(r"[^\w\s-]", "", line, flags=re.UNICODE)
    line = re.sub(r"\s+", "-", line).strip("-")
    return line[:60] if line else "note"


def park_path(folder, ext, text):
    ext = str(ext).lstrip(".")
    os.makedirs(folder, exist_ok=True)
    base = "{}-{}".format(datetime.now().strftime("%Y-%m-%d-%H%M%S"), first_line_slug(text))
    path = os.path.join(folder, "{}.{}".format(base, ext))
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, "{}-{}.{}".format(base, n, ext))
        n += 1
    return path
