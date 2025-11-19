NAME = "repeated_chars"
DESCRIPTION = "重复字符或重复单元口令"

import re


def has_repeating_unit(s: str) -> bool:
    return bool(re.fullmatch(r"(.+?)\1+", s))


def detect(ctx):
    pw = ctx.password.lower()
    if len(pw) >= 3 and len(set(pw)) == 1:
        return True
    if len(pw) >= 6 and has_repeating_unit(pw):
        return True
    return False
