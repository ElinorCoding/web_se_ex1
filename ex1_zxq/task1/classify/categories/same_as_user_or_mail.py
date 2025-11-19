NAME = "same_as_user_or_mail"
DESCRIPTION = "与用户名/邮箱完全相同"

def detect(ctx):
    pw = ctx.password.strip().lower()
    cands = [ctx.mail.lower(), ctx.mail_local.lower()]
    if ctx.username:
        cands.append(ctx.username.strip().lower())
    return pw in cands
