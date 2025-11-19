"""日期类口令检测（增强版，加入合法性校验）

思路（在原实现基础上增强两点）：
1) 解析：从口令中提取可能的日期片段（支持分隔符 - / . 以及纯数字 4/6/8 位）。
2) 校验：不再直接依赖 strptime 的 %y 百年映射；对 Y/M/D 进行显式合法性校验（闰年、月份天数），
    并对两位年采用可控阈值映射（30-99 -> 1930-1999，00-29 -> 2000-2029，可按需要调整）。
3) 判定：
    - 若密码整体就是一个有效日期（带或不带分隔符），判定为日期类。
    - 若密码中含有一个有效日期子串，且去掉该子串后的剩余字符数不超过 2，也判定为日期类。
    - 若出现两个连续年份（YYYYYYYY）也视为日期类。
"""

NAME = "date_like"
DESCRIPTION = "日期样式（多格式提取+校验）"

import re
from datetime import datetime

NOISE_NUMBERS = {"123456", "654321", "123123", "1234", "4321", "1314", "123321"}

# 两位年分界（含义：00-29 -> 2000-2029；30-99 -> 1930-1999）
TWO_DIGIT_YEAR_SPLIT = 30

YEAR_PAIR_PATTERN = re.compile(r"^(19|20)\d{2}(19|20)\d{2}$")


def _is_leap(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _days_in_month(year: int, month: int) -> int:
    if month < 1 or month > 12:
        return 0
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    return 29 if _is_leap(year) else 28


def _map_two_digit_year(yy: int) -> int:
    return 1900 + yy if yy >= TWO_DIGIT_YEAR_SPLIT else 2000 + yy


def _valid_ymd(year: int, month: int, day: int) -> bool:
    if year < 1900 or year > 2039:
        return False
    if month < 1 or month > 12:
        return False
    dim = _days_in_month(year, month)
    return 1 <= day <= dim


def _valid_ym(year: int, month: int) -> bool:
    if year < 1900 or year > 2039:
        return False
    return 1 <= month <= 12


def _valid_md(month: int, day: int) -> bool:
    if month < 1 or month > 12:
        return False
    # 无年份时按非闰年 28 天的保守校验，避免大量 0229 误报
    dim = 29 if month == 2 else (31 if month in (1, 3, 5, 7, 8, 10, 12) else 30)
    return 1 <= day <= dim

def _extract_date_candidates(pwd: str):
    """提取并校验可能的日期片段，返回通过合法性校验的候选集合（纯数字形式）。"""
    candidates = set()
    occupied = []

    # 1) 含分隔符的日期片段，如 2023-1-2 / 2023.01.02 / 12/31/2020 / 2024/02
    for m in re.finditer(r"\d{1,4}[-/\.]\d{1,4}(?:[-/\.]\d{1,4})?", pwd):
        raw = m.group()
        cleaned = re.sub(r"[-/\.]", "", raw)
        candidates.add(cleaned)
        occupied.append((m.start(), m.end()))

    # 2) 纯数字片段 4-8 位
    for m in re.finditer(r"(?<!\d)\d{4,8}(?!\d)", pwd):
        # 避免与分隔符片段重叠重复
        if any(start <= m.start() < end or start < m.end() <= end for start, end in occupied):
            continue
        candidates.add(m.group())

    valid = set()
    for c in candidates:
        # 噪声与重复过滤
        if c in NOISE_NUMBERS:
            continue
        if re.fullmatch(r"(\d)\1{3,}", c):
            continue
        if len(c) not in (4, 6, 8):
            continue

        # 连续两年，如 19901991
        if YEAR_PAIR_PATTERN.fullmatch(c):
            valid.add(c)
            continue

        if _is_valid_date_string(c):
            valid.add(c)
    return valid


def _is_valid_date_string(s: str) -> bool:
    """按长度分别尝试多种组合并进行显式合法性校验。"""
    n = len(s)
    if n == 8:
        # 尝试 Y(4) M(2) D(2)
        y = int(s[0:4]); m = int(s[4:6]); d = int(s[6:8])
        if _valid_ymd(y, m, d):
            return True
        # 尝试 D(2) M(2) Y(4)
        d = int(s[0:2]); m = int(s[2:4]); y = int(s[4:8])
        if _valid_ymd(y, m, d):
            return True
        # 尝试 M(2) D(2) Y(4)
        m = int(s[0:2]); d = int(s[2:4]); y = int(s[4:8])
        if _valid_ymd(y, m, d):
            return True
        return False
    elif n == 6:
        # 可能是 YYMMDD
        yy = int(s[0:2]); m = int(s[2:4]); d = int(s[4:6])
        y = _map_two_digit_year(yy)
        if _valid_ymd(y, m, d):
            return True
        # 可能是 DDMMYY
        d = int(s[0:2]); m = int(s[2:4]); yy = int(s[4:6]); y = _map_two_digit_year(yy)
        if _valid_ymd(y, m, d):
            return True
        # 可能是 MMDDYY
        m = int(s[0:2]); d = int(s[2:4]); yy = int(s[4:6]); y = _map_two_digit_year(yy)
        if _valid_ymd(y, m, d):
            return True
        # 也可能是 YYYYMM（认为是部分日期，也可接受）
        y = int(s[0:4]); m = int(s[4:6])
        if 1900 <= y <= 2039 and _valid_ym(y, m):
            return True
        return False
    elif n == 4:
        # YYYY 或 MMDD
        y = int(s)
        if 1900 <= y <= 2039:
            return True
        m = int(s[0:2]); d = int(s[2:4])
        if _valid_md(m, d):
            return True
        return False
    else:
        return False


def detect(ctx):
    pw = ctx.password.strip()
    # 快速路径：整体就是日期（包含或不包含分隔符）
    compact = re.sub(r"[-/.]", "", pw)
    if compact.isdigit() and len(compact) in (4, 6, 8):
        if YEAR_PAIR_PATTERN.fullmatch(compact) or _is_valid_date_string(compact):
            return True
    # 诸如 2023-01-02 / 23/1/2
    if re.fullmatch(r"\d{1,4}[-/\.]\d{1,2}(?:[-/\.]\d{1,2})?", pw):
        if _is_valid_date_string(compact):
            return True

    candidates = _extract_date_candidates(pw)
    if not candidates:
        return False

    for c in candidates:
        if compact == c:
            return True
        if c in pw:
            non_len = len(pw) - len(c)
            if non_len <= 2:
                return True
    return False
