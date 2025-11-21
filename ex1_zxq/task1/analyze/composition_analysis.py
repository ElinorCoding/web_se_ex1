"""
密码构成与结构分析模块

功能：
  - 密码长度分布统计
  - 字符类型分析（数字、小写字母、大写字母、符号）
  - 密码结构模式分析（如 LLDD、ULLDS 等）
  - 高频子串分析
  - 两个数据集的交叉对比
  - 生成文本报告和 JSON 汇总（不生成图表，由 visualize_results.py 负责）
"""

import os
import re
import json
from collections import Counter

# 输出配置
TOPK = 10
SUBSTR_MIN = 3
SUBSTR_MAX = 6

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "analysis_results")
TASK1_DIR = os.path.dirname(CURRENT_DIR)
REPORT_PATH = os.path.join(OUTPUT_DIR, "composition_report.txt")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "composition_summary.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 数据文件
FILE_CSDN = os.path.join(TASK1_DIR, "processed_dataset", "csdn_mail_password_username.txt")
FILE_YAHOO = os.path.join(TASK1_DIR, "processed_dataset", "yahoo_mail_password.txt")

# 工具函数
def char_type(c):
    """判断字符类型"""
    if c.isdigit():
        return 'D'  # Digit
    elif c.islower():
        return 'L'  # Lowercase
    elif c.isupper():
        return 'U'  # Uppercase
    else:
        return 'S'  # Symbol


def password_pattern(pwd):
    return ''.join(char_type(c) for c in pwd)


def ngram_generator(s, n):
    """生成 n-gram 子串"""
    return [s[i:i + n] for i in range(len(s) - n + 1)]


def analyze_file(path: str, label: str, limit: int | None = None):
    if not os.path.isfile(path):
        print(f"[WARN] 文件不存在: {path}")
        return None
    
    print(f"正在分析: {path}")

    passwords = []
    total = 0
    
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
            
            if limit and total >= limit:
                break

            passwords.append(password)

    if not passwords:
        return None  
    
    # 基本统计
    lengths = [len(p) for p in passwords]
    avg_len = sum(lengths) / len(lengths)
    length_counter = Counter(lengths)
    
    # 字符类型统计
    type_counter = Counter()
    for pwd in passwords:
        for c in pwd:
            type_counter[char_type(c)] += 1
    total_chars = sum(type_counter.values())
    
    # 结构模式分析
    patterns = [password_pattern(p) for p in passwords]
    pattern_counter = Counter(patterns)
    
    # 高频子串分析
    substring_counter = Counter()
    for pwd in passwords:
        for n in range(SUBSTR_MIN, SUBSTR_MAX + 1):
            substring_counter.update(ngram_generator(pwd, n))
    
    return {
        'label': label,
        'file': path,
        'total_passwords': len(passwords),
        'avg_length': avg_len,
        'length_counter': length_counter,
        'type_counter': type_counter,
        'total_chars': total_chars,
        'pattern_counter': pattern_counter,
        'substring_counter': substring_counter,
        'passwords': passwords,  # 用于交叉分析
    }


# 交叉对比分析 
def analyze_cross(result1, result2):
    """两个密码集的交叉对比"""
    counter1 = Counter(result1['passwords'])
    counter2 = Counter(result2['passwords'])
    inter_pwds = set(counter1.keys()) & set(counter2.keys())
    inter_counts = {pwd: counter1[pwd] + counter2[pwd] for pwd in inter_pwds}
    top_common = sorted(inter_counts.items(), key=lambda x: x[1], reverse=True)[:TOPK]
    
    return {
        'file1_unique': len(counter1),
        'file2_unique': len(counter2),
        'common_count': len(inter_pwds),
        'top_common': top_common,
        'counter1': counter1,
        'counter2': counter2,
    }


# ========== 报告生成 ==========
def write_report(results: list[dict], cross_result: dict | None = None):
    """
    生成文本报告和 JSON 汇总
    """
    type_names = {'L': '小写字母', 'U': '大写字母', 'D': '数字', 'S': '符号'}
    
    # ========== 文本报告 ==========
    with open(REPORT_PATH, 'w', encoding='utf-8') as rep:
        rep.write("密码构成与结构分析报告\n")
        rep.write("=" * 60 + "\n\n")
        
        for r in results:
            rep.write(f"== 数据集: {r['label']} ==\n")
            rep.write(f"密码总数: {r['total_passwords']}\n")
            rep.write(f"平均长度: {r['avg_length']:.2f}\n")
            rep.write("字符类型说明: L=小写字母, U=大写字母, D=数字, S=符号\n\n")
            
            # 字符类型分布
            rep.write("字符类型分布:\n")
            for t, cnt in r['type_counter'].items():
                ratio = cnt / r['total_chars'] * 100
                rep.write(f"  {type_names[t]} ({t}): {cnt} ({ratio:.2f}%)\n")
            rep.write("\n")
            
            # Top 结构模式
            rep.write(f"Top-{TOPK} 密码结构模式:\n")
            for pattern, cnt in r['pattern_counter'].most_common(TOPK):
                rep.write(f"  {pattern}: {cnt}\n")
            rep.write("\n")
            
            # Top 高频子串
            rep.write(f"Top-{TOPK} 高频子串 (长度 {SUBSTR_MIN}~{SUBSTR_MAX}):\n")
            for substr, cnt in r['substring_counter'].most_common(TOPK):
                rep.write(f"  '{substr}': {cnt}\n")
            rep.write("\n")
        
        # 交叉对比
        if cross_result:
            rep.write("文件交叉对比分析\n")
            rep.write("=" * 60 + "\n")
            rep.write(f"文件1 唯一密码数: {cross_result['file1_unique']}\n")
            rep.write(f"文件2 唯一密码数: {cross_result['file2_unique']}\n")
            rep.write(f"共同出现的密码数: {cross_result['common_count']}\n\n")
            
            if cross_result['top_common']:
                rep.write(f"Top {TOPK} 共同高频密码:\n")
                for pwd, cnt in cross_result['top_common']:
                    cnt1 = cross_result['counter1'][pwd]
                    cnt2 = cross_result['counter2'][pwd]
                    rep.write(f"  '{pwd}': 共出现 {cnt} 次 (文件1 {cnt1} 次, 文件2 {cnt2} 次)\n")
            else:
                rep.write("  无共同密码。\n")
            rep.write("\n")
    
    # JSON 汇总
    summary = {
        'datasets': []
    }
    
    for r in results:
        dataset_summary = {
            'label': r['label'],
            'total': r['total_passwords'],
            'avg_length': r['avg_length'],
            'type_distribution': {
                type_names[t]: {'count': cnt, 'ratio': cnt / r['total_chars'] * 100}
                for t, cnt in r['type_counter'].items()
            },
            'length_distribution': r['length_counter'].most_common(20),  # Top 20 长度
            'top_patterns': r['pattern_counter'].most_common(TOPK),
            'top_substrings': r['substring_counter'].most_common(TOPK),
        }
        summary['datasets'].append(dataset_summary)
    
    # 交叉对比数据
    if cross_result:
        summary['cross_analysis'] = {
            'file1_unique': cross_result['file1_unique'],
            'file2_unique': cross_result['file2_unique'],
            'common_count': cross_result['common_count'],
            'top_common': cross_result['top_common'],
        }
    
    with open(SUMMARY_JSON, 'w', encoding='utf-8') as js:
        json.dump(summary, js, ensure_ascii=False, indent=2)


def main():
    """
    主函数：分析所有数据集并生成报告
    """
    print("=" * 60)
    print("密码构成与结构分析")
    print("=" * 60)
    
    results = []
    if os.path.isfile(FILE_YAHOO):
        results.append(analyze_file(FILE_YAHOO, 'Yahoo'))
    if os.path.isfile(FILE_CSDN):
        results.append(analyze_file(FILE_CSDN, 'CSDN'))  
    results = [r for r in results if r]

    # 交叉对比
    cross_result = None
    if len(results) == 2:
        print("正在进行交叉对比...")
        cross_result = analyze_cross(results[0], results[1])
        print(f"共同密码: {cross_result['common_count']}")
    
    write_report(results, cross_result)
    print(f"分析完成，报告: {REPORT_PATH}")
    print(f"汇总: {SUMMARY_JSON}")

if __name__ == '__main__':
    main()