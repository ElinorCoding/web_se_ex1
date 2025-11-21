NAME = "partial_like_user_or_mail"
DESCRIPTION = "与用户名/邮箱部分相同（子串长度>=4）"

import re


def split_tokens(s: str):
    return [t for t in re.split(r"[^a-zA-Z0-9]+", s.lower()) if t]


def detect(ctx):
    pw = ctx.password.lower()
    tokens = []
    tokens.extend(split_tokens(ctx.mail_local))
    if ctx.username:
        tokens.extend(split_tokens(ctx.username))
    tokens = [t for t in tokens if len(t) >= 4]
    return any(t in pw for t in tokens)
