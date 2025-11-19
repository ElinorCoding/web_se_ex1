NAME = "dictionary_order"
DESCRIPTION = "连续字符序列（如 123456、abcdef 或其倒序）"

import re


def _same_class(a: str, b: str) -> bool:
    return (a.isdigit() and b.isdigit()) or (a.isalpha() and b.isalpha())


def _has_linear_run(token: str, min_len: int = 4) -> bool:
    if len(token) < min_len:
        return False
    asc = 1
    desc = 1
    for i in range(len(token) - 1):
        a, b = token[i], token[i + 1]
        if not _same_class(a, b):
            asc = 1
            desc = 1
            continue
        d = ord(b) - ord(a)
        asc = asc + 1 if d == 1 else 1
        desc = desc + 1 if d == -1 else 1
        if asc >= min_len or desc >= min_len:
            return True
    return False


def detect(ctx):
    s = ctx.password.lower()
    for token in re.findall(r"[a-z0-9]+", s):
        if _has_linear_run(token, min_len=4):
            return True
    return False
