"""
英文单词分析模块 (整合自 pw_analy5_wsy.py)

功能：
  - 使用 wordfreq 库识别常见英文单词
  - 贪心算法拆分密码中的单词片段
  - 过滤噪声 (键盘序列、常见姓氏等)
  - 统计单词频次和大小写模式 (lower, upper, capitalized, mixed)
  - 生成 JSON 汇总供 visualize_results.py 使用
"""
import os
import re
import json
from collections import Counter
from wordfreq import zipf_frequency

# 输出配置
TOPK = 10

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "analysis_results")
TASK1_DIR = os.path.dirname(CURRENT_DIR)
REPORT_PATH = os.path.join(OUTPUT_DIR, "english_word_report.txt")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "english_word_summary.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 数据文件
FILE_CSDN = os.path.join(TASK1_DIR, "processed_dataset", "csdn_mail_password_username.txt")
FILE_YAHOO = os.path.join(TASK1_DIR, "processed_dataset", "yahoo_mail_password.txt")
COUNT_MODE = 'unique_per_password'  # 每个密码只统计一次单词

# 噪声过滤机制
COMMON_NON_WORDS = [
    r'^[a-z]{1}$',                      # 过短字母串
    r'^(qwe|asd|zxc|poi|lkj|mnb|qaz|wsx|edc|abc)+$',  # 键盘序列
    r'^(aaa|bbb|ccc|ddd|eee|fff)+$',      # 重复字母
]

BLACK_SURNAMES = {
    'wang', 'li', 'zhang', 'liu', 'chen', 'yang', 'zhao', 'wu', 'zhou', 'xu',
    'sun', 'hu', 'zhu', 'gao', 'lin', 'he', 'guo', 'ma', 'lu', 'dong', 'xie',
    'song', 'shi', 'tang', 'feng', 'yu', 'cai', 'pan', 'deng', 'xiao', 'tian',
    'liang', 'wei', 'jiang', 'han', 'fan', 'peng', 'yuan', 'cao', 'fu', 'ren',
    'fang', 'jing', 'cheng', 'qian', 'mo', 'qiu', 'long', 'chang', 'com', 'ian',
    'qiao', 'mei', 'hua', 'jin', 'tao', 'qi', 'wen', 'yan', 'bao', 'du', 'bin',
    'ye', 'su', 'pei', 'luo', 'shan', 'hou', 'qin', 'ruan', 'tan', 'lu', 'hong',
    'min', 'dan', 'ron', 'juan', 'don'
}

def is_noise_word(word):
    if word in BLACK_SURNAMES:
        return True
    for pat in COMMON_NON_WORDS:
        if re.fullmatch(pat, word):
            return True
    return False

def is_common_english_word(word, min_freq=3.0):
    """用 wordfreq 判断是否为常见英文单词"""
    return zipf_frequency(word, 'en') >= min_freq


# 核心算法
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

        """
        尝试在原始片段中定位单词
        注意：这里简化处理，假设贪心拆分顺序与原始字符对应
        实际情况中，如果拆分跳过了字符，索引可能对不上，但对于连续单词通常没问题
         """
        for w_lower in splits:
            
            if idx + len(w_lower) > len(seg):
                break
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
            validated.append(w_lower) 

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


# 文件分析函数
def analyze_file(path: str, label: str, min_freq_all=3.0):
    if not os.path.isfile(path):
        print(f"[WARN] 文件不存在: {path}")
        return None
    
    print(f"正在分析: {path}")

    all_words = []
    all_cases = []
    word_in_pwd_count = 0
    total_pwds = 0
    
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
            total_pwds += 1

            words, case_patterns = extract_valid_words(password, min_freq=min_freq_all)
            if words:
                word_in_pwd_count += 1
                all_words.extend(words)
                all_cases.extend(case_patterns)

    # 统计
    word_counter = Counter(all_words)
    case_counter = Counter(all_cases)
    
    return {
        'label': label,
        'total': total_pwds,
        'word_pwd_count': word_in_pwd_count,
        'ratio': (word_in_pwd_count / total_pwds * 100) if total_pwds else 0,
        'word_counter': word_counter,
        'case_counter': case_counter
    }


# 报告生成
def write_report(results, min_freq_top=3.5):
    # 1. 文本报告
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write("英文单词分析报告\n====================\n\n")
        
        for r in results:
            f.write(f"========= {r['label']} 英文单词统计 =========\n")
            f.write(f"密码总数: {r['total']}\n")
            f.write(f"包含英文单词的密码数: {r['word_pwd_count']} ({r['ratio']:.2f}%)\n")
            
            # 筛选高频词 (排除过于简单的词)
            high_freq_words = [w for w in r['word_counter'] if is_common_english_word(w, min_freq=min_freq_top)]
            # 按频次排序
            top_words = sorted(((w, r['word_counter'][w]) for w in high_freq_words), key=lambda x: x[1], reverse=True)[:TOPK]
            
            f.write(f"\nTop-{TOPK} 高频英文单词 (min_freq={min_freq_top}):\n")
            for w, c in top_words:
                f.write(f"{w}: {c}\n")
                
            f.write("\n大小写模式分布:\n")
            for case, count in r['case_counter'].most_common():
                f.write(f"{case}: {count}\n")
            f.write("\n")

    # 2. JSON 汇总
    summary = {'datasets': []}
    for r in results:
        # 同样筛选高频词用于可视化
        high_freq_words = [w for w in r['word_counter'] if is_common_english_word(w, min_freq=min_freq_top)]
        top_words = sorted(((w, r['word_counter'][w]) for w in high_freq_words), key=lambda x: x[1], reverse=True)[:TOPK]
        
        summary['datasets'].append({
            'label': r['label'],
            'top_words': top_words,
            'case_dist': r['case_counter'].most_common()
        })
    
    with open(SUMMARY_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    print("="*60 + "\n英文单词分析\n" + "="*60)
    results = []
    # 分析 Yahoo
    if os.path.isfile(FILE_YAHOO):
        res = analyze_file(FILE_YAHOO, 'Yahoo', min_freq_all=3.0)
        if res: results.append(res)

    # 分析 CSDN (下面的min_freq_top建议略高一些)
    if os.path.isfile(FILE_CSDN):
        res = analyze_file(FILE_CSDN, 'CSDN', min_freq_all=3.0)
        if res: results.append(res)


    write_report(results, min_freq_top=3.5)
    print(f"分析完成，报告: {REPORT_PATH}")
    print(f"汇总: {SUMMARY_JSON}")

if __name__ == '__main__':
    main()