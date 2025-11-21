"""
键盘模式分析模块

功能：
  - 检测密码中的键盘序列（横向/纵向/对角线）
  - 统计各类型分布、高频序列
  - 生成文本报告和 JSON 汇总
"""

import os
import re
import json
from collections import Counter

# 输出配置
TOPK = 10

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "analysis_results")
TASK1_DIR = os.path.dirname(CURRENT_DIR)
REPORT_PATH = os.path.join(OUTPUT_DIR, "keyboard_report.txt")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "keyboard_summary.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 数据文件
FILE_CSDN = os.path.join(TASK1_DIR, "processed_dataset", "csdn_mail_password_username.txt")
FILE_YAHOO = os.path.join(TASK1_DIR, "processed_dataset", "yahoo_mail_password.txt")

# 键盘序列最小长度
MIN_SEQ_LEN = 3

# 键盘布局定义
HORIZONTAL_ROWS = [
    "1234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm"
]

VERTICAL_COLS = [
    "1qaz", "2wsx", "3edc", "4rfv", "5tgb", 
    "6yhn", "7ujm", "8ik,", "9ol.", "0p;/"
]

DIAGONAL_COLS = [
    "!QAZ", "@WSX", "#EDC", "$RFV", "%TGB", 
    "^YHN", "&UJM", "*IK<", "(OL>", ")P:?"
]

SHIFT_ROW = "!@#$%^&*()"

KEYBOARD_SETS = {
    "Horizontal": HORIZONTAL_ROWS + [r.upper() for r in HORIZONTAL_ROWS],
    "Vertical": VERTICAL_COLS,
    "Diagonal": DIAGONAL_COLS + [SHIFT_ROW],
}


# 核心检测函数
def find_keyboard_sequences(pwd, min_seq_len=MIN_SEQ_LEN):
    """检测密码中的键盘序列"""
    pwd_lower = pwd.lower()
    found = {"Horizontal": [], "Vertical": [], "Diagonal": []}
    
    for direction, seq_list in KEYBOARD_SETS.items():
        for seq_row in seq_list:
            for i in range(len(seq_row) - min_seq_len + 1):
                seq = seq_row[i:i + min_seq_len]
                # 正向匹配
                if seq.lower() in pwd_lower:
                    found[direction].append(seq)
                # 反向匹配
                elif seq[::-1].lower() in pwd_lower:
                    found[direction].append(seq[::-1])
    
    return found


# 文件分析函数 
def analyze_file(path: str, label: str, limit: int | None = None):
    if not os.path.isfile(path):
        print(f"[WARN] 文件不存在: {path}")
        return None
    
    print(f"正在分析: {path}")
    
    type_counts = {"Horizontal": 0, "Vertical": 0, "Diagonal": 0}
    seq_counter = {"Horizontal": Counter(), "Vertical": Counter(), "Diagonal": Counter()}
    keyboard_pwds = []
    
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
            
            # 检测键盘序列
            found = find_keyboard_sequences(password, MIN_SEQ_LEN)
            has_any = False
            
            for direction, seqs in found.items():
                if seqs:
                    type_counts[direction] += 1
                    seq_counter[direction].update(seqs)
                    has_any = True
            
            if has_any:
                keyboard_pwds.append(password)
            
            if limit and total >= limit:
                break
    
    total_kb = len(keyboard_pwds)
    ratio = total_kb / total * 100 if total else 0
    
    return {
        'label': label,
        'file': path,
        'total_passwords': total,
        'keyboard_passwords': total_kb,
        'ratio_percent': ratio,
        'type_counts': type_counts,
        'seq_counter': seq_counter,
        'examples': keyboard_pwds[:TOPK],
    }


# 报告生成
def write_report(results: list[dict]):
    """
    生成文本报告和 JSON 汇总
    """
    # 文本报告 
    with open(REPORT_PATH, 'w', encoding='utf-8') as rep:
        rep.write("键盘模式口令分析报告\n")
        rep.write("=" * 60 + "\n\n")
        
        for r in results:
            rep.write(f"== 数据集: {r['label']} ==\n")
            rep.write(f"总密码数: {r['total_passwords']}\n")
            rep.write(f"检测为键盘模式的密码数: {r['keyboard_passwords']} ({r['ratio_percent']:.2f}%)\n\n")
            
            # 类型分布
            total_kb = r['keyboard_passwords']
            for direction in ["Horizontal", "Vertical", "Diagonal"]:
                cnt = r['type_counts'][direction]
                pct = cnt / total_kb * 100 if total_kb else 0
                rep.write(f"  {direction} 类型: {cnt} 个 ({pct:.2f}%)\n")
            rep.write("\n")
            
            # Top 10 键盘序列（按类型）
            for direction in ["Horizontal", "Vertical", "Diagonal"]:
                rep.write(f"【{direction} 类型 Top {TOPK} 键盘序列】\n")
                for seq, cnt in r['seq_counter'][direction].most_common(TOPK):
                    rep.write(f"  {seq}: {cnt}\n")
                rep.write("\n")
            
            # 出现次数超过100的序列
            rep.write("【出现次数超过100的键盘序列】\n")
            has_over100 = False
            for direction, counter in r['seq_counter'].items():
                over100 = [(s, c) for s, c in counter.items() if c > 100]
                if over100:
                    has_over100 = True
                    rep.write(f"\n{direction} 类型:\n")
                    for s, c in sorted(over100, key=lambda x: x[1], reverse=True):
                        rep.write(f"  {s}: {c}\n")
            if not has_over100:
                rep.write("  无\n")
            rep.write("\n")
            
            # 样例密码
            rep.write(f"样例键盘模式密码（前{TOPK}条）:\n")
            for sample in r['examples']:
                rep.write(f"  {sample}\n")
            rep.write("\n")
    
    # JSON 汇总
    summary = {
        'datasets': []
    }
    
    for r in results:
        # 合并所有类型的序列计数（用于整体 Top 序列图）
        all_seqs = sum(r['seq_counter'].values(), Counter())
        
        dataset_summary = {
            'label': r['label'],
            'total': r['total_passwords'],
            'keyboard_total': r['keyboard_passwords'],
            'ratio_percent': r['ratio_percent'],
            'type_distribution': r['type_counts'],
            'top_sequences': all_seqs.most_common(TOPK),  # 整体 Top 序列
            'top_sequences_by_type': {  # 按类型分组的 Top 序列
                direction: counter.most_common(TOPK)
                for direction, counter in r['seq_counter'].items()
            },
        }
        summary['datasets'].append(dataset_summary)
    
    with open(SUMMARY_JSON, 'w', encoding='utf-8') as js:
        json.dump(summary, js, ensure_ascii=False, indent=2)


def main():
    """
    主函数：分析所有数据集并生成报告
    """
    print("=" * 60)
    print("键盘模式口令分析")
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