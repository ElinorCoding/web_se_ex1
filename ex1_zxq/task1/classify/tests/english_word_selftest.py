import os
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(ROOT, "categories", "english_word.py")

spec = importlib.util.spec_from_file_location("english_word", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore

class Ctx:
    def __init__(self, password: str):
        self.password = password
        self.mail = "u@example.com"
        self.username = "user"

CASES_TRUE = [
    "password",
    "Summer2024",
    "helloWorld",
    "welcome!",
]

CASES_FALSE = [
    "qwerty",       # 键盘序列，不一定视为英文单词（此处按英文词检测应尽量不命中）
    "li6ping",      # 类人名/拼音结构
    "xqz",          # 罕见串
]


def run():
    ok, fail = 0, 0
    for s in CASES_TRUE:
        if mod.detect(Ctx(s)):
            ok += 1
        else:
            print("Expected True, got False:", s)
            fail += 1
    for s in CASES_FALSE:
        if not mod.detect(Ctx(s)):
            ok += 1
        else:
            print("Expected False, got True:", s)
            fail += 1
    print(f"Selftest passed: {ok}, failed: {fail}")

if __name__ == "__main__":
    run()
