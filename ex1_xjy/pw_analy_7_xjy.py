#!/usr/bin/env python3
# pw_user_email_relation.py
# 检测密码与用户名/邮箱之间的关联（包含/相等/反向/邮箱 local-part 等）
# 使用方式：python pw_user_email_relation.py
# 输出：analysis_relation/relation_report.txt, analysis_relation/matches.csv, analysis_relation/relation_pie.png

import re
import os
import csv
import math
from collections import Counter, defaultdict
import matplotlib.pyplot as plt

# ========== 配置（写死路径） ==========
FILE1 = "plaintxt_yahoo.txt"   # 格式: id:username:clear_passwd:passwd -> username at index 1, passwd at last
FILE2 = "www.csdn.net.sql"     # 格式: user # passwd # email -> user,index0 passwd index1 email index2
OUTPUT_DIR = "analysis_relation"
os.makedirs(OUTPUT_DIR, exist_ok=True)
REPORT_PATH = os.path.join(OUTPUT_DIR, "relation_report.txt")
MATCH_CSV = os.path.join(OUTPUT_DIR, "matches.csv")
PIE_PNG = os.path.join(OUTPUT_DIR, "relation_pie.png")

# ========== 工具函数 ==========
def strip_quotes(s):
    if not s:
        return s
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s

def extract_yahoo_fields(line):
    # id:username:clear_passwd:passwd  -> username usually parts[1], password last
    parts = [p.strip() for p in line.split(':')]
    if len(parts) >= 3:
        uid = parts[0] if parts else ""
        username = parts[1] if len(parts) > 1 else ""
        password = parts[-1] if parts else ""
        # username may be an email in some datasets; keep both username and email
        email = username if '@' in username else ""
        return strip_quotes(username), strip_quotes(email), strip_quotes(password)
    return None, None, None

def extract_csdn_fields(line):
    # user # passwd # email  -> parts[0]=user, parts[1]=passwd, parts[2]=email
    parts = [p.strip() for p in line.split('#')]
    if len(parts) >= 3:
        username = parts[0]
        password = parts[1]
        email = parts[2]
        return strip_quotes(username), strip_quotes(email), strip_quotes(password)
    return None, None, None

def normalize_alnum(s):
    """小写并去掉非字母数字字符，用于比较"""
    if s is None:
        return ""
    return re.sub(r'[^a-z0-9]', '', s.lower())

def tokenize_name(s):
    """
    将用户名或 email local-part 拆成 tokens（按非字母数字分隔，或驼峰拆分不处理）
    只保留长度 >=3 的 token
    """
    if not s:
        return []
    s = s.strip()
    # local-part may have dots/underscores/hyphens
    parts = re.split(r'[^A-Za-z0-9]+', s)
    tokens = [p.lower() for p in parts if len(p) >= 3]
    return tokens

# 简单的 leet -> letter 反替换映射（常见）
LEET_MAP = {
    '4': 'a', '@': 'a',
    '0': 'o',
    '1': 'l', '!': 'i',
    '3': 'e',
    '$': 's', '5': 's',
    '7': 't', '+': 't',
    '2': 'z',
    '9': 'g', '6': 'g'
}
def deleet(s):
    """把常见 leet 字替换成对应字母并返回清理后的字符串"""
    if not s:
        return ""
    out = []
    for ch in s:
        if ch in LEET_MAP:
            out.append(LEET_MAP[ch])
        else:
            out.append(ch)
    return ''.join(out).lower()

# ========== 解析并收集记录 ==========
def parse_file_collect(file_path):
    """
    读取文件并返回记录列表，每项为 dict:
    {'username':..., 'email':..., 'password':..., 'src': filename}
    """
    records = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.rstrip('\n\r')
                if not line.strip():
                    continue
                uname, email, pwd = None, None, None
                # try csdn style first (has '#')
                if '#' in line and '@' in line:
                    uname, email, pwd = extract_csdn_fields(line)
                # else try yahoo style (colon-separated)
                elif ':' in line:
                    # check pattern with at least 3 cols
                    uname, email, pwd = extract_yahoo_fields(line)
                # fallback: attempt to heuristically split
                else:
                    # if whitespace separated, maybe "user pwd" or "email pwd"
                    parts = [p.strip() for p in re.split(r'[\t ]+', line) if p.strip() != '']
                    if len(parts) >= 2:
                        # if one part contains @, treat as email
                        if '@' in parts[0]:
                            email = parts[0]
                            pwd = parts[1]
                            uname = parts[0].split('@')[0]
                        else:
                            uname = parts[0]
                            pwd = parts[1]
                    else:
                        # if only one field, treat as password-only record
                        pwd = parts[0]
                if (uname is None and email) and '@' in email:
                    uname = email.split('@')[0]
                # ensure strings
                uname = uname or ""
                email = email or ""
                pwd = pwd or ""
                records.append({'username': uname, 'email': email, 'password': pwd, 'src': os.path.basename(file_path)})
    except Exception as e:
        print(f"[ERROR] read {file_path}: {e}")
    return records

# ========== 关联检测规则 ==========
def detect_relations(record):
    """
    对一条记录检测多种关联，返回 dict flags:
     - exact_username: password == username (normalized)
     - exact_email: password == email (normalized)
     - contains_username: username substring in password (normalized)
     - startswith_username / endswith_username
     - contains_localpart: local-part of email in password
     - contains_token: password contains any token from username/email tokens (>=3 chars)
     - reversed_username: reversed username in password
     - deleet_contains: deleeted(password) contains normalized username (or tokens)
    """
    uname = record.get('username','') or ""
    email = record.get('email','') or ""
    pwd = record.get('password','') or ""
    u_norm = normalize_alnum(uname)
    e_norm = normalize_alnum(email)
    p_norm = normalize_alnum(pwd)
    results = {}
    # exact matches
    results['exact_username'] = (u_norm != "" and p_norm == u_norm)
    results['exact_email'] = (e_norm != "" and p_norm == e_norm)
    # contains / start / end
    results['contains_username'] = (u_norm != "" and u_norm in p_norm)
    results['startswith_username'] = (u_norm != "" and p_norm.startswith(u_norm))
    results['endswith_username'] = (u_norm != "" and p_norm.endswith(u_norm))
    # localpart
    local = ""
    if '@' in email:
        local = email.split('@')[0]
    local_norm = normalize_alnum(local)
    results['contains_localpart'] = (local_norm != "" and local_norm in p_norm)
    # tokens from uname or local
    tokens = tokenize_name(uname) + tokenize_name(local)
    results['contains_token'] = False
    matched_tokens = []
    for t in tokens:
        if t and t in p_norm:
            results['contains_token'] = True
            matched_tokens.append(t)
    results['matched_tokens'] = matched_tokens
    # reversed
    rev_un = u_norm[::-1] if u_norm else ""
    results['reversed_username'] = (rev_un != "" and rev_un in p_norm)
    # deleet check
    p_deleet = normalize_alnum(deleet(pwd))
    results['deleet_contains_username'] = (u_norm != "" and u_norm in p_deleet)
    results['deleet_contains_token'] = False
    matched_deleet_tokens = []
    for t in tokens:
        if t and t in p_deleet:
            results['deleet_contains_token'] = True
            matched_deleet_tokens.append(t)
    results['matched_deleet_tokens'] = matched_deleet_tokens
    # any relation
    # We'll compute overall flag outside
    return results

# ========== 汇总分析 ==========
def analyze_relations(records):
    total = len(records)
    counts = Counter()
    # primary category priority order
    # exact_username > exact_email > contains_username > contains_localpart > contains_token > deleet_contains_username > deleet_contains_token > reversed_username
    priority_keys = ['exact_username', 'exact_email', 'contains_username', 'contains_localpart', 'contains_token', 'deleet_contains_username', 'deleet_contains_token', 'reversed_username']
    matches = []  # list of (record, primary_flag, flags)
    for rec in records:
        flags = detect_relations(rec)
        # determine primary flag
        primary = None
        for k in priority_keys:
            if flags.get(k):
                primary = k
                counts[k] += 1
                break
        if primary is None:
            counts['no_relation'] += 1
        else:
            counts['related'] += 1
        matches.append( (rec, primary, flags) )

    # compute ratios
    related = counts['related']
    no_relation = counts['no_relation']
    related_pct = related / total * 100 if total else 0
    no_relation_pct = no_relation / total * 100 if total else 0

    # detail for each primary type
    detail = {k: counts[k] for k in priority_keys}
    # collect top examples for each primary type
    examples = defaultdict(list)
    for rec, primary, flags in matches:
        key = primary or 'no_relation'
        if len(examples[key]) < 10:
            examples[key].append({'username': rec['username'], 'email': rec['email'], 'password': rec['password'], 'src': rec['src']})

    # produce CSV of all matched records where related
    with open(MATCH_CSV, 'w', encoding='utf-8', newline='') as csvf:
        w = csv.writer(csvf)
        header = ['src','username','email','password','primary_relation','flags','matched_tokens','matched_deleet_tokens']
        w.writerow(header)
        for rec, primary, flags in matches:
            if primary is not None:
                w.writerow([
                    rec['src'],
                    rec['username'],
                    rec['email'],
                    rec['password'],
                    primary,
                    ";".join([k for k,v in flags.items() if v and k not in ('matched_tokens','matched_deleet_tokens')]),
                    ",".join(flags.get('matched_tokens') or []),
                    ",".join(flags.get('matched_deleet_tokens') or [])
                ])

    # write textual report (中文)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write("密码与用户名/邮箱关联分析报告\n")
        f.write("="*50 + "\n")
        f.write(f"数据记录总数: {total}\n")
        f.write(f"检测到相关的密码数: {related} ({related_pct:.2f}%)\n")
        f.write(f"未检测到关联的密码数: {no_relation} ({no_relation_pct:.2f}%)\n\n")
        f.write("按优先级统计（primary relation counts）：\n")
        for k in priority_keys:
            f.write(f"  {k}: {detail.get(k,0)}\n")
        f.write("\n示例（每类最多10条）:\n")
        for k in priority_keys + ['no_relation']:
            f.write(f"\n--- {k} ---\n")
            exs = examples.get(k, [])
            if not exs:
                f.write("  （无示例）\n")
            else:
                for e in exs:
                    f.write(f"  src={e['src']}, username={e['username']}, email={e['email']}, password={e['password']}\n")
        f.write("\n匹配结果的全部记录已保存为 CSV： " + MATCH_CSV + "\n")

    # 绘图：关联 vs 非关联饼图，并保存
    labels = ['related', 'no_relation']
    sizes = [related, no_relation]
    colors = ['#66c2a5', '#fc8d62']
    plt.figure(figsize=(5,5))
    plt.pie(sizes, labels=[f"{l} ({s})" for l,s in zip(labels,sizes)], colors=colors, autopct="%1.1f%%", startangle=90)
    plt.title("Password <-> Username/Email Relation")
    plt.tight_layout()
    plt.savefig(PIE_PNG)
    plt.close()

    # 返回 summary
    return {
        'total': total,
        'related': related,
        'no_relation': no_relation,
        'related_pct': related_pct,
        'no_relation_pct': no_relation_pct,
        'detail': detail,
        'report_path': REPORT_PATH,
        'csv_path': MATCH_CSV,
        'pie_path': PIE_PNG
    }

# ========== 主程序 ==========
def main():
    print("Starting relation analysis...")
    recs1 = parse_file_collect(FILE1)
    recs2 = parse_file_collect(FILE2)
    all_recs = recs1 + recs2
    print(f"Loaded records: {len(all_recs)} (from {FILE1} and {FILE2})")
    summary = analyze_relations(all_recs)
    print("Analysis finished. Summary:")
    print(f" Total records: {summary['total']}")
    print(f" Related: {summary['related']} ({summary['related_pct']:.2f}%)")
    print(f" Not related: {summary['no_relation']} ({summary['no_relation_pct']:.2f}%)")
    print(f" Report: {summary['report_path']}")
    print(f" CSV: {summary['csv_path']}")
    print(f" Pie chart: {summary['pie_path']}")

if __name__ == "__main__":
    main()
