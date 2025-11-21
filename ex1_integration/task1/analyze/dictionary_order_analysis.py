import os
import re
import json
from collections import Counter
from dataclasses import dataclass

# 输出配置
TOPK = 10

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "analysis_results")
TASK1_DIR = os.path.dirname(CURRENT_DIR)
REPORT_PATH = os.path.join(OUTPUT_DIR, "dictionary_order_report.txt")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "dictionary_order_summary.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 数据文件相对工程根目录（与 classify 脚本保持一致）
FILE_CSDN = os.path.join(TASK1_DIR, "processed_dataset", "csdn_mail_password_username.txt")
FILE_YAHOO = os.path.join(TASK1_DIR, "processed_dataset", "yahoo_mail_password.txt")

# 线性序列最小长度
MIN_RUN = 4

@dataclass
class LinearRun:
    sequence: str  # 命中的连续序列（如 abcdef / 654321）
    asc: bool      # 是否升序
    start_index: int
    length: int


def _same_class(a: str, b: str) -> bool:
    return (a.isdigit() and b.isdigit()) or (a.isalpha() and b.isalpha())


def _extract_linear_runs(token: str, min_len: int = MIN_RUN):
    runs = []
    asc_len = 1
    desc_len = 1
    asc_start = 0
    desc_start = 0
    for i in range(len(token) - 1):
        a, b = token[i], token[i + 1]
        if not _same_class(a, b):
            asc_len = 1
            desc_len = 1
            asc_start = i + 1
            desc_start = i + 1
            continue
        d = ord(b) - ord(a)
        if d == 1:  # 升序继续
            asc_len += 1
            if asc_len == 2:  # 新升序段开始
                asc_start = i
        else:
            asc_len = 1
        if d == -1:  # 降序继续
            desc_len += 1
            if desc_len == 2:
                desc_start = i
        else:
            desc_len = 1
        if asc_len >= min_len:
            seq = token[asc_start: i + 2]
            runs.append(LinearRun(sequence=seq, asc=True, start_index=asc_start, length=len(seq)))
        if desc_len >= min_len:
            seq = token[desc_start: i + 2]
            runs.append(LinearRun(sequence=seq, asc=False, start_index=desc_start, length=len(seq)))
    return runs


def detect_dictionary_order(password: str) -> bool:
    s = password.lower()
    for token in re.findall(r"[a-z0-9]+", s):
        if any(r.length >= MIN_RUN for r in _extract_linear_runs(token)):
            return True
    return False


def analyze_file(path: str, label: str, limit: int | None = None):
    if not os.path.isfile(path):
        print(f"[WARN] 文件不存在: {path}")
        return None
    
    print(f"正在分析: {path}")

    total = 0
    dict_order_pwds = []
    run_counter = Counter()
    length_counter = Counter()
    start_char_counter = Counter()
    asc_counter = 0
    desc_counter = 0
    structure_counter = Counter()  # 简单结构: 将线性段替换为 'R'

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            parts = raw.split(':')
            if len(parts) < 2:
                continue
            # password 字段位置：Yahoo 两段, CSDN 第二段
            password = parts[1] if len(parts) >= 2 else raw
            password = password.strip()
            total += 1

            lower = password.lower()
            hits = []
            for token in re.findall(r"[a-z0-9]+", lower):
                runs = _extract_linear_runs(token)
                for r in runs:
                    run_counter[r.sequence] += 1
                    length_counter[r.length] += 1
                    start_char_counter[r.sequence[0]] += 1
                    if r.asc:
                        asc_counter += 1
                    else:
                        desc_counter += 1
                    hits.append(r)
            if hits:
                dict_order_pwds.append(password)
                # 构造结构：按最长匹配替换
                struct = _password_structure(password, hits)
                structure_counter[struct] += 1

            if limit and total >= limit:
                break

    ratio = len(dict_order_pwds) / total * 100 if total else 0
    return {
        'label': label,
        'file': path,
        'total_passwords': total,
        'dict_order_passwords': len(dict_order_pwds),
        'ratio_percent': ratio,
        'run_counter': run_counter,
        'length_counter': length_counter,
        'start_char_counter': start_char_counter,
        'asc_count': asc_counter,
        'desc_count': desc_counter,
        'structure_counter': structure_counter,
        'examples': dict_order_pwds[:TOPK],
    }


def _password_structure(password: str, runs: list[LinearRun]) -> str:
    # 根据 runs 按长度排序，避免嵌套覆盖冲突
    runs_sorted = sorted(runs, key=lambda r: (-r.length, r.start_index))
    markers = [''] * len(password)
    for r in runs_sorted:
        # 仅在位置未被标记时替换
        conflict = any(markers[i] for i in range(r.start_index, r.start_index + r.length))
        if conflict:
            continue
        for i in range(r.start_index, r.start_index + r.length):
            markers[i] = 'R'
    # 未标记部分按字符类型归类
    out = []
    for i, m in enumerate(markers):
        if m == 'R':
            out.append('R')
        else:
            ch = password[i]
            if ch.isalpha():
                out.append('L')
            elif ch.isdigit():
                out.append('D')
            else:
                out.append('S')
    return ''.join(out)


def write_report(results: list[dict]):
    with open(REPORT_PATH, 'w', encoding='utf-8') as rep:
        rep.write("字典序类口令分析报告\n")
        rep.write("=" * 60 + "\n\n")
        for r in results:
            rep.write(f"== 数据集: {r['label']} ==\n")
            rep.write(f"总密码数: {r['total_passwords']}\n")
            rep.write(f"命中字典序类密码: {r['dict_order_passwords']} ({r['ratio_percent']:.2f}%)\n")
            rep.write(f"升序/降序片段计数: {r['asc_count']} / {r['desc_count']}\n")
            rep.write("长度分布(Top):\n")
            for length, cnt in r['length_counter'].most_common(TOPK):
                rep.write(f"  len={length}: {cnt}\n")
            rep.write("起始字符分布(Top):\n")
            for ch, cnt in r['start_char_counter'].most_common(TOPK):
                rep.write(f"  {ch}: {cnt}\n")
            rep.write("常见连续序列(Top):\n")
            for seq, cnt in r['run_counter'].most_common(TOPK):
                rep.write(f"  {seq}: {cnt}\n")
            rep.write("结构模式(Top):\n")
            for struct, cnt in r['structure_counter'].most_common(TOPK):
                rep.write(f"  {struct}: {cnt}\n")
            rep.write("示例密码(Top):\n")
            for ex in r['examples']:
                rep.write(f"  {ex}\n")
            rep.write("\n")
    # JSON 汇总
    summary = {
        'datasets': [
            {
                'label': r['label'],
                'total': r['total_passwords'],
                'dict_order_total': r['dict_order_passwords'],
                'ratio_percent': r['ratio_percent'],
                'top_runs': r['run_counter'].most_common(TOPK),
                'top_lengths': r['length_counter'].most_common(TOPK),
                'top_start_chars': r['start_char_counter'].most_common(TOPK),
            } for r in results
        ]
    }
    with open(SUMMARY_JSON, 'w', encoding='utf-8') as js:
        json.dump(summary, js, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("字典序连续字符口令分析")
    print("=" * 60)
    results = []
    if os.path.isfile(FILE_YAHOO):
        results.append(analyze_file(FILE_YAHOO, 'Yahoo'))
    if os.path.isfile(FILE_CSDN):
        results.append(analyze_file(FILE_CSDN, 'CSDN'))
    results = [r for r in results if r]
    write_report(results)
    print(f"分析完成，报告: {REPORT_PATH}")
    print(f"汇总: {SUMMARY_JSON}")

if __name__ == '__main__':
    main()
