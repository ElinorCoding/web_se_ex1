import os
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(ROOT, "categories", "keyboard_pattern.py")

spec = importlib.util.spec_from_file_location("keyboard_pattern", MODULE_PATH)
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)  # type: ignore

class Ctx:
    def __init__(self, password: str):
        self.password = password
        self.mail = "u@example.com"
        self.username = "user"

CASES_TRUE = [
    "qwerty",    # horizontal
    "asdfg",     # horizontal
    "1234",      # horizontal (digits)
    "qaz",       # vertical column
    "esz",       # diagonal down-left
    "rfv",       # vertical/diagonal column
    "WSX",       # case-insensitive
    "!@#$",      # shift symbols on digit row (normalized to 1234)
]

CASES_FALSE = [
    "qxa",
    "apple",
    "pass123",   # not a straight keyboard run
    ".,/",       # length 3 horizontal should not pass (need 4)
    "li6ping?",  # should NOT be detected
    ")_+",       # shift row length 3 should not pass
    "qsc",       # remove meaningless ↘ diagonal (q->s->c) matches
]


def run():
    ok, fail = 0, 0
    for s in CASES_TRUE:
        if kb.detect(Ctx(s)):
            ok += 1
        else:
            print("Expected True, got False:", s)
            fail += 1
    for s in CASES_FALSE:
        if not kb.detect(Ctx(s)):
            ok += 1
        else:
            print("Expected False, got True:", s)
            fail += 1
    print(f"Selftest passed: {ok}, failed: {fail}")

if __name__ == "__main__":
    run()
