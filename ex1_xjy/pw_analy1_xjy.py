#本代码完成分析1：① 密码构成元素分析（数字、字符、字母等）和结构分析，得到密码中这些基本元素常用的组合方法；
# 分析结果保存在1_analysis_results目录下
import re
import matplotlib.pyplot as plt
from collections import Counter
import os

# ========== 全局参数 ==========
SUBSTR_MIN = 3
SUBSTR_MAX = 6
TOPK = 10

# ========== 文件路径 ==========
FILE1 = "plaintxt_yahoo.txt"
FILE2 = "www.csdn.net.sql"

# ========== 输出目录 ==========
OUTPUT_DIR = "1_analysis_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)
REPORT_PATH = os.path.join(OUTPUT_DIR, "密码分析报告.txt")

# ========== 工具函数 ==========
def extract_password_yahoo(line):
    """提取Yahoo格式的密码"""
    parts = line.strip().split(":")
    if len(parts) >= 3:
        return parts[-1].strip()
    return None


def extract_password_csdn(line):
    """提取CSDN格式的密码"""
    match = re.search(r"#\s*(.*?)\s*#", line)
    if match:
        return match.group(1).strip()
    return None


def load_passwords(filename):
    """根据文件名自动选择提取函数"""
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

    print(f"[INFO] 成功读取 {len(passwords)} 条密码来自 {filename}\n")
    return passwords


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
    """返回密码的结构模式，如 'LLDD'"""
    return ''.join(char_type(c) for c in pwd)


def ngram_generator(s, n):
    """生成 n-gram 子串"""
    return (s[i:i + n] for i in range(len(s) - n + 1))


# ========== 分析函数 ==========
def analyze_basic(passwords, label, report_file):
    """基本统计 + 图表"""
    if not passwords:
        return

    lengths = [len(p) for p in passwords]
    avg_len = sum(lengths) / len(lengths)
    type_counter = Counter()
    for pwd in passwords:
        for c in pwd:
            type_counter[char_type(c)] += 1
    total_chars = sum(type_counter.values())

    # === 写入报告 ===
    report_file.write(f"\n========= {label} 基本统计 =========\n")
    report_file.write(f"密码总数: {len(passwords)}\n")
    report_file.write(f"平均长度: {avg_len:.2f}\n")
    report_file.write("字符类型说明: L=小写字母, U=大写字母, D=数字, S=符号\n\n")

    for t, cnt in type_counter.items():
        ratio = cnt / total_chars * 100
        typename = {'L': '小写字母', 'U': '大写字母', 'D': '数字', 'S': '符号'}[t]
        report_file.write(f"{typename} ({t}): {cnt} ({ratio:.2f}%)\n")

    # === 图表 1: 密码长度分布 ===
    plt.figure(figsize=(6, 4))
    plt.hist(lengths, bins=range(1, 21), edgecolor='black')
    plt.title(f"{label} Password Length Distribution", fontsize=12)
    plt.xlabel("Password Length")
    plt.ylabel("Count")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{label}_length_distribution.png"))
    plt.close()

    # === 图表 2: 字符类型占比 ===
    plt.figure(figsize=(5, 5))
    type_labels = {'L': 'Lowercase', 'U': 'Uppercase', 'D': 'Digit', 'S': 'Symbol'}
    labels = [f"{t} ({type_labels.get(t, 'Unknown')})" for t in type_counter.keys()]
    plt.pie(type_counter.values(), labels=labels, autopct="%1.1f%%", startangle=90)
    plt.title(f"{label} Character Type Distribution", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{label}_char_types.png"))
    plt.close()


def analyze_patterns(passwords, label, report_file):
    """结构模式分析"""
    patterns = [password_pattern(p) for p in passwords]
    counter = Counter(patterns)
    report_file.write(f"\n========= {label} Top-{TOPK} 密码结构模式 =========\n")
    for pattern, cnt in counter.most_common(TOPK):
        report_file.write(f"{pattern}: {cnt}\n")

    # 图表
    top_patterns = counter.most_common(TOPK)
    plt.figure(figsize=(8, 4))
    plt.bar([p for p, _ in top_patterns], [c for _, c in top_patterns])
    plt.title(f"{label} Top-{TOPK} Password Patterns", fontsize=12)
    plt.xticks(rotation=45)
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{label}_pattern_top{TOPK}.png"))
    plt.close()


def analyze_substrings(passwords, label, report_file):
    """高频子串分析"""
    substring_counter = Counter()
    for pwd in passwords:
        for n in range(SUBSTR_MIN, SUBSTR_MAX + 1):
            substring_counter.update(ngram_generator(pwd, n))

    report_file.write(f"\n========= {label} Top-{TOPK} 高频子串 (长度 {SUBSTR_MIN}~{SUBSTR_MAX}) =========\n")
    for substr, cnt in substring_counter.most_common(TOPK):
        report_file.write(f"'{substr}': {cnt}\n")


def analyze_cross(file1_pwds, file2_pwds, report_file):
    """两个密码集的交叉对比"""
    counter1 = Counter(file1_pwds)
    counter2 = Counter(file2_pwds)
    inter_pwds = set(counter1.keys()) & set(counter2.keys())
    inter_counts = {pwd: counter1[pwd] + counter2[pwd] for pwd in inter_pwds}
    top_common = sorted(inter_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    report_file.write("\n========= 文件交叉对比 =========\n")
    report_file.write(f"文件1 唯一密码数: {len(counter1)}\n")
    report_file.write(f"文件2 唯一密码数: {len(counter2)}\n")
    report_file.write(f"共同出现的密码数: {len(inter_pwds)}\n\n")

    if top_common:
        report_file.write("Top 10 共同高频密码:\n")
        for pwd, cnt in top_common:
            report_file.write(f"'{pwd}': 共出现 {cnt} 次 (文件1 {counter1[pwd]} 次, 文件2 {counter2[pwd]} 次)\n")
    else:
        report_file.write("无共同密码。\n")


# ========== 主程序入口 ==========
def main():
    print("=" * 60)
    print("密码特征分析实验 (图表英文版)")
    print("=" * 60)
    print(f"文件1: {FILE1}")
    print(f"文件2: {FILE2}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60, "\n")

    pwds1 = load_passwords(FILE1)
    pwds2 = load_passwords(FILE2)

    with open(REPORT_PATH, "w", encoding="utf-8") as report_file:
        analyze_basic(pwds1, "Yahoo", report_file)
        analyze_patterns(pwds1, "Yahoo", report_file)
        analyze_substrings(pwds1, "Yahoo", report_file)

        analyze_basic(pwds2, "CSDN", report_file)
        analyze_patterns(pwds2, "CSDN", report_file)
        analyze_substrings(pwds2, "CSDN", report_file)

        analyze_cross(pwds1, pwds2, report_file)

    print(f"分析完成！报告已保存至: {REPORT_PATH}")
    print(f"图表已保存至: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
