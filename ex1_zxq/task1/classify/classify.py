"""
口令分析与分类（可扩展架构）

输入数据：
- CSDN:  code/processed_dataset/csdn_mail_password_username.txt  每行 <mail>:<password>:<username>
- Yahoo: code/processed_dataset/yahoo_mail_password.txt          每行 <mail>:<password>

输出：
- 将分类结果分别写入 code/classify/classify_result/{csdn|yahoo}/ 下的若干文件，并生成汇总统计。

命令行：
- 列出分析器：python code/classify/classify.py --list
- 运行分析：  python code/classify/classify.py --dataset csdn --limit 100000
"""

from __future__ import annotations

import argparse
import json
import os
import re
import importlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

# --------------------------- 基础与注册表 ---------------------------


@dataclass
class Context:
    mail: str
    password: str
    username: Optional[str] = None

    @property
    def mail_local(self) -> str:
        return self.mail.split("@", 1)[0] if "@" in self.mail else self.mail

    @property
    def mail_domain(self) -> str:
        return self.mail.split("@", 1)[1] if "@" in self.mail else ""


class BaseAnalyzer:
    name: str = "base"
    description: str = ""
    priority: int = 100  # 数字越小优先级越高

    def detect(self, ctx: Context) -> bool:
        raise NotImplementedError


class AnalyzerRegistry:
    def __init__(self):
        self._analyzers: List[BaseAnalyzer] = []

    def register(self, analyzer_cls):
        inst = analyzer_cls()
        # 应用全局权重覆盖（若存在）
        try:
            inst.priority = PRIORITY.get(inst.name, getattr(inst, "priority", 100))
        except NameError:
            pass
        self._analyzers.append(inst)
        self._analyzers.sort(key=lambda a: a.priority)
        return analyzer_cls

    @property
    def analyzers(self) -> List[BaseAnalyzer]:
        return list(self._analyzers)


REGISTRY = AnalyzerRegistry()


def register_analyzer(cls):
    return REGISTRY.register(cls)


def load_category_modules(names: Optional[List[str]] = None) -> None:
    """从 code/classify/categories 自动加载模块并用模块的 detect() 创建动态 Analyzer 并注册。

    模块接口要求：NAME, DESCRIPTION, detect(ctx)
    """
    pkg = "categories"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cat_dir = os.path.join(base_dir, "categories")
    if not os.path.isdir(cat_dir):
        print(f"[WARN] categories 目录不存在: {cat_dir}")
        return

    if names is None:
        names = [fn[:-3] for fn in os.listdir(cat_dir) if fn.endswith(".py") and fn != "__init__.py"]

    # 清空已注册的分析器（将由 categories 重新注册）
    REGISTRY._analyzers.clear()

    for modname in names:
        full = f"{pkg}.{modname}"
        try:
            m = importlib.import_module(full)
        except Exception as e:
            print(f"[WARN] 加载分类模块 {full} 失败: {e}")
            continue

        name = getattr(m, "NAME", getattr(m, "name", modname))
        desc = getattr(m, "DESCRIPTION", getattr(m, "description", ""))
        prio = PRIORITY.get(name, 100)
        detect_fn = getattr(m, "detect", None)
        if detect_fn is None:
            print(f"[WARN] 模块 {full} 未提供 detect(ctx) 函数，跳过")
            continue

        def make_detect(f):
            def _detect(self, ctx):
                return f(ctx)
            return _detect

        attrs = {
            "name": name,
            "description": desc,
            "priority": prio,
            "detect": make_detect(detect_fn),
        }
        AnalyzerCls = type(f"DynAnalyzer_{name}", (BaseAnalyzer,), attrs)
        REGISTRY.register(AnalyzerCls)


# --------------------------- 实用工具 ---------------------------


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_wordlist(path: Optional[str]) -> Optional[set]:
    if not path:
        return None
    if not os.path.isfile(path):
        print(f"[WARN] 词典文件未找到：{path}")
        return None
    words = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            w = line.strip().lower()
            if w:
                words.add(w)
    return words


def _default_dict_path(name: str) -> str:
    # 本脚本位于 code/classify；词典在 code/dicts
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "..", "dicts", name)


def load_default_pinyin_words() -> set:
    """尝试从 code/dicts/pinyin_syllables.txt 加载默认拼音词表，否则回退为内置简表。"""
    path = _default_dict_path("pinyin_syllables.txt")
    words = load_wordlist(path)
    if words:
        return words
    # 兜底：保留一组常见拼音片段/姓氏
    return {
        "zhang","wang","li","zhao","chen","yang","wu","liu","zhou","sun",
        "guo","lin","he","ma","gao","xue","feng","ying","hua","long",
        "tian","ming","jun","hong","lv","nv",
    }


DEFAULT_PINYIN_WORDS = load_default_pinyin_words()


def normalize_leet(s: str) -> str:
    table = str.maketrans({
        "0": "o","1": "l","3": "e","4": "a","5": "s","7": "t","8": "b","@": "a","$": "s","!": "i",
    })
    return s.lower().translate(table)


def has_repeating_unit(s: str) -> bool:
    return bool(re.fullmatch(r"(.+?)\1+", s))


def contains_sequence(s: str, seqs: Iterable[str], min_len: int = 4) -> bool:
    s_low = s.lower()
    for row in seqs:
        row_low = row.lower()
        for i in range(0, len(row_low) - min_len + 1):
            sub = row_low[i : i + min_len]
            if sub in s_low:
                return True
        row_rev = row_low[::-1]
        for i in range(0, len(row_rev) - min_len + 1):
            sub = row_rev[i : i + min_len]
            if sub in s_low:
                return True
    return False


# --------------------------- 分类器（内置兜底版） ---------------------------
# 说明：优先从 code/classify/categories 加载增强版实现，若未提供则保留这些简版。


@register_analyzer
class SameAsUserOrMailAnalyzer(BaseAnalyzer):
    name = "same_as_user_or_mail"
    description = "与用户名/邮箱完全相同"

    def detect(self, ctx: Context) -> bool:
        pw = ctx.password.strip().lower()
        cands = [ctx.mail.lower(), ctx.mail_local.lower()]
        if ctx.username:
            cands.append(ctx.username.strip().lower())
        return pw in cands


@register_analyzer
class PartialLikeUserOrMailAnalyzer(BaseAnalyzer):
    name = "partial_like_user_or_mail"
    description = "与用户名/邮箱部分相同（子串长度>=4）"

    def detect(self, ctx: Context) -> bool:
        pw = ctx.password.lower()
        tokens: List[str] = []
        def split_tokens(s: str) -> List[str]:
            return [t for t in re.split(r"[^a-zA-Z0-9]+", s.lower()) if t]
        tokens.extend(split_tokens(ctx.mail_local))
        if ctx.username:
            tokens.extend(split_tokens(ctx.username))
        tokens = [t for t in tokens if len(t) >= 4]
        return any(t in pw for t in tokens)


@register_analyzer
class NumericOnlyAnalyzer(BaseAnalyzer):
    name = "numeric_only"
    description = "纯数字口令"

    def detect(self, ctx: Context) -> bool:
        pw = ctx.password
        return pw.isdigit() and len(pw) >= 4


@register_analyzer
class RepeatedCharsAnalyzer(BaseAnalyzer):
    name = "repeated_chars"
    description = "重复字符或重复单元口令"

    def detect(self, ctx: Context) -> bool:
        pw = ctx.password.lower()
        if len(pw) >= 3 and len(set(pw)) == 1:
            return True
        if len(pw) >= 6 and has_repeating_unit(pw):
            return True
        return False


@register_analyzer
class KeyboardPatternAnalyzer(BaseAnalyzer):
    name = "keyboard_pattern"
    description = "键盘序列（如 qwerty、asdf、1234 等）"

    KEY_ROWS = [
        "`1234567890-=",
        "qwertyuiop[]\\",
        "asdfghjkl;'",
        "zxcvbnm,./",
    ]

    def detect(self, ctx: Context) -> bool:
        return contains_sequence(ctx.password, self.KEY_ROWS, min_len=4)


@register_analyzer
class DateLikeAnalyzer(BaseAnalyzer):
    name = "date_like"
    description = "日期样式（YYYYMMDD、YYYY-MM-DD、YYMMDD、MMDD 等）"

    DATE_PATTERNS = [
        r"^(19|20)\d{2}[-/.]?((0[1-9])|(1[0-2]))[-/.]?(([0-2][0-9])|(3[01]))$",
        r"^\d{2}[-/.]?(0[1-9]|1[0-1])[-/.]?(0[1-9]|[12]\d|30)$",
        r"^((0?[1-9])|(1[0-2]))[-/.]?((0?[1-9])|([12][0-9])|(3[01]))$",
        r"^((19|20)\d{2})$",
    ]

    def detect(self, ctx: Context) -> bool:
        pw = ctx.password
        for pat in self.DATE_PATTERNS:
            if re.fullmatch(pat, pw):
                return True
        return False


@register_analyzer
class PinyinAnalyzer(BaseAnalyzer):
    name = "pinyin"
    description = "疑似拼音（词典匹配或启发式拼音结构）"

    def __init__(self, pinyin_wordlist: Optional[set] = None):
        self.words = pinyin_wordlist or DEFAULT_PINYIN_WORDS

    def detect(self, ctx: Context) -> bool:
        pw = normalize_leet(ctx.password)
        letters = re.findall(r"[a-zA-Z]+", pw)
        if not letters:
            return False
        for token in letters:
            t = token.lower()
            if len(t) < 3:
                continue
            if t in self.words:
                return True
            for w in self.words:
                if len(w) >= 3 and w in t:
                    return True
        return False


@register_analyzer
class EnglishWordAnalyzer(BaseAnalyzer):
    name = "english_word"
    description = "英文单词（支持简单 Leet 归一化）"

    def __init__(self, english_wordlist: Optional[set] = None):
        self.words = english_wordlist or {
            "password","qwerty","admin","welcome","iloveyou","love","secret","dragon","monkey","letmein",
            "football","baseball","abc","abc123","hello","flower",
        }

    def detect(self, ctx: Context) -> bool:
        pw = normalize_leet(ctx.password)
        letters = re.findall(r"[a-zA-Z]+", pw)
        if not letters:
            return False
        for token in letters:
            t = token.lower()
            if t in self.words:
                return True
            for w in self.words:
                if len(w) >= 3 and w in t:
                    return True
        return False


@register_analyzer
class OtherAnalyzer(BaseAnalyzer):
    name = "other"
    description = "其他"

    def detect(self, ctx: Context) -> bool:
        return True


# --------------------------- 管道与执行 ---------------------------

# 全局可编辑的优先级定义（权重）：名称 -> 数值（越小越先匹配）
PRIORITY: Dict[str, int] = {
    "same_as_user_or_mail": 1,
    "partial_like_user_or_mail": 2,
    "repeated_chars": 3,
    "dictionary_order": 4,
    "keyboard_pattern": 5,
    "date_like": 6,
    "english_word": 7,
    "pinyin": 8,
    "numeric_only": 9,
    "other": 999,
}

# 输出顺序；自动追加未列出的分析器
CATEGORY_ORDER = [
    "same_as_user_or_mail",
    "partial_like_user_or_mail",
    "numeric_only",
    "repeated_chars",
    "keyboard_pattern",
    "dictionary_order",
    "date_like",
    "pinyin",
    "english_word",
    "other",
]


def apply_priorities(priority_map: Dict[str, int]) -> None:
    PRIORITY.update(priority_map)
    for a in REGISTRY.analyzers:
        a.priority = PRIORITY.get(a.name, getattr(a, "priority", 100))
    REGISTRY._analyzers.sort(key=lambda a: a.priority)


def pick_category(ctx: Context, exclusive: bool, analyzers: List[BaseAnalyzer]) -> List[str]:
    """根据 exclusive 选择主分类；多标签时忽略 other 并返回所有命中的类别。"""
    matched: List[str] = []
    for analyzer in analyzers:
        if not exclusive and analyzer.name == "other":
            continue
        if analyzer.detect(ctx):
            matched.append(analyzer.name)
            if exclusive:
                break
    if not matched:
        matched = ["other"]
    return matched


def iter_dataset_lines(dataset: str, input_path: Optional[str]) -> Iterable[Tuple[Context, str]]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 处理后的数据仍位于 code/processed_dataset
    processed_dir = os.path.join(base_dir, "..", "processed_dataset")
    if dataset == "csdn":
        default_path = os.path.join(processed_dir, "csdn_mail_password_username.txt")
    elif dataset == "yahoo":
        default_path = os.path.join(processed_dir, "yahoo_mail_password.txt")
    else:
        csdn_path = os.path.join(processed_dir, "csdn_mail_password_username.txt")
        yahoo_path = os.path.join(processed_dir, "yahoo_mail_password.txt")
        default_path = csdn_path if os.path.isfile(csdn_path) else yahoo_path

    path = input_path or default_path
    if not os.path.isfile(path):
        raise FileNotFoundError(f"未找到输入文件：{path}")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            raw = line.rstrip("\n")
            if not raw:
                continue
            parts = raw.split(":")
            if len(parts) < 2:
                continue
            if len(parts) == 2:
                mail, password = parts
                username = None
            else:
                mail, password, username = parts[0], parts[1], ":".join(parts[2:])
            yield Context(mail=mail, password=password, username=username), raw


def save_and_count(
    dataset: str,
    output_root: Optional[str],
    exclusive: bool,
    english_wordlist: Optional[set],
    pinyin_wordlist: Optional[set],
    input_path: Optional[str] = None,
    limit: Optional[int] = None,
    workers: int = 1,
    batch_size: int = 5000,
) -> Dict[str, int]:
    # 将词典注入到对应分析器（如果提供），按 name 字段匹配
    for analyzer in REGISTRY.analyzers:
        if analyzer.name == "english_word" and english_wordlist is not None:
            setattr(analyzer, "words", english_wordlist)
        if analyzer.name == "pinyin" and pinyin_wordlist is not None:
            setattr(analyzer, "words", pinyin_wordlist)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 输出到 code/classify/classify_result
    classify_root = output_root or os.path.join(base_dir, "classify_result")
    out_dir = os.path.join(classify_root, dataset)
    ensure_dir(out_dir)

    # 构建实际启用的分析器列表：Yahoo 数据集禁用 pinyin
    active_analyzers: List[BaseAnalyzer] = [
        a for a in REGISTRY.analyzers if not (dataset == "yahoo" and a.name == "pinyin")
    ]

    # 输出类别名称按预定义顺序 + 其它补充；若禁用则自动移除
    category_names = [
        name for name in CATEGORY_ORDER
        if any(a.name == name for a in active_analyzers)
    ] + [
        a.name for a in active_analyzers if a.name not in CATEGORY_ORDER
    ]

    writers: Dict[str, any] = {}
    for name in category_names:
        writers[name] = open(os.path.join(out_dir, f"{name}.txt"), "w", encoding="utf-8")

    counts: Dict[str, int] = {name: 0 for name in category_names}
    total = 0

    # 复合特征统计：对每条密码记录所有命中的类别（不含 other），组合尺寸>1 视为复合
    combo_counts: Dict[str, int] = {}
    combo_examples: Dict[str, List[str]] = {}
    COMBO_EXAMPLE_LIMIT = 10

    def _is_numeric_seq(pw: str) -> bool:
        if not pw.isdigit() or len(pw) < 4:
            return False
        diffs = [int(pw[i+1]) - int(pw[i]) for i in range(len(pw)-1)]
        return all(d == 1 for d in diffs) or all(d == -1 for d in diffs)

    def classify_one(ctx: Context, raw: str) -> Tuple[List[str], List[str], str]:
        primary = pick_category(ctx, exclusive, active_analyzers)
        all_hits = [a.name for a in active_analyzers if a.name != "other" and a.detect(ctx)]
        # 归一化（数字连续三重重复）
        if (
            'dictionary_order' in all_hits and
            'keyboard_pattern' in all_hits and
            'numeric_only' in all_hits and
            _is_numeric_seq(ctx.password)
        ):
            all_hits = [h for h in all_hits if h != 'keyboard_pattern']
        return primary, all_hits, ctx.password, raw

    # 线程池路径：读取批次 -> 并行分类 -> 聚合
    try:
        batch: List[Tuple[Context, str]] = []
        executor: Optional[ThreadPoolExecutor] = None
        if workers > 1:
            executor = ThreadPoolExecutor(max_workers=workers)
            print(f"[info] 多线程启用，workers={workers}, batch_size={batch_size}")
        for i, (ctx, raw) in enumerate(iter_dataset_lines(dataset, input_path), start=1):
            batch.append((ctx, raw))
            # 达到批次大小或最后一条，处理批次
            if (len(batch) >= batch_size) or (limit and i >= limit):
                if executor:
                    futures = [executor.submit(classify_one, c, r) for c, r in batch]
                    results = [f.result() for f in futures]
                else:
                    results = [classify_one(c, r) for c, r in batch]

                for primary, all_hits, password, raw_line in results:
                    for c in primary:
                        counts[c] += 1
                        writers[c].write(raw_line + "\n")
                    if len(all_hits) > 1:
                        combo_key = "+".join(sorted(all_hits))
                        combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1
                        if len(combo_examples.get(combo_key, [])) < COMBO_EXAMPLE_LIMIT:
                            combo_examples.setdefault(combo_key, []).append(password)
                    total += 1

                batch.clear()
                if i % 200000 == 0:
                    print(f"[progress] processed: {i}")
            if limit and i >= limit:
                break
        # 处理残余批次
        if batch:
            if executor:
                futures = [executor.submit(classify_one, c, r) for c, r in batch]
                results = [f.result() for f in futures]
            else:
                results = [classify_one(c, r) for c, r in batch]
            for primary, all_hits, password, raw_line in results:
                for c in primary:
                    counts[c] += 1
                    writers[c].write(raw_line + "\n")
                if len(all_hits) > 1:
                    combo_key = "+".join(sorted(all_hits))
                    combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1
                    if len(combo_examples.get(combo_key, [])) < COMBO_EXAMPLE_LIMIT:
                        combo_examples.setdefault(combo_key, []).append(password)
                total += 1
    finally:
        for fp in writers.values():
            fp.close()

    # 依据类型权重（优先级）生成打印/汇总顺序（数值小=权重高）
    name_to_prio = {a.name: getattr(a, "priority", 9999) for a in REGISTRY.analyzers}
    def _prio_of(name: str) -> int:
        return int(name_to_prio.get(name, PRIORITY.get(name, 9999)))
    print_order = sorted(counts.keys(), key=_prio_of)

    summary = {
        "dataset": dataset,
        "exclusive_mode": exclusive,
        "total": total,
        "single_counts": counts,
        "single_ratios": {k: (counts[k] / total if total else 0.0) for k in counts},
        "order": print_order,
        "combo_counts": combo_counts,
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fjson:
        json.dump(summary, fjson, ensure_ascii=False, indent=2)

    # 生成分析报告（文本）：单类统计 + 复合特征概览
    report_path = os.path.join(out_dir, "analysis_report.txt")
    with open(report_path, "w", encoding="utf-8") as frep:
        frep.write(f"数据集: {dataset}\n")
        frep.write(f"模式: {'独占' if exclusive else '多标签'}\n")
        frep.write(f"线程数: {workers}\n")
        frep.write(f"总记录: {total}\n\n")
        frep.write("=== 单类统计 ===\n")
        for k in print_order:
            r = summary["single_ratios"][k]
            frep.write(f"{k}: {counts[k]} ({r:.2%})\n")
        frep.write("\n=== 复合特征（组合尺寸>1） ===\n")
        if combo_counts:
            sorted_combos = sorted(combo_counts.items(), key=lambda x: x[1], reverse=True)
            for combo, cnt in sorted_combos[:50]:
                frep.write(f"{combo}: {cnt}\n")
            frep.write("\n-- 示例（每组合最多10条） --\n")
            for combo, examples in combo_examples.items():
                frep.write(f"[{combo}] => {', '.join(examples)}\n")
        else:
            frep.write("(无复合特征密码)\n")

    print("\n分类完成：")
    print(f"  数据集: {dataset}")
    print(f"  模式:   {'独占' if exclusive else '多标签'}")
    print(f"  总数:   {total}")
    for k in print_order:
        r = summary["single_ratios"][k]
        print(f"  - {k:27s} {counts[k]:>10}  ({r:.2%})")
    if summary["combo_counts"]:
        print("  [复合特征组合数]", len(summary["combo_counts"]))

    return counts


# --------------------------- CLI ---------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="口令分析与分类（可扩展）")
    p.add_argument("--dataset", choices=["csdn", "yahoo", "auto"], default="auto", help="选择数据集")
    p.add_argument("--input", help="输入文件路径（可选，默认从 processed_dataset 推断）")
    p.add_argument("--output-dir", help="分类结果根目录（默认 code/classify/classify_result）")
    p.add_argument("--exclusive", action="store_true", help="独占分类（命中第一个即归类，默认）")
    p.add_argument("--multi", action="store_true", help="多标签分类（可同时命中多个类别）")
    p.add_argument("--limit", type=int, help="处理前 N 行用于抽样验证")
    p.add_argument("--english-wordlist", help="英文词典路径（每行一个词，已小写）")
    p.add_argument("--pinyin-wordlist", help="拼音词典路径（每行一个词/音节，已小写）")
    p.add_argument("--priority-config", help="JSON 文件，定义 {分类名: 优先级} 的映射，越小越先匹配")
    p.add_argument("--list", action="store_true", help="列出已注册的分析器")
    p.add_argument("--workers", type=int, default=1, help="并行工作线程数(>1 启用多线程批处理加速)")
    return p


def main():
    args = build_arg_parser().parse_args()

    # 优先加载 categories 目录中的动态分类器（覆盖内置实现）
    load_category_modules()

    apply_priorities({})
    exclusive = True if args.exclusive or not args.multi else False
    dataset = args.dataset

    english_words = load_wordlist(args.english_wordlist)
    pinyin_words = load_wordlist(args.pinyin_wordlist)

    if args.priority_config:
        if not os.path.isfile(args.priority_config):
            print(f"[WARN] 未找到优先级配置：{args.priority_config}")
        else:
            try:
                with open(args.priority_config, "r", encoding="utf-8") as fp:
                    mapping = json.load(fp)
                mapping = {str(k): int(v) for k, v in mapping.items()}
                apply_priorities(mapping)
                print("[info] 已应用优先级配置：", args.priority_config)
            except Exception as e:
                print(f"[WARN] 加载优先级配置失败：{e}")

    save_and_count(
        dataset=dataset,
        output_root=args.output_dir,
        exclusive=exclusive,
        english_wordlist=english_words,
        pinyin_wordlist=pinyin_words,
        input_path=args.input,
        limit=args.limit,
        workers=max(1, args.workers),
    )


if __name__ == "__main__":
    main()
