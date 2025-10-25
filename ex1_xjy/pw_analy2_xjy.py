import re
import matplotlib.pyplot as plt
from collections import Counter
import os

# ========== 全局参数 ==========
FILE1 = "plaintxt_yahoo.txt"
FILE2 = "www.csdn.net.sql"
OUTPUT_DIR = "analysis_results_keyboard_v3"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========== 键盘布局扩展 ==========
HORIZONTAL_ROWS = [
    "1234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm"
]

VERTICAL_COLS = [
    "1qaz", "2wsx", "3edc", "4rfv", "5tgb", "6yhn", "7ujm", "8ik,", "9ol.", "0p;/"
]

DIAGONAL_COLS = [
    "!QAZ", "@WSX", "#EDC", "$RFV", "%TGB", "^YHN", "&UJM", "*IK<", "(OL>", ")P:?"
]

SHIFT_ROW = "!@#$%^&*()"

KEYBOARD_SETS = {
    "Horizontal": HORIZONTAL_ROWS + [r.upper() for r in HORIZONTAL_ROWS],
    "Vertical": VERTICAL_COLS,
    "Diagonal": DIAGONAL_COLS + [SHIFT_ROW],
}


# ========== 提取函数 ==========
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
                if not line.strip():
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
        print(f"[ERROR] 读取文件失败: {e}")
    print(f"[INFO] 从 {filename} 读取到 {len(passwords)} 条密码。")
    return passwords


# ========== 键盘序列检测 ==========
def find_keyboard_sequences(pwd, min_seq_len=3):
    pwd_lower = pwd.lower()
    found = {"Horizontal": [], "Vertical": [], "Diagonal": []}
    for direction, seq_list in KEYBOARD_SETS.items():
        for seq_row in seq_list:
            for i in range(len(seq_row) - min_seq_len + 1):
                seq = seq_row[i:i + min_seq_len]
                if seq.lower() in pwd_lower:
                    found[direction].append(seq)
                elif seq[::-1].lower() in pwd_lower:
                    found[direction].append(seq[::-1])
    return found


# ========== 主分析函数 ==========
def analyze_keyboard_patterns(passwords, label):
    total = len(passwords)
    type_counts = {"Horizontal": 0, "Vertical": 0, "Diagonal": 0}
    seq_counter = {"Horizontal": Counter(), "Vertical": Counter(), "Diagonal": Counter()}
    keyboard_pwds = []

    for pwd in passwords:
        found = find_keyboard_sequences(pwd)
        has_any = False
        for direction, seqs in found.items():
            if seqs:
                type_counts[direction] += 1
                seq_counter[direction].update(seqs)
                has_any = True
        if has_any:
            keyboard_pwds.append(pwd)

    total_kb = len(keyboard_pwds)
    ratio = total_kb / total * 100 if total else 0

    print(f"\n========= {label} 键盘模式分析 =========")
    print(f"总密码数: {total}")
    print(f"检测为键盘模式的密码: {total_kb} ({ratio:.2f}%)")

    for direction in type_counts:
        cnt = type_counts[direction]
        pct = cnt / total_kb * 100 if total_kb else 0
        print(f"  {direction}: {cnt} ({pct:.2f}%)")

    # === 输出报告 ===
    report_path = os.path.join(OUTPUT_DIR, f"{label}_keyboard_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"{label} 键盘模式分析报告\n")
        f.write("=" * 50 + "\n")
        f.write(f"总密码数: {total}\n")
        f.write(f"检测为键盘模式的密码数: {total_kb} ({ratio:.2f}%)\n\n")
        for direction in type_counts:
            cnt = type_counts[direction]
            pct = cnt / total_kb * 100 if total_kb else 0
            f.write(f"{direction} 类型: {cnt} 个 ({pct:.2f}%)\n")
        f.write("\n\n")

        for direction in seq_counter:
            f.write(f"【{direction} 类型 Top 10 键盘序列】\n")
            for seq, cnt in seq_counter[direction].most_common(10):
                f.write(f"  {seq}: {cnt}\n")
            f.write("\n")

        # 输出超过100次的序列
        f.write("【出现次数超过100的键盘序列】\n")
        for direction, counter in seq_counter.items():
            over100 = [(s, c) for s, c in counter.items() if c > 100]
            if over100:
                f.write(f"\n{direction} 类型:\n")
                for s, c in over100:
                    f.write(f"  {s}: {c}\n")

        f.write("\n样例键盘模式密码（前10条）:\n")
        for sample in keyboard_pwds[:10]:
            f.write(f"  {sample}\n")

    # === 可视化 ===
    plt.figure(figsize=(6, 4))
    plt.bar(type_counts.keys(), type_counts.values(), color="steelblue")
    plt.title(f"{label} Keyboard Pattern Types")
    plt.xlabel("Pattern Type")
    plt.ylabel("Password Count")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{label}_keyboard_type_ratio.png"))
    plt.close()

    # Top10 sequences overall
    all_seqs = sum(seq_counter.values(), Counter())
    if all_seqs:
        top_items = all_seqs.most_common(10)
        seqs, counts = zip(*top_items)
        plt.figure(figsize=(8, 4))
        plt.bar(seqs, counts, color="darkcyan")
        plt.title(f"{label} Top Keyboard Sequences")
        plt.xlabel("Keyboard Sequence")
        plt.ylabel("Frequency")
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, f"{label}_keyboard_topseqs.png"))
        plt.close()

    print(f"[INFO] 已保存报告与图表到 {OUTPUT_DIR}/")


# ========== 主程序 ==========
def main():
    print("=" * 60)
    print("🔍 键盘密码模式分析 (v3 Enhanced)")
    print("=" * 60)

    pwds1 = load_passwords(FILE1)
    pwds2 = load_passwords(FILE2)

    analyze_keyboard_patterns(pwds1, "Yahoo")
    analyze_keyboard_patterns(pwds2, "CSDN")

    print("\n✅ 分析完成，结果已保存。")


if __name__ == "__main__":
    main()
