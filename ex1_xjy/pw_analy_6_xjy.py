import math
import re
import matplotlib.pyplot as plt
from collections import Counter

# ========== 全局参数 ==========
FILE1 = "plaintxt_yahoo.txt"   # Yahoo文件
FILE2 = "www.csdn.net.sql"     # CSDN文件
REPORT_FILE = "report_entropy.txt"

# ========== 工具函数 ==========

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
    """根据文件名解析密码"""
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
        print(f"[ERROR] 无法读取 {filename}: {e}")
    return passwords

# ========== 信息熵计算函数 ==========
def shannon_entropy(password):
    """计算一个密码的香农熵 Shannon Entropy"""
    if not password:
        return 0
    counter = Counter(password)
    length = len(password)
    probs = [count / length for count in counter.values()]
    entropy = -sum(p * math.log2(p) for p in probs)
    return entropy

# ========== 熵分析 ==========
def analyze_entropy(passwords, label):
    entropies = [shannon_entropy(p) for p in passwords if p]

    if not entropies:
        print(f"[WARN] {label} 无可计算的密码数据。\n")
        return

    avg_entropy = sum(entropies) / len(entropies)
    var_entropy = sum((e - avg_entropy) ** 2 for e in entropies) / len(entropies)
    std_entropy = math.sqrt(var_entropy)

    # 分类分布
    low = len([e for e in entropies if e < 2])
    mid = len([e for e in entropies if 2 <= e < 4])
    high = len([e for e in entropies if e >= 4])

    total = len(entropies)
    low_ratio, mid_ratio, high_ratio = low / total * 100, mid / total * 100, high / total * 100

    # Top10 熵最高密码
    top10 = sorted(
        zip(passwords, entropies), key=lambda x: x[1], reverse=True
    )[:10]

    # ========== 打印结果 ==========
    print(f"========== 熵分析结果：{label} ==========")
    print(f"平均熵值: {avg_entropy:.3f} bits/char")
    print(f"标准差: {std_entropy:.3f}")
    print(f"低熵(0~2): {low} ({low_ratio:.2f}%)")
    print(f"中熵(2~4): {mid} ({mid_ratio:.2f}%)")
    print(f"高熵(>4): {high} ({high_ratio:.2f}%)")
    print("\nTop 10 熵最高密码:")
    for p, e in top10:
        print(f"  {p} -> {e:.3f}")
    print()

    # ========== 写入报告 ==========
    with open(REPORT_FILE, "a", encoding="utf-8") as f:
        f.write(f"========== 熵分析结果：{label} ==========\n")
        f.write(f"平均熵值: {avg_entropy:.3f} bits/char\n")
        f.write(f"标准差: {std_entropy:.3f}\n")
        f.write(f"低熵(0~2): {low} ({low_ratio:.2f}%)\n")
        f.write(f"中熵(2~4): {mid} ({mid_ratio:.2f}%)\n")
        f.write(f"高熵(>4): {high} ({high_ratio:.2f}%)\n\n")
        f.write("Top 10 熵最高密码:\n")
        for p, e in top10:
            f.write(f"  {p} -> {e:.3f}\n")
        f.write("\n")

    # ========== 可视化 ==========
    plt.figure(figsize=(8, 4))
    plt.hist(entropies, bins=30, color="#69b3a2", edgecolor="black", alpha=0.8)
    plt.title(f"Entropy Distribution - {label}")
    plt.xlabel("Entropy (bits/char)")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(f"entropy_distribution_{label}.png")
    plt.close()

    plt.figure(figsize=(5, 5))
    plt.pie(
        [low, mid, high],
        labels=["Low (0-2)", "Medium (2-4)", "High (>4)"],
        autopct="%1.1f%%",
        colors=["#ff9999", "#ffcc99", "#99ff99"],
    )
    plt.title(f"Entropy Level Ratio - {label}")
    plt.savefig(f"entropy_ratio_{label}.png")
    plt.close()


# ========== 主程序入口 ==========
def main():
    print("=" * 60)
    print("🧩 密码语义复杂度分析 (Shannon Entropy)")
    print("=" * 60)
    print(f"文件1: {FILE1}")
    print(f"文件2: {FILE2}")
    print("=" * 60, "\n")

    pwds1 = load_passwords(FILE1)
    pwds2 = load_passwords(FILE2)

    # 清空报告文件
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("🔍 密码语义复杂度分析报告（基于信息熵）\n")
        f.write("说明：熵越高表示随机性越强，密码越安全。\n\n")

    analyze_entropy(pwds1, "Yahoo")
    analyze_entropy(pwds2, "CSDN")

    print(f"✅ 分析完成，结果已保存至 {REPORT_FILE}")
    print(f"✅ 图表文件已生成：entropy_distribution_*.png, entropy_ratio_*.png")


if __name__ == "__main__":
    main()
