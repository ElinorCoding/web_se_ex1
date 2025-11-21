"""
密码复杂度分析模块

功能：
  - 计算密码的香农熵 (Shannon Entropy)
  - 统计熵值分布 (低/中/高)
  - 提取高熵密码
  - 生成 JSON 汇总供 visualize_results.py 使用
"""

import os
import math
import json
from collections import Counter

# 配置
TOPK = 10

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "analysis_results")
TASK1_DIR = os.path.dirname(CURRENT_DIR)
REPORT_PATH = os.path.join(OUTPUT_DIR, "entropy_report.txt")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "entropy_summary.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 数据文件
FILE_CSDN = os.path.join(TASK1_DIR, "processed_dataset", "csdn_mail_password_username.txt")
FILE_YAHOO = os.path.join(TASK1_DIR, "processed_dataset", "yahoo_mail_password.txt")


# 核心算法
def shannon_entropy(password):
    """计算一个密码的香农熵 Shannon Entropy"""
    if not password:
        return 0
    counter = Counter(password)
    length = len(password)
    probs = [count / length for count in counter.values()]
    entropy = -sum(p * math.log2(p) for p in probs)
    return entropy


# 文件分析函数
def analyze_file(path: str, label: str):
    if not os.path.isfile(path):
        print(f"[WARN] 文件不存在: {path}")
        return None

    print(f"正在分析: {path}")
    
    passwords = []
    entropies = []
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            raw = line.strip()
            if not raw: continue
            
            # 兼容格式解析
            if ':' in raw:
                parts = raw.split(':')
                pwd = parts[-1].strip()
            else:
                pwd = raw
            
            if not pwd: continue
            
            ent = shannon_entropy(pwd)
            passwords.append(pwd)
            entropies.append(ent)

    if not entropies:
        return None

    # 统计指标
    avg_entropy = sum(entropies) / len(entropies)
    var_entropy = sum((e - avg_entropy) ** 2 for e in entropies) / len(entropies)
    std_entropy = math.sqrt(var_entropy)

    # 分类分布
    low = len([e for e in entropies if e < 2])
    mid = len([e for e in entropies if 2 <= e < 4])
    high = len([e for e in entropies if e >= 4])
    total = len(entropies)

    # Top10 熵最高密码
    # 使用 zip 打包密码和熵值，按熵值排序
    top10 = sorted(zip(passwords, entropies), key=lambda x: x[1], reverse=True)[:TOPK]

    max_val = 8.0
    step = 0.1
    num_bins = int(max_val / step) + 1 
    bins = [0] * num_bins
    
    for e in entropies:
        idx = int(e / step)
        if idx < 0: idx = 0
        if idx >= num_bins: idx = num_bins - 1
        bins[idx] += 1
    
    # 构造数据
    hist_data = []
    for i in range(num_bins):
        val = bins[i]
        label_str = f"{i * step:.1f}"
        hist_data.append((label_str, val))

    return {
        'label': label,
        'total': total,
        'avg_entropy': avg_entropy,
        'std_entropy': std_entropy,
        'level_counts': {'Low (0-2)': low, 'Medium (2-4)': mid, 'High (>4)': high},
        'top10_high_entropy': top10,
        'entropy_histogram': hist_data
    }


# 报告生成 
def write_report(results):
    # 1. 文本报告
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write("密码复杂度分析报告 (基于信息熵)\n================================\n")
        f.write("说明：熵越高表示随机性越强，密码越安全。\n\n")
        
        for r in results:
            f.write(f"========= {r['label']} 熵分析结果 =========\n")
            f.write(f"平均熵值: {r['avg_entropy']:.3f} bits/char\n")
            f.write(f"标准差: {r['std_entropy']:.3f}\n")
            
            total = r['total']
            levels = r['level_counts']
            f.write(f"低熵(0~2): {levels['Low (0-2)']} ({levels['Low (0-2)']/total*100:.2f}%)\n")
            f.write(f"中熵(2~4): {levels['Medium (2-4)']} ({levels['Medium (2-4)']/total*100:.2f}%)\n")
            f.write(f"高熵(>4): {levels['High (>4)']} ({levels['High (>4)']/total*100:.2f}%)\n")
            
            f.write("\nTop 10 熵最高密码:\n")
            for p, e in r['top10_high_entropy']:
                f.write(f"  {p} -> {e:.3f}\n")
            f.write("\n")

    # 2. JSON 汇总
    summary = {'datasets': []}
    for r in results:
        summary['datasets'].append({
            'label': r['label'],
            'avg_entropy': r['avg_entropy'],
            'level_dist': list(r['level_counts'].items()), # 转为列表供绘图
            'histogram': r['entropy_histogram']
        })
    
    with open(SUMMARY_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    print("="*60 + "\n密码复杂度分析 (Shannon Entropy)\n" + "="*60)
    results = []
    if os.path.isfile(FILE_YAHOO):
        results.append(analyze_file(FILE_YAHOO, 'Yahoo'))
    if os.path.isfile(FILE_CSDN):
        results.append(analyze_file(FILE_CSDN, 'CSDN'))  

    write_report(results)
    print(f"分析完成，报告: {REPORT_PATH}")
    print(f"汇总: {SUMMARY_JSON}")

if __name__ == '__main__':
    main()