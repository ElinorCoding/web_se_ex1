"""
日期模式分析模块 (整合自 pw_analy3_wsy.py)

功能：
  - 识别密码中的日期格式 (YYYYMMDD, MMDDYYYY 等)
  - 统计年份分布
  - 统计日期格式分布
  - 生成 JSON 汇总供可视化使用
"""
import os
import re
import json
from datetime import datetime
from collections import Counter

# 输出配置
TOPK = 10

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "analysis_results")
TASK1_DIR = os.path.dirname(CURRENT_DIR)
REPORT_PATH = os.path.join(OUTPUT_DIR, "date_report.txt")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "date_summary.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 数据文件
FILE_CSDN = os.path.join(TASK1_DIR, "processed_dataset", "csdn_mail_password_username.txt")
FILE_YAHOO = os.path.join(TASK1_DIR, "processed_dataset", "yahoo_mail_password.txt")

NOISE_NUMBERS = {'123456', '654321', '123123', '1234', '4321', '1314', '123321', '1212', '1221', '2112', '1122', '2211'}

# 提取日期
def extract_date_candidates(pwd):
    candidates = set()
    occupied = []

    # 1. 带分隔符的日期 (如 1990-01-01)
    for m in re.finditer(r'\d{1,4}[-/\.]\d{1,4}(?:[-/\.]\d{1,4})?', pwd):
        cleaned = re.sub(r'[-/\.]', '', m.group())
        candidates.add(cleaned)
        occupied.append((m.start(), m.end()))

    # 2. 纯数字日期 (如 19900101)
    for m in re.finditer(r'(?<!\d)\d{4,8}(?!\d)', pwd):
        # 避免与已提取的带分隔符日期重叠
        if any(start <= m.start() < end or start < m.end() <= end for start, end in occupied):
            continue
        candidates.add(m.group())

    valid_dates = set()
    for c in candidates:
        # 排除简单重复数字和噪声
        if re.fullmatch(r'(\d)\1{3,}', c) or c in NOISE_NUMBERS:
            continue
        if len(c) not in (4, 6, 8):
            continue

        accepted = False
        # 尝试解析日期
        for fmt in ("%Y%m%d", "%y%m%d", "%Y%m", "%y%m", "%d%m%Y", "%d%m%y", "%m%d", "%d%m"):
            try:
                datetime.strptime(c, fmt)
                valid_dates.add(c)
                accepted = True
                break
            except ValueError:
                continue
        
        # 特殊处理双年份 (如 19801980)
        if not accepted and re.fullmatch(r'(19|20)\d{2}(19|20)\d{2}', c):
            valid_dates.add(c)

    return list(valid_dates)


# 判断日期格式
def classify_date_format(date_str):
    if re.fullmatch(r'(19|20)\d{2}(19|20)\d{2}', date_str):
        return "YYYYYYYY"
    if re.fullmatch(r'(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])', date_str):
        return "YYYYMMDD"
    if re.fullmatch(r'(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])(19|20)\d{2}', date_str):
        return "DDMMYYYY"
    if re.fullmatch(r'(19|20)\d{2}(0[1-9]|1[0-2])', date_str):
        return "YYYYMM"
    if re.fullmatch(r'(19|20)\d{2}', date_str):
        return "YYYY"
    if re.fullmatch(r'(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])', date_str):
        return "MMDD"
    if re.fullmatch(r'(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])', date_str):
        return "DDMM"
    return "Other"


# 生成密码结构模式 (N=日期, L=字母, D=数字, S=符号)
def password_to_structure(password, date_candidates):
    
    s = password
    structure = ''
    i = 0
    # 优先匹配较长的日期串
    sorted_dates = sorted(date_candidates, key=lambda x: -len(x))
    
    while i < len(s):
        matched_date = None
        for d in sorted_dates:
            if s.startswith(d, i):
                matched_date = d
                break
        if matched_date:
            structure += 'N' * len(matched_date)
            i += len(matched_date)
        else:
            ch = s[i]
            if ch.isalpha():
                structure += 'L'
            elif ch.isdigit():
                structure += 'D'
            else:
                structure += 'S'
            i += 1
    return structure


# 文件分析函数 
def analyze_file(path: str, label: str):
    if not os.path.isfile(path):
        print(f"[WARN] 文件不存在: {path}")
        return None
    
    print(f"正在分析: {path}")
    
    # 统计器
    format_counter = Counter()
    year_counter = Counter()
    monthday_counter = Counter()
    structure_counter = Counter()
    format_to_dates = {}  # 记录每种格式下的具体日期
    
    total = 0
    date_pwds_count = 0
    
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

            # 1. 提取日期候选
            candidates = extract_date_candidates(password)
            valid_dates = [d for d in candidates if classify_date_format(d) != "Other"]
            
            if not valid_dates:
                continue
            
            date_pwds_count += 1
            
            # 2. 统计日期信息
            for d in valid_dates:
                fmt = classify_date_format(d)
                format_counter[fmt] += 1
                format_to_dates.setdefault(fmt, []).append(d)

                # 提取年份和月日
                if fmt == "YYYYMMDD":
                    year_counter[d[:4]] += 1
                    monthday_counter[d[4:8]] += 1
                elif fmt == "DDMMYYYY":
                    year_counter[d[-4:]] += 1
                    monthday_counter[d[2:4] + d[0:2]] += 1
                elif fmt == "YYYYYYYY":
                    year_counter[d[:4]] += 1
                    year_counter[d[4:8]] += 1
                elif fmt == "YYYYMM":
                    year_counter[d[:4]] += 1
                elif fmt == "YYYY":
                    year_counter[d] += 1
                elif fmt == "MMDD":
                    monthday_counter[d] += 1
                elif fmt == "DDMM":
                    monthday_counter[d[2:4] + d[0:2]] += 1

            # 3. 生成结构模式
            struct = password_to_structure(password, valid_dates)
            structure_counter[struct] += 1

    return {
        'label': label,
        'total': total,
        'date_count': date_pwds_count,
        'ratio': (date_pwds_count / total * 100) if total else 0,
        'format_counter': format_counter,
        'year_counter': year_counter,
        'monthday_counter': monthday_counter,
        'structure_counter': structure_counter,
        'format_to_dates': format_to_dates
    }


# 报告生成
def write_report(results):
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write("日期模式分析报告\n====================\n\n")
        
        for r in results:
            f.write(f"========= {r['label']} 日期密码统计 =========\n")
            f.write(f"密码总数: {r['total']}\n")
            f.write(f"包含常见日期格式的密码数: {r['date_count']} ({r['ratio']:.2f}%)\n")
            
            f.write("\n日期格式分布:\n")
            for fmt, cnt in r['format_counter'].most_common():
                f.write(f"{fmt}: {cnt}\n")
            
            f.write(f"\n各日期类型 Top-{TOPK} 高频日期:\n")
            for fmt, dates in r['format_to_dates'].items():
                top_dates = Counter(dates).most_common(TOPK)
                f.write(f"\n[{fmt}] Top-{TOPK}:\n")
                for d, c in top_dates:
                    f.write(f"{d}: {c}\n")
            
            f.write(f"\n年份出现频次 Top-{TOPK}:\n")
            for y, c in r['year_counter'].most_common(TOPK):
                f.write(f"{y}: {c}\n")
                
            f.write(f"\n月日组合(MMDD)频次 Top-{TOPK}:\n")
            for md, c in r['monthday_counter'].most_common(TOPK):
                f.write(f"{md}: {c}\n")
                
            f.write(f"\nTop-{TOPK} 密码结构模式(N=日期, L=字母):\n")
            for struct, count in r['structure_counter'].most_common(TOPK):
                f.write(f"{struct}: {count}\n")
            f.write("\n")

    # JSON 汇总
    summary = {'datasets': []}
    for r in results:
        summary['datasets'].append({
            'label': r['label'],
            'format_dist': r['format_counter'].most_common(),
            'year_dist': r['year_counter'].most_common(TOPK),
            'monthday_dist': r['monthday_counter'].most_common(TOPK),
            'structure_dist': r['structure_counter'].most_common(TOPK)
        })
    
    with open(SUMMARY_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    print("="*60 + "\n日期模式分析\n" + "="*60)
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