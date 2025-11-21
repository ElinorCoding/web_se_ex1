NAME = "english_word"
DESCRIPTION = "英文单词（基于 wordfreq 频率与噪声过滤）"

import re

try:
    from wordfreq import zipf_frequency as _zipf
except Exception:
    _zipf = None


COMMON_NON_WORDS = [
    r"^[a-z]{1,2}$",  # 过短字母串
    r"^(qwe|asd|zxc|poi|lkj|mnb|qaz|wsx|edc|abc)+$",  # 键盘序列
    r"^(aaa|bbb|ccc|ddd|eee|fff|ggg|hhh|iii|jjj|kkk|lll|mmm|nnn|ooo|ppp|qqq|rrr|sss|ttt|uuu|vvv|www|xxx|yyy|zzz)+$",
]

PINYIN_SURNAMES = {
    'wang', 'li', 'zhang', 'liu', 'chen', 'yang', 'zhao', 'wu', 'zhou', 'xu',
    'sun', 'hu', 'zhu', 'gao', 'lin', 'he', 'guo', 'ma', 'lu', 'dong', 'xie',
    'song', 'shi', 'tang', 'feng', 'yu', 'cai', 'pan', 'deng', 'xiao', 'tian',
    'liang', 'wei', 'jiang', 'han', 'fan', 'peng', 'yuan', 'cao', 'fu', 'ren',
    'fang', 'jing', 'cheng', 'qian', 'mo', 'qiu', 'long', 'chang', 'qiao',
    'mei', 'hua', 'jin', 'tao', 'qi', 'wen', 'yan', 'bao', 'du', 'ye', 'su',
    'pei', 'luo', 'shan', 'hou', 'qin', 'ruan', 'tan', 'lv'
}


def _is_noise_word(word: str) -> bool:
    wl = word.lower()
    if wl in PINYIN_SURNAMES:
        return True
    for pat in COMMON_NON_WORDS:
        if re.fullmatch(pat, wl):
            return True
    return False


def _is_common_english_word(word: str, min_freq: float = 4.0) -> bool:
    if not word or len(word) < 3:
        return False
    if _zipf is None:
        # 若缺少 wordfreq，则保守返回 False，避免误报
        return False
    try:
        return _zipf(word.lower(), 'en') >= min_freq
    except Exception:
        return False


def _greedy_split_english(segment: str, min_freq: float):
    s = segment.lower()
    i, n = 0, len(s)
    out = []
    while i < n:
        match = None
        for j in range(n, i, -1):
            sub = s[i:j]
            if _is_common_english_word(sub, min_freq):
                out.append(sub)
                i = j
                match = True
                break
        if not match:
            i += 1
    return out


def detect(ctx):
    # 提取字母段
    segments = re.findall(r"[A-Za-z]+", ctx.password)
    if not segments:
        return False

    # 只要存在一个较强英文单词，即判为英文词类
    for seg in segments:
        words = _greedy_split_english(seg, min_freq=4.0)
        for w in words:
            if len(w) < 3:
                continue
            if _is_noise_word(w):
                continue
            if _is_common_english_word(w, min_freq=4.0):
                return True
    return False
