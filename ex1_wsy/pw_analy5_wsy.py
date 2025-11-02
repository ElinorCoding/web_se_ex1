import re
import os
import matplotlib.pyplot as plt
from wordfreq import zipf_frequency
from collections import Counter

# ========== 全局参数 ==========
TOPK = 10
OUTPUT_DIR = "5_english_word_analysis_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)
REPORT_PATH = os.path.join(OUTPUT_DIR, "英文单词使用分析报告.txt")

FILE1 = "plaintxt_yahoo.txt"
FILE2 = "www.csdn.net.sql"
COUNT_MODE = 'unique_per_password'  # 每个密码只统计一次单词

# ========== 噪声过滤机制 ==========
COMMON_NON_WORDS = [
    r'^[a-z]{1,2}$',                      # 过短字母串
    r'^(qwe|asd|zxc|poi|lkj|mnb|qaz|wsx|edc|abc)+$',  # 键盘序列
    r'^(aaa|bbb|ccc|ddd|eee|fff)+$',      # 重复字母
]

PINYIN_SURNAMES = {
    'wang', 'li', 'zhang', 'liu', 'chen', 'yang', 'zhao', 'wu', 'zhou', 'xu',
    'sun', 'hu', 'zhu', 'gao', 'lin', 'he', 'guo', 'ma', 'lu', 'dong', 'xie',
    'song', 'shi', 'tang', 'feng', 'yu', 'cai', 'pan', 'deng', 'xiao', 'tian',
    'liang', 'wei', 'jiang', 'han', 'fan', 'peng', 'yuan', 'cao', 'fu', 'ren',
    'fang', 'jing', 'cheng', 'qian', 'mo', 'qiu', 'long', 'chang',
    'qiao', 'mei', 'hua', 'jin', 'tao', 'qi', 'wen', 'yan', 'bao', 'du',
    'ye', 'su', 'pei', 'luo', 'shan', 'hou', 'qin', 'ruan', 'tan', 'lv'
}

def is_noise_word(word):
    if word in PINYIN_SURNAMES:
        return True
    for pat in COMMON_NON_WORDS:
        if re.fullmatch(pat, word):
            return True
    return False

def is_common_english_word(word, min_freq=3.0):
    """用 wordfreq 判断是否为常见英文单词"""
    return zipf_frequency(word, 'en') >= min_freq

# ========== 文件读取 ==========
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

# ========== 贪心拆分函数 ==========
def greedy_word_split_case_insensitive(segment, min_freq):
    """
    大小写无关的贪心最大匹配拆分。
    返回拆分后的单词列表（小写）
    """
    segment_lower = segment.lower()
    i = 0
    n = len(segment_lower)
    results = []
    while i < n:
        match = None
        for j in range(n, i, -1):
            sub = segment_lower[i:j]
            if is_common_english_word(sub, min_freq=min_freq):
                match = sub
                results.append(sub)
                i = j
                break
        if not match:
            i += 1
    return results

# ========== 提取英文单词函数 ==========
def extract_valid_words(pwd, min_freq):
    """
    提取英文单词，同时统计大小写模式
    """
    candidates = re.findall(r"[A-Za-z]+", pwd)
    validated = []
    seen_in_pwd = set()
    case_patterns = []

    for seg in candidates:
        splits = greedy_word_split_case_insensitive(seg, min_freq)

        idx = 0  # 回溯原始大小写
        for w_lower in splits:
            w_orig = seg[idx:idx+len(w_lower)]
            idx += len(w_lower)

            if len(w_lower) < 3 or len(w_lower) > 15:
                continue
            if is_noise_word(w_lower):
                continue
            if not is_common_english_word(w_lower, min_freq=min_freq):
                continue
            if COUNT_MODE == 'unique_per_password' and w_lower in seen_in_pwd:
                continue

            seen_in_pwd.add(w_lower)
            validated.append(w_orig)

            # 大小写模式
            if w_orig.islower():
                case_patterns.append('lower')
            elif w_orig.isupper():
                case_patterns.append('upper')
            elif w_orig[0].isupper() and w_orig[1:].islower():
                case_patterns.append('capitalized')
            else:
                case_patterns.append('mixed')

    return validated, case_patterns

# ========== 英文单词分析 ==========
def analyze_english_words(passwords, label, report_file, min_freq_all=3.0, min_freq_top=5.0):
    all_words = []
    all_cases = []
    word_in_pwd = 0

    for pwd in passwords:
        words, case_patterns = extract_valid_words(pwd, min_freq=min_freq_all)
        if words:
            word_in_pwd += 1
            all_words.extend(words)
            all_cases.extend(case_patterns)

    report_file.write(f"\n========= {label} 英文单词统计 =========\n")
    report_file.write(f"密码总数: {len(passwords)}\n")
    report_file.write(f"包含英文单词的密码数: {word_in_pwd} ({word_in_pwd / len(passwords) * 100:.2f}%)\n")
    report_file.write(f"（已启用噪声过滤，统计min_freq={min_freq_all}，筛选min_freq={min_freq_top}）\n\n")

    # Top10 高频单词
    counter = Counter(all_words)
    high_freq_words = [w for w in counter if is_common_english_word(w.lower(), min_freq=min_freq_top)]
    top_high_freq = sorted(((w, counter[w]) for w in high_freq_words), key=lambda x: x[1], reverse=True)[:TOPK]

    report_file.write(f"Top{TOPK} 高频英文单词 (min_freq={min_freq_top}):\n")
    for w, c in top_high_freq:
        report_file.write(f"{w}: {c}\n")

    # 大小写模式统计
    case_counter = Counter(all_cases)
    report_file.write("\n英文单词大小写模式统计:\n")
    for case, count in case_counter.items():
        report_file.write(f"{case}: {count}\n")

    # === 图表绘制 ===
    if top_high_freq:
        plt.figure(figsize=(8, 4))
        plt.bar([w for w, _ in top_high_freq], [c for _, c in top_high_freq], color='lightgreen')
        plt.title(f"{label} Top-{TOPK} Frequent English Words", fontsize=12)
        plt.xlabel("Word")
        plt.ylabel("Count")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, f"{label}_top_words.png"))
        plt.close()

    if case_counter:
        sorted_cases = sorted(case_counter.items(), key=lambda x: x[1], reverse=True)
        plt.figure(figsize=(6, 4))
        plt.bar([case for case, _ in sorted_cases], [count for _, count in sorted_cases], color='orange')
        plt.title(f"{label} Case Patterns (Sorted by Count)", fontsize=12)
        plt.xlabel("Case")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, f"{label}_case_patterns.png"))
        plt.close()

        # === 饼状图 ===
        plt.figure(figsize=(6, 6))
        plt.pie(
            [count for _, count in sorted_cases],
            labels=[case for case, _ in sorted_cases],
            autopct='%1.1f%%',
            startangle=140
        )
        plt.title(f"{label} Case Patterns Distribution (Pie Chart)", fontsize=12)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, f"{label}_case_patterns_pie.png"))
        plt.close()


# ========== 主程序入口 ==========
def main():
    print("=" * 60)
    print("英文单词识别与使用统计分析")
    print("=" * 60)
    print(f"文件1: {FILE1}")
    print(f"文件2: {FILE2}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60, "\n")

    pwds1 = load_passwords(FILE1)
    pwds2 = load_passwords(FILE2)

    with open(REPORT_PATH, "w", encoding="utf-8") as report_file:
        analyze_english_words(pwds1, "Yahoo", report_file, min_freq_all=3.0, min_freq_top=5.0)
        analyze_english_words(pwds2, "CSDN", report_file, min_freq_all=3.0, min_freq_top=5.0)

    print(f"✅ 英文单词分析完成！报告已保存至: {REPORT_PATH}")
    print(f"📊 图表已保存至: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
