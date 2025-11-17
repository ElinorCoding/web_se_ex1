import re
import os
from datetime import datetime
import matplotlib.pyplot as plt
from collections import Counter

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'Heiti TC']

# ========== 全局参数 ==========
TOPK = 10
OUTPUT_DIR = "3_date_analysis_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)
REPORT_PATH = os.path.join(OUTPUT_DIR, "日期密码分析报告.txt")

FILE1 = "../plaintxt_yahoo.txt"
FILE2 = "../www.csdn.net.sql"

NOISE_NUMBERS = ['123456', '654321', '123123', '1234', '4321', '1314', '123321','1212','1221','2112','1122','2211']


# ========== 提取可能的日期片段 ==========
def extract_date_candidates(pwd):
    candidates = set()
    occupied = []

    for m in re.finditer(r'\d{1,4}[-/\.]\d{1,4}(?:[-/\.]\d{1,4})?', pwd):
        cleaned = re.sub(r'[-/\.]', '', m.group())
        candidates.add(cleaned)
        occupied.append((m.start(), m.end()))

    for m in re.finditer(r'(?<!\d)\d{4,8}(?!\d)', pwd):
        if any(start <= m.start() < end or start < m.end() <= end for start, end in occupied):
            continue
        candidates.add(m.group())

    valid_dates = set()
    for c in candidates:
        if re.fullmatch(r'(\d)\1{3,}', c) or c in NOISE_NUMBERS:
            continue
        if len(c) not in (4, 6, 8):
            continue

        accepted = False
        for fmt in ("%Y%m%d", "%y%m%d", "%Y%m", "%y%m", "%d%m%Y", "%d%m%y", "%m%d", "%d%m"):
            try:
                datetime.strptime(c, fmt)
                valid_dates.add(c)
                accepted = True
                break
            except ValueError:
                continue
        if not accepted and re.fullmatch(r'(19|20)\d{2}(19|20)\d{2}', c):
            valid_dates.add(c)

    return list(valid_dates)


# ========== 日期格式分类 ==========
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


# ========== 密码提取函数 ==========
def extract_password_yahoo(line):
    parts = line.strip().split(":")
    if len(parts) >= 3:
        return parts[-1].strip()
    return None


def extract_password_csdn(line):
    match = re.search(r"#\s*(.*?)\s*#", line)
    if match:
        return match.group(1).strip()
    return None


def load_passwords(filename):
    passwords = []
    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "yahoo" in filename.lower():
                    pwd = extract_password_yahoo(line)
                elif "csdn" in filename.lower():
                    pwd = extract_password_csdn(line)
                else:
                    pwd = line.strip()
                if pwd:
                    passwords.append(pwd)
    except Exception as e:
        print(f"[错误] 无法读取 {filename}: {e}")
    print(f"[INFO] 成功读取 {len(passwords)} 条密码来自 {filename}")
    return passwords


# ========== 密码结构模式 ==========
def password_to_structure(password, date_candidates):
    s = password
    structure = ''
    i = 0
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


# ========== 日期分析核心函数 ==========
def analyze_date_patterns(passwords, label, report_file):
    all_dates = []
    format_counter = Counter()
    date_in_pwd = 0
    format_to_dates = {}
    structure_counter = Counter()
    year_counter = Counter()
    monthday_counter = Counter()

    for pwd in passwords:
        candidates = extract_date_candidates(pwd)
        valid_dates = [d for d in candidates if classify_date_format(d) != "Other"]
        if not valid_dates:
            continue

        date_in_pwd += 1
        for d in valid_dates:
            fmt = classify_date_format(d)
            format_counter[fmt] += 1
            all_dates.append(d)
            format_to_dates.setdefault(fmt, []).append(d)

            if fmt == "YYYYMMDD":
                year = d[:4]
                mmdd = d[4:8]
                year_counter[year] += 1
                monthday_counter[mmdd] += 1
            elif fmt == "DDMMYYYY":
                year = d[-4:]
                mmdd = d[2:4] + d[0:2]
                year_counter[year] += 1
                monthday_counter[mmdd] += 1
            elif fmt == "YYYYYYYY":
                y1, y2 = d[:4], d[4:8]
                year_counter[y1] += 1
                year_counter[y2] += 1
            elif fmt == "YYYYMM":
                year_counter[d[:4]] += 1
            elif fmt == "YYYY":
                year_counter[d] += 1
            elif fmt == "MMDD":
                monthday_counter[d] += 1
            elif fmt == "DDMM":
                mmdd = d[2:4] + d[0:2]
                monthday_counter[mmdd] += 1

        struct = password_to_structure(pwd, valid_dates)
        structure_counter[struct] += 1

    # ==== 输出报告 ====
    report_file.write(f"\n========= {label} 日期密码统计 =========\n")
    report_file.write(f"密码总数: {len(passwords)}\n")
    report_file.write(f"包含常见日期格式的密码数: {date_in_pwd} ({date_in_pwd / len(passwords) * 100:.2f}%)\n")

    report_file.write("\n日期格式分布:\n")
    for fmt, cnt in format_counter.most_common():
        report_file.write(f"{fmt}: {cnt}\n")

    report_file.write("\n各日期类型 Top-{0} 高频日期:\n".format(TOPK))
    for fmt, dates_list in format_to_dates.items():
        top_dates = Counter(dates_list).most_common(TOPK)
        report_file.write(f"\n[{fmt}] Top-{TOPK}:\n")
        for d, c in top_dates:
            report_file.write(f"{d}: {c}\n")

    report_file.write("\n========= 年份出现频次 Top-{0} =========\n".format(TOPK))
    for y, c in year_counter.most_common(TOPK):
        report_file.write(f"{y}: {c}\n")

    report_file.write("\n========= 月日组合(MMDD)频次 Top-{0} =========\n".format(TOPK))
    for md, c in monthday_counter.most_common(TOPK):
        report_file.write(f"{md}: {c}\n")

    report_file.write(f"\nTop-{TOPK} 密码结构模式(N=日期, L=字母):\n")
    for struct, count in structure_counter.most_common(TOPK):
        report_file.write(f"{struct}: {count}\n")

    # ==== 可视化 ====
    color_map = {"Yahoo": "steelblue", "CSDN": "darkorange"}
    color = color_map.get(label, "gray")

    def plot_topk(counter, title, xlabel, filename):
        items = counter.most_common(TOPK)
        if not items:
            return
        labels = [k for k, _ in items]
        values = [v for _, v in items]
        plt.figure(figsize=(8, 4))
        plt.bar(labels, values, color=color)
        plt.title(title)                  
        plt.xlabel(xlabel)
        plt.ylabel("数量")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, filename))
        plt.close()

    plot_topk(format_counter, f"{label} 日期格式分布", None, f"{label}_date_formats.png")
    plot_topk(year_counter, f"{label} 年份出现频次 Top-{TOPK}", "Year", f"{label}_top_years.png")
    plot_topk(monthday_counter, f"{label} 月日组合出现频次 Top-{TOPK}", "MMDD", f"{label}_top_monthdays.png")
    plot_topk(structure_counter, f"{label} 密码结构 Top-{TOPK}", None, f"{label}_top_structures.png")


# ========== 主函数 ==========
def main():
    print("=" * 60)
    print("📅 日期密码识别统计")
    print("=" * 60)

    pwds1 = load_passwords(FILE1)
    pwds2 = load_passwords(FILE2)

    with open(REPORT_PATH, "w", encoding="utf-8") as report_file:
        analyze_date_patterns(pwds1, "Yahoo", report_file)
        analyze_date_patterns(pwds2, "CSDN", report_file)

    print(f"✅ 分析完成！报告路径: {REPORT_PATH}")
    print(f"📊 图表保存至: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
