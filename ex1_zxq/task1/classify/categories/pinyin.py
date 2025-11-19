NAME = "pinyin"
DESCRIPTION = "疑似拼音（词典匹配或启发式拼音结构）"

import os
import re

# 加载拼音音节表（忽略以 # 开头的注释行），兼容新目录结构
def _load_pinyin_syllables():
    bases = []
    try:
        base = os.path.dirname(__file__)
        # 新路径：code/classify/categories -> ../../dicts
        bases.append(os.path.join(base, "..", "..", "dicts", "pinyin_syllables.txt"))
        # 兼容旧路径：code/categories -> ../dicts（若用户单独运行旧结构）
        bases.append(os.path.join(base, "..", "dicts", "pinyin_syllables.txt"))
        for path in bases:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return {l.strip().lower() for l in f if l.strip() and not l.lstrip().startswith("#")}
    except Exception:
        pass
    return {
        "zhang","wang","li","zhao","chen","yang","wu","liu","zhou","sun","guo","lin","he","ma","gao",
        "xue","feng","ying","hua","long","tian","ming","jun","hong","lv","nv"
    }


WORDS = _load_pinyin_syllables()

try:
    from wordfreq import zipf_frequency as _zipf
except Exception:
    _zipf = None

EN_COMMON_FALLBACK = {
    "password","qwerty","admin","hello","love","secret","dragon","monkey","login","user","computer","internet",
    "music","summer","winter","spring","autumn","football","baseball","welcome","flower"
}


def normalize_leet(s: str) -> str:
    table = str.maketrans({
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "8": "b",
        "@": "a",
        "$": "s",
        "!": "i",
    })
    return s.lower().translate(table)


def _is_strong_english(w: str) -> bool:
    w = w.lower()
    if len(w) < 3:
        return False
    if _zipf:
        try:
            if _zipf(w, "en") >= 3.0:
                return True
        except Exception:
            pass
    return w in EN_COMMON_FALLBACK


def _is_valid_v_usage(t: str) -> bool:
    if "v" not in t:
        return True
    # 允许 nv/nve/lv/lve/lue 等组合，其它视为非拼音
    return any(x in t for x in ("nv", "nve", "lv", "lve", "lue"))


def detect(ctx):
    # 若原始口令不含任何字母，则直接排除（避免数字被 leet 归一化成字母导致误判）
    if not re.search(r"[A-Za-z]", ctx.password):
        return False
    pw = normalize_leet(ctx.password)
    letters = re.findall(r"[a-zA-Z]+", pw)
    if not letters:
        return False
    for token in letters:
        t = token.lower()
        if len(t) < 3:
            continue
        if not _is_valid_v_usage(t):
            continue
        if _is_strong_english(t):
            continue
        # 计算拼音覆盖率（最长匹配贪心）
        i = 0
        n = len(t)
        covered = 0
        while i < n:
            hit = None
            for j in range(n, i, -1):
                if t[i:j] in WORDS:
                    hit = j
                    break
            if hit is None:
                i += 1
            else:
                covered += (hit - i)
                i = hit
        cov = covered / n
        if cov >= 0.8 and (covered >= 4 or (covered >= 3 and t.endswith(("ng", "ang", "eng", "ing")))):
            return True
    return False
