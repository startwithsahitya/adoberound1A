import re

def is_garbage(text):
    t = text.strip()
    if not t:
        return True
    if re.fullmatch(r"[^\w\s]+", t):  # only symbols
        return True
    if t.isdigit():  # only digits
        return True
    if len(t) <= 2 and not t.isalpha():  # short junk
        return True
    return False
