#!/usr/bin/env python3
"""
仅用于研究与教学的“离线口令猜解模拟”脚本：
    - 训练：从数据集中统计高频片段与模式（不连接任何外部服务）
    - 生成：基于统计结果 + 内置高频模式列表 + 启发式规则生成候选
    - 评估：在已持有的完整口令集合上评估“前K次”命中率（--evaluate）
    - 演示/模拟：针对指定或随机抽取目标集合，模拟猜解过程记录时间与命中顺序（--simulate-targets）

内置高频模式（无需额外参数）：包含分析报告提取的常见数字序列、键盘序列、英文单词、年份/日期组合等，始终在生成过程的最前序列化输出，以模拟“先猜最可能”的策略。

演示模式参数：
    --simulate-targets   启用针对目标集合的模拟模式（不使用全集评估逻辑）
    --target <pw>        指定单个目标口令，可用逗号分隔多个
    --target-file <file> 从文件读取目标口令（每行一个）
    --random-targets N   从数据集中随机抽取 N 个不同口令为目标
    --demo               在开始模拟前打印目标集合
    --delay-ms <int>     每次猜测后延迟毫秒数以模拟开销（默认0）
    --metrics-out <file> 将模拟指标写出为 JSON（破解次数、耗时、每个目标的统计）

用法示例（PowerShell）：
    python .\code\guess\guess.py --dataset csdn --budget 100000 --evaluate
    python .\code\guess\guess.py --dataset yahoo --budget 200000 --out .\guesses.txt
    python .\code\guess\guess.py --dataset auto --simulate-targets --random-targets 3 --budget 50000 --demo
    python .\code\guess\guess.py --simulate-targets --target 123456,password --delay-ms 2 --budget 200000 --metrics-out .\metrics.json

数据来源（已在仓库中）：
    code/processed_dataset/csdn_mail_password_username.txt
    code/processed_dataset/yahoo_mail_password.txt
"""
import argparse
import os
import re
import random
import time
import json
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import math
import itertools
import string

ROOT = os.path.dirname(os.path.dirname(__file__))
PROC_DIR = os.path.join(ROOT, "processed_dataset")
THIS_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(THIS_DIR, "output")
GENERATE_DIR = os.path.join(OUTPUT_DIR, "generate")
EVALUATE_DIR = os.path.join(OUTPUT_DIR, "evaluate")
SIMULATE_DIR = os.path.join(OUTPUT_DIR, "simulate")
for _d in (OUTPUT_DIR, GENERATE_DIR, EVALUATE_DIR, SIMULATE_DIR):
    os.makedirs(_d, exist_ok=True)

# 本地数据优先目录 (GUI/打包时可放入此处)
GUESS_DATA_DIR = os.path.join(THIS_DIR, 'data')
os.makedirs(GUESS_DATA_DIR, exist_ok=True)

CSDN_FILE = os.path.join(GUESS_DATA_DIR, "csdn_5000.txt") if os.path.exists(os.path.join(GUESS_DATA_DIR, "csdn_5000.txt")) else os.path.join(PROC_DIR, "csdn_mail_password_username.txt")
YAHOO_FILE = os.path.join(GUESS_DATA_DIR, "yahoo_5000.txt") if os.path.exists(os.path.join(GUESS_DATA_DIR, "yahoo_5000.txt")) else os.path.join(PROC_DIR, "yahoo_mail_password.txt")

def load_dataset(name: str):
    recs = []
    path = None
    if name == "csdn":
        path = CSDN_FILE
    elif name == "yahoo":
        path = YAHOO_FILE
    else:
        # auto: 优先存在哪个用哪个
        path = CSDN_FILE if os.path.exists(CSDN_FILE) else YAHOO_FILE
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"未找到数据文件: {path}")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            parts = line.split(":")
            # 兼容两种格式：mail:password 或 mail:password:username
            if len(parts) == 2:
                mail, password = parts
                username = ""
            else:
                mail, password, username = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
            recs.append({"mail": mail, "password": password, "username": username})
    return recs

def tokenize_alpha_numeric(pw: str):
    alphas = re.findall(r"[A-Za-z]+", pw)
    nums = re.findall(r"\d+", pw)
    return alphas, nums

def local_part(email: str) -> str:
    return email.split("@", 1)[0].lower() if "@" in email else email.lower()

def domain_stub(email: str) -> str:
    if "@" not in email: return ""
    dom = email.split("@",1)[1].lower()
    dom = dom.split(".")[0]
    return dom

def train_stats(records, top_k=5000):
    alpha_counter = Counter()
    num_counter = Counter()
    suffix_counter = Counter()
    lp_counter = Counter()
    un_counter = Counter()
    for r in records:
        pw = r["password"]
        alphas, nums = tokenize_alpha_numeric(pw)
        for a in alphas:
            alpha_counter[a.lower()] += 1
        for n in nums:
            num_counter[n] += 1
        # 常见后缀（最后2~6位数字或 ! ? @ 组合）
        m = re.search(r"([0-9]{2,6}|[!@#$%^&*]{1,3})$", pw)
        if m:
            suffix_counter[m.group(1)] += 1
        lp = local_part(r["mail"])
        if lp: lp_counter[lp] += 1
        un = r.get("username","") or ""
        if un: un_counter[un.lower()] += 1
    alphat = [w for w,_ in alpha_counter.most_common(top_k)]
    numt = [w for w,_ in num_counter.most_common(top_k)]
    sufft = [w for w,_ in suffix_counter.most_common(200)]
    lpt = [w for w,_ in lp_counter.most_common(2000)]
    unt = [w for w,_ in un_counter.most_common(2000)]
    return {
        "alpha": alphat,
        "num": numt,
        "suffix": sufft,
        "locals": lpt,
        "usernames": unt
    }

# 轻量英文/拼音词表（可从项目里的词典中加载）
def load_pinyin_words():
    # 优先使用 code/guess/data 中的字典（用于打包/离线运行），否则回退到仓库 dicts
    path = os.path.join(THIS_DIR, 'data', "pinyin_syllables.txt")
    if not os.path.exists(path):
        path = os.path.join(ROOT, "code", "dicts", "pinyin_syllables.txt")
    words = set()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip().lower()
                if s and not s.startswith("#"):
                    words.add(s)
    except Exception:
        pass
    # 常见姓名/词片段补齐
    words.update(["zhang","wang","li","zhao","chen","yang","wu","liu","zhou","sun","hua","xue","ming","jun","tian","long","lin","gao","lv","nv"])
    return words

EN_FALLBACK = {
  "password","qwerty","admin","welcome","love","hello","secret","dragon","monkey","letmein","football","baseball","flower","computer","internet","login","user","music","spring","summer","winter","autumn","iloveyou"
}

def caps_variants(w: str):
    # 简化：首字母大写 + 全小写 + 全大写
    yield w
    if len(w) > 0:
        yield w.capitalize()
    if len(w) <= 8:
        yield w.upper()

def leet_variants(w: str):
    table = str.maketrans({'a':'@','e':'3','i':'!','o':'0','s':'$','t':'7','b':'8','l':'1'})
    # 只做一层替换，控制爆炸
    yield w
    v = w.translate(table)
    if v != w:
        yield v

COMMON_SUFFIX = ["", "1","12","123","1234","12345","123456","2023","2024","2025","!","!1","!23","@123","!2024"]
COMMON_PREFIX = ["", "20","19"]

KEYBOARD = ["qwerty","asdfgh","zxcvbn","qazwsx","1q2w3e","poiuyt","lkjhgf"]

# 内置高频模式（基于报告汇总的代表性子集，控制规模）
HIGH_FREQ_TOKENS = [
    # —— 常见弱口令（综合 Top） ——
    "123456","1234567","12345678","123456789","1234567890",
    "111111","11111111","111111111","000000","00000000","88888888",
    "123123","123123123","987654321","147258369",
    "admin","password","hello","wang","winter",

    # —— 高频连续/字典序片段 ——
    "123","234","345","456","567","678","789","890","321","987",
    "1234","12345","1234567","12345678","123456789","0123","9876","98765","abcd",

    # —— 键盘序列（横向/纵向/对角，含 Yahoo & CSDN 报告） ——
    "qwerty","asdfgh","zxcvbn",
    "qwe","wer","ert","rty","tyu","yui","uio","iop","poi","rew","tre",
    "asd","sdf","dfg","fgh","ghj","hjk","jkl","dsa","fds","gfd",
    "zxc","xcv","cvb","vbn","bnm",
    "qaz","wsx","edc","cde","xsw","zaq","aq1","1qa","2ws","sw2","de3",
    "QAZ","WSX","EDC","CDE","XSW","ZAQ","!@#","@#$",

    # —— 英文高频词（Yahoo/CSDN Top） ——
    "love","book","you","king","happy","man","china","boy","good","and",
    "dog","baby","the","girl","red","money",

    # —— 年份（Top 年份） ——
    "2008","2009","2007","2006","2005","2004","2002","2001","2010",
    "1987","1988","1989","1986","1985","1984","1990",

    # —— 高频 MMDD（Yahoo & CSDN） ——
    "1010","1123","1225","1020","1214","1231","1213","1023","1031","1024",
    "0117","1224","1022","1001","1025","1028","1012","1230","0123",

    # —— DDMM（Yahoo & CSDN） ——
    "1701","2911","1812","1310","2204","2512","1309","2205","2412","2408",
    "1412","1312","2311","2312","2510","2111","1311","2612","2310","2611",

    # —— YYYYMM（Yahoo & CSDN） ——
    "198811","198610","202003","192003","198911","200808","197712","197511","202004","198812",
    "198611","198712","198512","198711","198710","198612","198912",

    # —— YYYYMMDD（CSDN Top） ——
    "20080808","19491001","19841010","19841020","19871024","19871010","19881010","19871020","19871025","19881212",

    # —— YYYYYYYY（重复年份） ——
    "19841984","19851985","19911991","19561956","19691969",
    "20082008","20102010","20092009","19871987","19861986","19821982","19881988","20052005","19891989",

    # —— 情感数字短语 ——
    "520","1314"
]

# 将高频集合按类别拆分，便于分散到各模式
HF_NUMERIC = [
    "123456","1234567","12345678","123456789","1234567890",
    "111111","11111111","111111111","000000","00000000","88888888",
    "123123","123123123","987654321","147258369","520","1314"
]
HF_KEYBOARD = [
    "qwerty","asdfgh","zxcvbn",
    "qwe","wer","ert","rty","tyu","yui","uio","iop","poi","rew","tre",
    "asd","sdf","dfg","fgh","ghj","hjk","jkl","dsa","fds","gfd",
    "zxc","xcv","cvb","vbn","bnm",
    "qaz","wsx","edc","cde","xsw","zaq","aq1","1qa","2ws","sw2","de3",
    "QAZ","WSX","EDC","CDE","XSW","ZAQ","!@#","@#$"
]
HF_ENGLISH = [
    "admin","password","hello","wang","winter",
    "love","book","you","king","happy","man","china","boy","good","and",
    "dog","baby","the","girl","red","money","abcd"
]
HF_YEARS = ["2008","2009","2007","2006","2005","2004","2002","2001","2010","1987","1988","1989","1986","1985","1984","1990"]
HF_MMDD = [
    "1010","1123","1225","1020","1214","1231","1213","1023","1031","1024",
    "0117","1224","1022","1001","1025","1028","1012","1230","0123"
]
HF_DDMM = [
    "1701","2911","1812","1310","2204","2512","1309","2205","2412","2408",
    "1412","1312","2311","2312","2510","2111","1311","2612","2310","2611"
]
HF_YYYYMM = [
    "198811","198610","202003","192003","198911","200808","197712","197511","202004","198812",
    "198611","198712","198512","198711","198710","198612","198912"
]
HF_YYYYMMDD = [
    "20080808","19491001","19841010","19841020","19871024","19871010","19881010","19871020","19871025","19881212"
]
HF_YYYYYYYY = [
    "19841984","19851985","19911991","19561956","19691969","20082008","20102010","20092009","19871987","19861986","19821982","19881988","20052005","19891989"
]

# ---------------- 外部报告频率解析 -----------------
def gen_builtin_high_freq(suffixes):
    # 仅输出基础与大小写变体；不再内建附加后缀（统一由外部包装器处理）
    for tok in HIGH_FREQ_TOKENS:
        yield tok
        if tok.isalpha() and len(tok) <= 8:
            yield tok.lower()
            yield tok.upper()
            yield tok.capitalize()

def gen_user_related(locals_top, users_top, suffixes):
    for base in locals_top + users_top:
        base = base.strip()
        if not base: continue
        for s in suffixes or COMMON_SUFFIX:
            yield f"{base}{s}"
            # 简单替换 o->0 a->@ 等
            for v in leet_variants(base):
                if v != base:
                    yield f"{v}{s}"

def gen_english(alpha_top, suffixes, high_priority=None):
    # 仅输出英文单词的大小写/leet 变体本体；不再附加后缀（统一由外部包装器处理）
    base_words = (list(high_priority or []) + list(EN_FALLBACK)) + alpha_top[:2000]
    seen = set()
    for w in base_words:
        w = w.lower()
        if len(w) < 3: continue
        if w in seen: continue
        seen.add(w)
        for cv in caps_variants(w):
            for lv in leet_variants(cv):
                yield lv

def gen_pinyin(alpha_top, suffixes, pinyin_dict):
    # 从训练片段中过滤出疑似拼音词（在词典中或由多个音节构成）
    def pinyin_like(tok: str) -> bool:
        t = tok.lower()
        # 简单：任意子串在词典里则认可
        if t in pinyin_dict: return True
        # 贪心拼接覆盖
        i, n, cov = 0, len(t), 0
        while i < n:
            hit = None
            for j in range(n, i, -1):
                if t[i:j] in pinyin_dict:
                    hit = j
                    break
            if hit is None: i += 1
            else:
                cov += (hit - i); i = hit
        return cov >= max(3, int(0.8*len(t)))
    cand = [w.lower() for w in alpha_top[:4000] if len(w)>=3 and pinyin_like(w)]
    seen = set()
    for w in cand:
        if w in seen: continue
        seen.add(w)
        for s in suffixes or COMMON_SUFFIX:
            yield f"{w}{s}"

def gen_numeric(num_top, high_priority=None):
    # 纯数字：按训练高频，限长度 6~10
    hp = list(high_priority or [])
    for n in hp:
        if n.isdigit() and 2 <= len(n) <= 12:
            yield n
    for n in num_top:
        if 4 <= len(n) <= 10:
            yield n
    # 常见年份与日期组合
    years = list(range(1990, 2026))
    for y in years:
        yield f"{y}"
    # yyyymm / yyyymmdd 的常见范围
    for y in years:
        for m in range(1,13):
            yield f"{y}{m:02d}"
            for d in (1, 11, 22, 28):
                yield f"{y}{m:02d}{d:02d}"

def gen_dates(priority_years=None, priority_mmdd=None, priority_ddmm=None, priority_yyyymm=None, priority_yyyymmdd=None, priority_yyyyyyyy=None):
    # 少量格式组合，控制爆炸
    # 先输出高频年份与日期变体
    if priority_yyyymmdd:
        for s in priority_yyyymmdd:
            if re.fullmatch(r"\d{8}", s):
                y, m, d = s[:4], s[4:6], s[6:8]
                yield f"{y}-{m}-{d}"; yield f"{y}/{m}/{d}"; yield f"{y}{m}{d}"
    if priority_yyyyyyyy:
        for s in priority_yyyyyyyy:
            if re.fullmatch(r"\d{8}", s):
                yield s
    if priority_mmdd:
        for s in priority_mmdd:
            if re.fullmatch(r"\d{4}", s):
                yield s
    if priority_ddmm:
        for s in priority_ddmm:
            if re.fullmatch(r"\d{4}", s):
                yield s
    if priority_yyyymm:
        for s in priority_yyyymm:
            if re.fullmatch(r"\d{6}", s):
                yield s
    if priority_years:
        for y in priority_years:
            if re.fullmatch(r"\d{4}", y):
                yield y

    years = list(range(1990, 2026))
    for y in years:
        for m in range(1,13):
            for d in (1, 11, 22, 28):
                yield f"{y}-{m:02d}-{d:02d}"
                yield f"{y}/{m:02d}/{d:02d}"
                yield f"{y}{m:02d}{d:02d}"
    # mmdd、yymmdd
    for y in range(0, 100):
        for m in range(1,13):
            for d in (1,11,22,28):
                yield f"{y:02d}{m:02d}{d:02d}"
    for m in range(1,13):
        for d in range(1,29):
            yield f"{m:02d}{d:02d}"

def gen_keyboard_and_repeats(priority=None):
    pr = list(priority or [])
    # 仅输出键盘序列与重复串本体；不再附加后缀（统一由外部包装器处理）
    for kb in pr:
        yield kb
    for kb in KEYBOARD:
        yield kb
    for ch in "0123456789abcdefghijklmnopqrstuvwxyz":
        for k in range(6, 11):
            yield ch * k

def gen_numeric_exhaustive_upto7():
    # 穷举 1..7 位数字（含前导0）按长度递增、字典序输出
    digits = '0123456789'
    for l in range(1, 8):
        for tup in itertools.product(digits, repeat=l):
            yield ''.join(tup)

def _letter_affixes(max_len=3):
    # 生成长度0..max_len的小写字母前后缀
    letters = string.ascii_lowercase
    yield ''
    for l in range(1, max_len+1):
        for tup in itertools.product(letters, repeat=l):
            yield ''.join(tup)

def apply_one_side_affixes(base: str, affixes_iter):
    """对给定 base 返回：
    - 不带附加的 base
    - 以每个 affix 为前缀的变体
    - 以每个 affix 为后缀的变体
    不产生同时两侧都附加的组合（即不产生 pre+base+suffix）。
    """
    yield base
    for a in affixes_iter:
        if not a:
            continue
        yield a + base
        yield base + a

def gen_dates_with_letter_affixes(max_affix_len=3):
    # 对 YYYYMMDD 与 YYMMDD 生成，字母前后缀各 0..max_affix_len
    affixes = list(_letter_affixes(max_affix_len))
    # YYYYMMDD 合法日期
    for y in range(1990, 2026):
        for m in range(1, 13):
            for d in range(1, 32):
                try:
                    # 粗略合法性：排除 2 月 >29、30天月 >30等
                    if m == 2 and d > 29: continue
                    if m in {4,6,9,11} and d > 30: continue
                except Exception:
                    continue
                date8 = f"{y}{m:02d}{d:02d}"
                for variant in apply_one_side_affixes(date8, affixes):
                    yield variant
    # YYMMDD（00-99）
    for y in range(0, 100):
        for m in range(1, 13):
            for d in range(1, 32):
                if m == 2 and d > 29: continue
                if m in {4,6,9,11} and d > 30: continue
                date6 = f"{y:02d}{m:02d}{d:02d}"
                for variant in apply_one_side_affixes(date6, affixes):
                    yield variant

def gen_dates_with_affixes(max_letter_len=2, max_digit_len=2,
                           priority_years=None, priority_mmdd=None,
                           priority_ddmm=None, priority_yyyymm=None,
                           priority_yyyymmdd=None,
                           allow_prefix=True, allow_suffix=True):
    """对高频日期/年份添加单侧字母/数字前后缀（长度受限，默认≤2），控制规模。
    仅对提供的优先级列表进行扩展，不遍历全部日期空间。
    """
    letters = list(_letter_affixes(max_letter_len))
    digits = list(_digit_affixes(max_digit_len))
    # 合并去重，'' 只保留一次
    affixes = list(dict.fromkeys(letters + digits))

    def emit_for_str(s: str):
        yielded_base = False
        # 基本值
        yield s
        yielded_base = True
        # 单侧前/后缀可选
        for a in affixes:
            if not a:
                continue
            if allow_prefix:
                yield a + s
            if allow_suffix:
                yield s + a

    if priority_yyyymmdd:
        for s in priority_yyyymmdd:
            if re.fullmatch(r"\d{8}", s):
                for v in emit_for_str(s):
                    yield v
    if priority_yyyymm:
        for s in priority_yyyymm:
            if re.fullmatch(r"\d{6}", s):
                for v in emit_for_str(s):
                    yield v
    if priority_mmdd:
        for s in priority_mmdd:
            if re.fullmatch(r"\d{4}", s):
                for v in emit_for_str(s):
                    yield v
    if priority_ddmm:
        for s in priority_ddmm:
            if re.fullmatch(r"\d{4}", s):
                for v in emit_for_str(s):
                    yield v
    if priority_years:
        for y in priority_years:
            if re.fullmatch(r"\d{4}", y):
                for v in emit_for_str(y):
                    yield v

def gen_english_wordfreq(max_words=5000):
    # 可选使用 wordfreq 提供更丰富英文词；若缺失则跳过
    try:
        from wordfreq import top_n_list
    except Exception:
        return
    common = top_n_list('en', max_words)
    for w in common:
        w = w.lower()
        if not w.isalpha() or len(w) < 3: continue
        for cv in caps_variants(w):
            yield cv

def load_pinyin_surnames():
    path = os.path.join(THIS_DIR, 'data', 'pinyin_surnames.txt')
    if not os.path.exists(path):
        path = os.path.join(ROOT, 'code', 'dicts', 'pinyin_surnames.txt')
    items = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                s = line.strip().lower()
                if s and not s.startswith('#'):
                    items.append(s)
    except Exception:
        # 回退少量常见姓氏
        items = [
            'li','wang','zhang','liu','chen','yang','zhao','huang','zhou','wu',
            'xu','sun','ma','zhu','hu','guo','he','gao','lin','luo'
        ]
    return items

COMMON_GIVEN_SYLLABLES = [
    'wei','hua','jun','lei','ming','li','lin','hao','yu','yang','jing','jie','bin','bo','chen','chao','fei','hong','jian','kai',
    'lei','liang','ning','peng','qing','qi','ran','tao','tian','wen','wu','xin','xiao','xue','yan','yi','yao','yong','yue','zhen','zhi','zhe','feng','rui','qiang','kun','hao','ze','yuan'
]

def _digit_affixes(max_len=3):
    yield ''
    for l in range(1, max_len+1):
        for tup in itertools.product('0123456789', repeat=l):
            yield ''.join(tup)

def gen_pinyin_surnames(surnames, max_given=2, max_num_affix=3):
    # 仅输出姓氏+名用音节的本体；不再附加数字前/后缀（统一由外部包装器处理）
    gives = ['']
    if max_given >= 1:
        gives += COMMON_GIVEN_SYLLABLES
    if max_given >= 2:
        gives += [a+b for a in COMMON_GIVEN_SYLLABLES for b in COMMON_GIVEN_SYLLABLES]
    for sn in surnames:
        base_opts = [f"{sn}{g}" for g in gives]
        for b in base_opts:
            yield b

def wrap_with_affixes(base_iter, max_letter_len=2, max_digit_len=2, allow_prefix=True, allow_suffix=True):
    """统一前/后缀包装：对 base_iter 逐个元素应用单侧字母/数字前后缀（不叠加两侧）。
    始终先输出 base 本体，再输出前缀或后缀变体。
    """
    letters = list(_letter_affixes(max_letter_len))
    digits = list(_digit_affixes(max_digit_len))
    affixes = list(dict.fromkeys(letters + digits))
    for base in base_iter:
        yield base
        for a in affixes:
            if not a:
                continue
            if allow_prefix:
                yield a + base
            if allow_suffix:
                yield base + a

def gen_simple_alpha_num_combos():
    # 简单字母/数字组合 + 重复
    # 1..4位小写字母
    for l in range(1, 5):
        for tup in itertools.product(string.ascii_lowercase, repeat=l):
            yield ''.join(tup)
    # 1..4位数字
    for l in range(1, 5):
        for tup in itertools.product('0123456789', repeat=l):
            yield ''.join(tup)
    # 简单重复模式
    bases = ['ab','abc','123','abc123','password']
    for b in bases:
        for k in range(2, 5):
            yield b * k

def interleave_generators(gens, budget, dedup=True):
    queues = [iter(g) for g in gens]
    q = deque(queues)
    seen = set()
    emitted = 0
    while q and emitted < budget:
        it = q.popleft()
        try:
            val = next(it)
            if not dedup or val not in seen:
                yield val
                if dedup: seen.add(val)
                emitted += 1
            q.append(it)
        except StopIteration:
            pass

def evaluate(guesses_iter, target_passwords, budget):
    cracked = 0
    tried = 0
    cracked_set = set()
    targets = set(target_passwords)
    for g in guesses_iter:
        tried += 1
        if g in targets and g not in cracked_set:
            cracked += 1
            cracked_set.add(g)
        if tried % 10000 == 0:
            rate = cracked / max(1, len(targets))
            print(f"[+]{tried} guesses, cracked={cracked}, hit_rate={rate:.4f}")
        if tried >= budget:
            break
    return tried, cracked, cracked_set

def evaluate_with_metrics(guesses_iter, target_passwords, budget, progress_interval=10000, progress_callback=None):
    """扩展评估：返回详细指标用于导出与绘图。
    metrics:
      tried, cracked, hit_rate
      cracked_passwords (list)
      progress_points: list[{guesses, cracked, hit_rate}]
      length_stats: {avg_all, avg_cracked, len_hist_all, len_hist_cracked}
      percentiles: {p25, p50, p75, p90} (猜中顺序的分位数，只针对已破解)
      time_elapsed_sec
    """
    start = time.time()
    targets_unique = list(dict.fromkeys(target_passwords))
    targets_set = set(targets_unique)
    total_targets = len(targets_set)
    cracked_set = set()
    progress = []
    tried = 0
    cracked = 0
    # 为计算分位数记录“首次命中所在的猜测序号”
    first_hit_indices = []
    last_progress = 0
    for g in guesses_iter:
        tried += 1
        if g in targets_set and g not in cracked_set:
            cracked_set.add(g)
            cracked += 1
            first_hit_indices.append(tried)
        if tried - last_progress >= max(1, progress_interval) or tried == budget:
            last_progress = tried
            elapsed = time.time() - start
            speed = tried / elapsed if elapsed > 0 else 0.0
            remaining = max(0, budget - tried)
            eta = (remaining / speed) if speed > 0 else None
            point = {
                "guesses": tried,
                "cracked": cracked,
                "hit_rate": cracked / max(1, total_targets),
                "elapsed_sec": elapsed,
                "guesses_per_sec": speed,
                "eta_sec": eta
            }
            progress.append(point)
            if progress_callback:
                try:
                    progress_callback(point)
                except Exception:
                    pass
        if tried >= budget:
            break
    end = time.time()
    # 长度统计
    all_lengths = [len(pw) for pw in targets_set]
    cracked_lengths = [len(pw) for pw in cracked_set]
    def length_hist(arr):
        h = Counter(arr)
        return dict(sorted(h.items()))
    # 分位数
    def percentile(data, p):
        if not data:
            return None
        data_sorted = sorted(data)
        k = (len(data_sorted)-1) * p
        f = int(k)
        c = min(f+1, len(data_sorted)-1)
        if f == c:
            return data_sorted[f]
        return data_sorted[f] + (data_sorted[c]-data_sorted[f]) * (k - f)
    percentiles = {
        "p25": percentile(first_hit_indices, 0.25),
        "p50": percentile(first_hit_indices, 0.5),
        "p75": percentile(first_hit_indices, 0.75),
        "p90": percentile(first_hit_indices, 0.90),
    }
    metrics = {
        "tried": tried,
        "cracked": cracked,
        "hit_rate": cracked / max(1, total_targets),
        "total_targets": total_targets,
        "cracked_passwords": sorted(cracked_set),
        "progress_points": progress,
        "length_stats": {
            "avg_all": sum(all_lengths)/max(1,len(all_lengths)),
            "avg_cracked": sum(cracked_lengths)/max(1,len(cracked_lengths)),
            "len_hist_all": length_hist(all_lengths),
            "len_hist_cracked": length_hist(cracked_lengths),
        },
        "percentiles": percentiles,
        "time_elapsed_sec": end - start,
    }
    return metrics

def parallel_interleave_generators(gens, budget, dedup=True, threads=4, prefetch_cap=100000):
    """并行版本（分批预取循环）：
    - 每轮为每个生成器预取至多 prefetch_cap 条（默认10万，建议按内存调小），合并后交错输出；
    - 当本轮批次耗尽且仍未达到 budget，则继续预取下一轮；
    - 某生成器在一轮返回空批次则认为已耗尽，从后续轮次移除；
    - 避免一次性预取导致总量被硬性限制或内存暴涨。
    说明：prefetch_cap 在此语义为“每轮每生成器的最大批量”。
    """
    if threads <= 1:
        for x in interleave_generators(gens, budget, dedup=dedup):
            yield x
        return

    # 将 gens 统一为迭代器，便于跨轮继续拉取
    active = [iter(g) for g in gens]
    seen = set()
    emitted = 0

    def collect_batch(gen_it, limit):
        out = []
        try:
            for i in range(limit):
                out.append(next(gen_it))
        except StopIteration:
            pass
        return out

    while active and emitted < budget:
        # 并行为每个仍活跃的生成器预取一批
        results = []
        with ThreadPoolExecutor(max_workers=threads) as ex:
            futs = [ex.submit(collect_batch, it, int(prefetch_cap)) for it in active]
            for f in futs:
                try:
                    results.append(f.result())
                except Exception:
                    results.append([])
        # 根据本轮是否取到数据，过滤已耗尽的生成器
        new_active = []
        queues = []
        for it, batch in zip(active, results):
            if batch:
                new_active.append(it)
                queues.append(deque(batch))
        active = new_active
        if not queues:
            break  # 所有生成器都无新数据，结束
        # 交错输出当前批次，直至批次耗尽或达到预算
        while queues and emitted < budget:
            q = queues.pop(0)
            if not q:
                continue
            val = q.popleft()
            if not dedup or val not in seen:
                yield val
                if dedup:
                    seen.add(val)
                emitted += 1
            if q:
                queues.append(q)


def evaluate_targets(guesses_iter, targets, budget, delay_ms=0):
    """针对给定的特定目标集合进行模拟：
    - 记录每个目标首次被命中的猜测序号（未命中则为 None）
    - 记录总体耗时、总体尝试次数、破解比例
    - 可选延迟模拟（每次猜测 sleep 指定毫秒）
    返回 metrics 字典。
    """
    start_time = time.time()
    targets_set = list(dict.fromkeys(targets))  # 去重并保持顺序
    target_lookup = set(targets_set)
    per_target = {pw: None for pw in targets_set}
    cracked_count = 0
    tried = 0
    delay = max(0, delay_ms) / 1000.0
    for guess in guesses_iter:
        tried += 1
        if guess in target_lookup and per_target[guess] is None:
            per_target[guess] = tried
            cracked_count += 1
            # 若全部命中可提前结束
            if cracked_count == len(targets_set):
                break
        if tried >= budget:
            break
        if delay:
            time.sleep(delay)
    end_time = time.time()
    cracked_pw = [pw for pw, idx in per_target.items() if idx is not None]
    avg_guess = (
        sum(idx for idx in per_target.values() if idx is not None) / max(1, len(cracked_pw))
        if cracked_pw else 0
    )
    metrics = {
        "total_targets": len(targets_set),
        "cracked_count": cracked_count,
        "hit_rate": cracked_count / max(1, len(targets_set)),
        "guesses_tried": tried,
        "time_elapsed_sec": end_time - start_time,
        "average_guesses_to_crack": avg_guess,
        "per_target": per_target,
        "cracked_passwords": cracked_pw
    }
    return metrics

def main():
    ap = argparse.ArgumentParser(description="离线口令猜解模拟器（研究/教学用途）")
    ap.add_argument("--dataset", choices=["csdn","yahoo","auto"], default="auto")
    ap.add_argument("--budget", type=int, default=100000)
    ap.add_argument("--threads", type=int, default=1, help="并行生成线程数(>1启用多线程采样阶段)")
    ap.add_argument("--no-dedup", action="store_true", help="关闭跨生成器去重以降低内存开销（可能产生重复项）")
    ap.add_argument("--prefetch-cap", type=int, default=100000, help="并行模式每个生成器的预取上限，防止内存暴涨(默认10万)")
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--evaluate", action="store_true", help="对照数据集口令集合评估命中率(仅将数据集作为目标集合，不再用于训练统计)")
    # 模拟/演示单独目标集合参数
    ap.add_argument("--simulate-targets", action="store_true", help="针对指定或随机抽取的目标集合模拟猜解过程")
    ap.add_argument("--target", type=str, default="", help="指定目标口令（可用逗号分隔多个）")
    ap.add_argument("--target-file", type=str, default="", help="从文件加载目标口令（一行一个）")
    ap.add_argument("--random-targets", type=int, default=0, help="从数据集中随机抽取N个不同目标")
    ap.add_argument("--demo", action="store_true", help="在模拟开始前打印目标集合")
    ap.add_argument("--delay-ms", type=int, default=0, help="每次猜测后延迟的毫秒数，用于模拟开销")
    ap.add_argument("--metrics-out", type=str, default="", help="模拟模式下输出指标 JSON 文件路径")
    # 评估扩展输出/绘图
    ap.add_argument("--eval-metrics-out", type=str, default="", help="评估模式输出详细 JSON")
    ap.add_argument("--cracked-out", type=str, default="", help="评估模式输出已命中口令列表")
    ap.add_argument("--plot-hit-rate", action="store_true", help="评估模式生成命中率-猜测数折线图(需要matplotlib)")
    ap.add_argument("--plot-out", type=str, default="", help="图像输出路径(默认 output/hit_rate_curve_<dataset>_<budget>.png)")
    ap.add_argument("--progress-interval", type=int, default=10000, help="评估进度记录间隔(命中率曲线采样)")
    ap.add_argument("--no-progress", action="store_true", help="评估时不打印进度（默认打印）")
    args = ap.parse_args()

    # 仅在评估或模拟获取数据作为目标集合；不再做训练统计
    recs = []
    if args.evaluate or args.simulate_targets:
        recs = load_dataset(args.dataset)
    pinyin_dict = load_pinyin_words()
    pinyin_surnames = load_pinyin_surnames()

    # 候选生成器（按经验优先度排列）
    gens = []
    # 全部静态：不使用任何数据集提取的局部/用户名/片段
    base_english = gen_english([], COMMON_SUFFIX, high_priority=HF_ENGLISH)
    base_highfreq = gen_builtin_high_freq(COMMON_SUFFIX)
    base_dates = gen_dates(priority_years=HF_YEARS, priority_mmdd=HF_MMDD, priority_ddmm=HF_DDMM, priority_yyyymm=HF_YYYYMM, priority_yyyymmdd=HF_YYYYMMDD, priority_yyyyyyyy=HF_YYYYYYYY)
    base_keyboard = gen_keyboard_and_repeats(priority=HF_KEYBOARD)
    base_wordfreq = gen_english_wordfreq(5000)
    base_pinyin = gen_pinyin_surnames(pinyin_surnames, max_given=2, max_num_affix=3)
    # 统一前/后缀包装（CLI默认应用于除日期外的几类，可根据需要调整）
    def wrap_if(it):
        return wrap_with_affixes(it, max_letter_len=2, max_digit_len=2, allow_prefix=True, allow_suffix=True)
    gens.append(wrap_if(base_english))
    gens.append(wrap_if(base_highfreq))
    gens.append(base_dates)  # 日期基本形态保留为本体（日期+前/后缀在 GUI 中单独可控）
    gens.append(wrap_if(base_keyboard))
    gens.append(wrap_if(base_wordfreq))
    gens.append(wrap_if(base_pinyin))
    gens.append(gen_simple_alpha_num_combos())
    gens.append(gen_numeric_exhaustive_upto7())

    dedup = not args.no_dedup
    if args.threads > 1:
        print(f"[并行] 使用 {args.threads} 线程并行采样候选… 预取上限={args.prefetch_cap}, 去重={'开' if dedup else '关'}")
        guesses = parallel_interleave_generators(gens, budget=args.budget, dedup=dedup, threads=args.threads, prefetch_cap=args.prefetch_cap)
    else:
        guesses = interleave_generators(gens, budget=args.budget, dedup=dedup)

    if args.out or (not args.evaluate and not args.simulate_targets):
        # 使用默认输出目录: 若未提供--out则生成默认文件名
        out_path = args.out.strip()
        if not out_path:
            out_path = os.path.join(GENERATE_DIR, f"guesses_{args.dataset}_{args.budget}.txt")
        elif not os.path.isabs(out_path):
            base_dir = os.path.dirname(out_path)
            if not base_dir:
                out_path = os.path.join(GENERATE_DIR, out_path)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8", errors="ignore") as f:
            for g in guesses:
                f.write(g + "\n")
        print(f"已写出候选到: {out_path}")
        if not args.out:
            print("(未指定 --out, 已使用默认输出目录 code/guess/output/generate/)")
        return
    # 新的模拟目标模式（优先级高于 --evaluate）
    if args.simulate_targets:
        chosen_targets = []
        # 解析 --target
        if args.target.strip():
            chosen_targets.extend([t for t in args.target.split(',') if t])
        # 解析 --target-file
        if args.target_file:
            try:
                with open(args.target_file, 'r', encoding='utf-8', errors='ignore') as tf:
                    for line in tf:
                        s = line.strip()
                        if s:
                            chosen_targets.append(s)
            except Exception as e:
                print(f"[!] 读取 target-file 失败: {e}")
        # 随机抽取
        if args.random_targets > 0:
            all_pw = list({r['password'] for r in recs if r.get('password')})
            if args.random_targets >= len(all_pw):
                sampled = all_pw
            else:
                sampled = random.sample(all_pw, args.random_targets)
            chosen_targets.extend(sampled)
        # 若仍为空则默认随机抽取 1 个
        if not chosen_targets:
            all_pw = [r['password'] for r in recs if r.get('password')]
            if all_pw:
                chosen_targets.append(random.choice(all_pw))
        # 去重
        final_targets = list(dict.fromkeys(chosen_targets))
        if args.demo:
            print("[演示] 目标集合 (共{}个):".format(len(final_targets)))
            for pw in final_targets:
                print("  -", pw)
        metrics = evaluate_targets(guesses, final_targets, args.budget, delay_ms=args.delay_ms)
        print("\n模拟结果:")
        print(f"  总目标: {metrics['total_targets']}")
        print(f"  已破解: {metrics['cracked_count']} (命中率={metrics['hit_rate']:.4f})")
        print(f"  总猜测次数: {metrics['guesses_tried']}")
        print(f"  耗时(秒): {metrics['time_elapsed_sec']:.3f}")
        print(f"  平均破解所需猜测(已破解目标): {metrics['average_guesses_to_crack']:.1f}")
        print("  每个目标首次命中猜测序号 (None=未命中):")
        for pw, idx in metrics['per_target'].items():
            print(f"    {pw}: {idx}")
        if args.metrics_out or args.simulate_targets:
            try:
                m_path = args.metrics_out.strip()
                if not m_path:
                    m_path = os.path.join(SIMULATE_DIR, f"metrics_simulate_{args.dataset}_{args.budget}.json")
                elif not os.path.isabs(m_path):
                    base_dir = os.path.dirname(m_path)
                    if not base_dir:
                        m_path = os.path.join(SIMULATE_DIR, m_path)
                os.makedirs(os.path.dirname(m_path) or '.', exist_ok=True)
                with open(m_path, 'w', encoding='utf-8') as mf:
                    json.dump(metrics, mf, ensure_ascii=False, indent=2)
                print(f"[+] 指标已写出到: {m_path}")
                if not args.metrics_out:
                    print("(未指定 --metrics-out, 已使用默认输出目录 code/guess/output/simulate/)")
            except Exception as e:
                print(f"[!] 写出 metrics 失败: {e}")
        return

    if args.evaluate:
        targets = [r["password"] for r in recs]
        e = gen_english([], COMMON_SUFFIX, high_priority=HF_ENGLISH)
        hf = gen_builtin_high_freq(COMMON_SUFFIX)
        dt = gen_dates(priority_years=HF_YEARS, priority_mmdd=HF_MMDD, priority_ddmm=HF_DDMM, priority_yyyymm=HF_YYYYMM, priority_yyyymmdd=HF_YYYYMMDD, priority_yyyyyyyy=HF_YYYYYYYY)
        kb = gen_keyboard_and_repeats(priority=HF_KEYBOARD)
        wf = gen_english_wordfreq(5000)
        py = gen_pinyin_surnames(pinyin_surnames, max_given=2, max_num_affix=3)
        def w(it): return wrap_with_affixes(it, max_letter_len=2, max_digit_len=2, allow_prefix=True, allow_suffix=True)
        gens_eval = [w(e), w(hf), dt, w(kb), w(wf), w(py), gen_simple_alpha_num_combos(), gen_numeric_exhaustive_upto7()]
        if args.threads > 1:
            guesses_eval = parallel_interleave_generators(gens_eval, budget=args.budget, dedup=dedup, threads=args.threads, prefetch_cap=args.prefetch_cap)
        else:
            guesses_eval = interleave_generators(gens_eval, budget=args.budget, dedup=dedup)
        def _print_progress(pt):
            if args.no_progress:
                return
            eta = pt.get('eta_sec')
            eta_s = f"{eta:.1f}s" if eta is not None else "--"
            spd = pt.get('guesses_per_sec') or 0.0
            print(f"[进度] {pt['guesses']}/{args.budget} cracked={pt['cracked']} hit_rate={pt['hit_rate']:.4f} speed={spd:.0f}/s eta={eta_s}")
        metrics = evaluate_with_metrics(
            guesses_eval,
            targets,
            args.budget,
            progress_interval=max(1, args.progress_interval),
            progress_callback=_print_progress
        )
        print(f"\n评估完成：tried={metrics['tried']}, cracked={metrics['cracked']}, hit_rate={metrics['hit_rate']:.4f}, elapsed={metrics['time_elapsed_sec']:.2f}s")
        print("[静态模式] 仅使用内置/词典生成器，未利用数据集统计。")
        # 输出 cracked 列表
        if args.cracked_out:
            path_c = args.cracked_out
            if not os.path.isabs(path_c):
                base_dir = os.path.dirname(path_c)
                if not base_dir:
                    path_c = os.path.join(EVALUATE_DIR, path_c)
            os.makedirs(os.path.dirname(path_c) or '.', exist_ok=True)
            with open(path_c, 'w', encoding='utf-8') as cf:
                cf.write('\n'.join(metrics['cracked_passwords']))
            print(f"[+] 已写出命中口令列表: {path_c} (数量={len(metrics['cracked_passwords'])})")
        elif not args.cracked_out:
            # 默认输出
            default_cracked = os.path.join(EVALUATE_DIR, f"cracked_{args.dataset}_{args.budget}.txt")
            with open(default_cracked, 'w', encoding='utf-8') as cf:
                cf.write('\n'.join(metrics['cracked_passwords']))
            print(f"[+] 已写出命中口令列表(默认): {default_cracked} (数量={len(metrics['cracked_passwords'])})")
        # 输出详细 JSON
        if args.eval_metrics_out:
            path_m = args.eval_metrics_out
            if not os.path.isabs(path_m):
                base_dir = os.path.dirname(path_m)
                if not base_dir:
                    path_m = os.path.join(EVALUATE_DIR, path_m)
            os.makedirs(os.path.dirname(path_m) or '.', exist_ok=True)
            with open(path_m, 'w', encoding='utf-8') as mf:
                json.dump(metrics, mf, ensure_ascii=False, indent=2)
            print(f"[+] 已写出评估指标 JSON: {path_m}")
        elif not args.eval_metrics_out:
            default_metrics_path = os.path.join(EVALUATE_DIR, f"eval_metrics_{args.dataset}_{args.budget}.json")
            with open(default_metrics_path, 'w', encoding='utf-8') as mf:
                json.dump(metrics, mf, ensure_ascii=False, indent=2)
            print(f"[+] 已写出评估指标 JSON(默认): {default_metrics_path}")
        # 绘制曲线
        if args.plot_hit_rate:
            try:
                import matplotlib.pyplot as plt
                xs = [pt['guesses'] for pt in metrics['progress_points']]
                ys = [pt['hit_rate'] for pt in metrics['progress_points']]
                plt.figure(figsize=(6,4))
                plt.plot(xs, ys, marker='o', linewidth=1)
                plt.xlabel('Guesses Tried')
                plt.ylabel('Hit Rate')
                plt.title(f'Hit Rate Curve ({args.dataset})')
                plt.grid(alpha=0.3)
                plot_path = args.plot_out.strip()
                if not plot_path:
                    plot_path = os.path.join(EVALUATE_DIR, f"hit_rate_curve_{args.dataset}_{args.budget}.png")
                elif not os.path.isabs(plot_path):
                    base_dir = os.path.dirname(plot_path)
                    if not base_dir:
                        plot_path = os.path.join(EVALUATE_DIR, plot_path)
                os.makedirs(os.path.dirname(plot_path) or '.', exist_ok=True)
                plt.tight_layout()
                plt.savefig(plot_path, dpi=120)
                plt.close()
                print(f"[+] 命中率曲线已保存: {plot_path}\n(点数={len(xs)}, 终点命中率={metrics['hit_rate']:.4f})")
            except Exception as e:
                print(f"[!] 绘图失败: {e} (可安装 matplotlib 或检查环境)")
        # 补充打印部分统计
        ls = metrics['length_stats']
        print(f"长度统计: avg_all={ls['avg_all']:.2f}, avg_cracked={ls['avg_cracked']:.2f}")
        print(f"分位数(首次命中猜测序号): p25={metrics['percentiles']['p25']}, p50={metrics['percentiles']['p50']}, p75={metrics['percentiles']['p75']}, p90={metrics['percentiles']['p90']}")
    else:
        # 默认打印前若干条做可视化
        for i, g in enumerate(guesses, 1):
            print(g)
            if i >= min(100, args.budget): break

if __name__ == "__main__":
    main()
