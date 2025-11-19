NAME = "numeric_only"
DESCRIPTION = "纯数字口令"


def detect(ctx):
    pw = ctx.password
    return pw.isdigit() and len(pw) >= 4
