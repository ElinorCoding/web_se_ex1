"""
个人信息关联分析模块 (适配 CSDN 真实格式版)

功能：
  - 检测密码与用户名/邮箱之间的关联
  - 针对 processed_dataset 中的特定格式进行解析
"""
import os
import re
import csv
import json
from collections import Counter, defaultdict

# 输出配置
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "analysis_results")
TASK1_DIR = os.path.dirname(CURRENT_DIR)
REPORT_PATH = os.path.join(OUTPUT_DIR, "personal_info_report.txt")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "personal_info_summary.json")
MATCH_CSV = os.path.join(OUTPUT_DIR, "personal_info_matches.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 数据文件路径
FILE_CSDN = os.path.join(TASK1_DIR, "processed_dataset", "csdn_mail_password_username.txt")
FILE_YAHOO = os.path.join(TASK1_DIR, "processed_dataset", "yahoo_mail_password.txt")


# 工具函数
def normalize_alnum(s):
    """小写并去掉非字母数字字符，用于比较"""
    if s is None: return ""
    return re.sub(r'[^a-z0-9]', '', s.lower())

def tokenize_name(s):
    """将用户名或 email local-part 拆成 tokens，只保留长度 >=3 的 token"""
    if not s: return []
    s = s.strip()
    parts = re.split(r'[^A-Za-z0-9]+', s)
    tokens = [p.lower() for p in parts if len(p) >= 3]
    return tokens

LEET_MAP = {
    '4': 'a', '@': 'a', '0': 'o', '1': 'l', '!': 'i', '3': 'e',
    '$': 's', '5': 's', '7': 't', '+': 't', '2': 'z', '9': 'g', '6': 'g'
}

def deleet(s):
    """把常见 leet 字替换成对应字母"""
    if not s: return ""
    out = []
    for ch in s:
        out.append(LEET_MAP.get(ch, ch))
    return ''.join(out).lower()


# 解析逻辑
def parse_line_current(line, source_type):
    """
    根据源类型解析行数据
    """
    line = line.strip()
    if not line: return None
    
    uname, email, pwd = "", "", ""

    # 1. Yahoo 格式: email:password
    if source_type == 'yahoo':
        # 使用 maxsplit=1 防止密码中包含冒号被切断
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                email = parts[0].strip()
                pwd = parts[1].strip()
                # Yahoo 数据通常没有单独的 username，默认取 email 的前缀
                if '@' in email:
                    uname = email.split('@')[0]
                else:
                    uname = email # 容错

    # 2. CSDN 格式: email:password:username
    elif source_type == 'csdn':
        if ':' in line:
            parts = [p.strip() for p in line.split(':')]
            
            if len(parts) >= 3:
                # 格式: email : password : username
                # 考虑到密码中可能包含冒号，这里取头和尾
                email = parts[0]
                uname = parts[-1]
                pwd = ":".join(parts[1:-1])
            
            elif len(parts) == 2:
                # 只有两列的情况，可能是 email:password
                email = parts[0]
                pwd = parts[1]
                if '@' in email:
                    uname = email.split('@')[0]
                else:
                    # 也有可能是 username:password
                    uname = email
        
        # 兼容旧的 # 分隔符 (以防万一)
        elif '#' in line:
            parts = [p.strip() for p in line.split('#')]
            if len(parts) >= 3:
                # 假设文件名顺序: mail # pass # user
                email, pwd, uname = parts[0], parts[1], parts[2]

    # 后处理：清理引号和空白
    uname = uname.strip('"\'') if uname else ""
    email = email.strip('"\'') if email else ""
    pwd = pwd.strip('"\'') if pwd else ""

    if not pwd: return None

    # 再次确认 email 逻辑
    if not email and '@' in uname:
        email = uname
        uname = email.split('@')[0]
    
    # 针对 Yahoo/CSDN 数据的额外清洗：如果 email 字段里混入了冒号
    if email and ':' in email:
        email = email.split(':')[0]
        # 如果 uname 是从 dirty email 派生的，也需要清洗
        if uname and ':' in uname:
            uname = uname.split(':')[0]

    return {'username': uname, 'email': email, 'password': pwd}


# 关联检测规则
def detect_relations(record):
    uname = record.get('username','') or ""
    email = record.get('email','') or ""
    pwd = record.get('password','') or ""
    
    u_norm = normalize_alnum(uname)
    e_norm = normalize_alnum(email)
    p_norm = normalize_alnum(pwd)
    
    results = {}
    
    # 1. 完全匹配
    results['exact_username'] = (u_norm != "" and p_norm == u_norm)
    results['exact_email'] = (e_norm != "" and p_norm == e_norm)
    
    # 2. 包含关系
    results['contains_username'] = (u_norm != "" and len(u_norm) > 3 and u_norm in p_norm)
    
    # 3. 邮箱 local-part
    local = email.split('@')[0] if '@' in email else ""
    local_norm = normalize_alnum(local)
    results['contains_localpart'] = (local_norm != "" and len(local_norm) > 3 and local_norm in p_norm)
    
    # 4. Token 匹配
    tokens = set(tokenize_name(uname) + tokenize_name(local))
    matched_tokens = [t for t in tokens if t in p_norm]
    results['contains_token'] = bool(matched_tokens)
    results['matched_tokens'] = matched_tokens
    
    # 5. 反向匹配
    rev_un = u_norm[::-1] if u_norm else ""
    results['reversed_username'] = (rev_un != "" and len(rev_un) > 3 and rev_un in p_norm)
    
    # 6. Leet 变换匹配 (包含 Username)
    p_deleet = normalize_alnum(deleet(pwd))
    results['deleet_contains_username'] = (u_norm != "" and len(u_norm) > 3 and u_norm in p_deleet)
    
    # 7. Leet 变换匹配 (包含 Token)
    matched_deleet_tokens = [t for t in tokens if t in p_deleet]
    results['deleet_contains_token'] = bool(matched_deleet_tokens)
    results['matched_deleet_tokens'] = matched_deleet_tokens
    
    return results


# 文件分析函数 
def analyze_file(path: str, source_type: str):
    if not os.path.isfile(path):
        print(f"[WARN] 文件不存在: {path}")
        return []

    print(f"正在分析: {path}")
    records = []
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            rec = parse_line_current(line, source_type)
            if rec: 
                rec['src'] = os.path.basename(path)
                records.append(rec)
    
    return records


# 报告生成
def write_report(all_records):
    print(f"总记录数: {len(all_records)}")
    
    total = len(all_records)
    counts = Counter()
    
    priority_keys = [
        'exact_username', 
        'exact_email', 
        'contains_username', 
        'contains_localpart', 
        'contains_token', 
        'deleet_contains_username', 
        'deleet_contains_token',
        'reversed_username'
    ]
    
    matches = []
    examples = defaultdict(list)
    
    for rec in all_records:
        flags = detect_relations(rec)
        primary = None
        for k in priority_keys:
            if flags.get(k):
                primary = k
                counts[k] += 1
                break
        
        if primary:
            counts['related'] += 1
            matches.append((rec, primary, flags))
            if len(examples[primary]) < 10:
                examples[primary].append(rec)
        else:
            counts['no_relation'] += 1
            if len(examples['no_relation']) < 10:
                examples['no_relation'].append(rec)

    # 生成 CSV
    print(f"正在生成 CSV: {MATCH_CSV}")
    with open(MATCH_CSV, 'w', encoding='utf-8', newline='') as csvf:
        w = csv.writer(csvf)
        w.writerow(['src','username','email','password','primary_relation','matched_tokens','matched_deleet_tokens'])
        for rec, primary, flags in matches:
            w.writerow([
                rec['src'],
                rec['username'],
                rec['email'],
                rec['password'],
                primary,
                ",".join(flags.get('matched_tokens', [])),
                ",".join(flags.get('matched_deleet_tokens', []))
            ])

    # 生成报告
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write("个人信息关联分析报告\n====================\n\n")
        f.write(f"总记录数: {total}\n")
        f.write(f"存在关联的密码: {counts['related']} ({counts['related']/total*100:.2f}%)\n")
        f.write(f"无关联密码: {counts['no_relation']} ({counts['no_relation']/total*100:.2f}%)\n\n")
        f.write("关联类型分布 (按优先级):\n")
        for k in priority_keys:
            f.write(f"  {k}: {counts[k]}\n")
            
        f.write("\n示例（每类最多10条）:\n")
        for k in priority_keys:
            if k in examples and examples[k]:
                f.write(f"\n--- {k} ---\n")
                for rec in examples[k]:
                    f.write(f"  src={rec['src']}, user={rec['username']}, email={rec['email']}, pass={rec['password']}\n")
        
        if examples['no_relation']:
            f.write(f"\n--- no_relation ---\n")
            for rec in examples['no_relation']:
                f.write(f"  src={rec['src']}, user={rec['username']}, email={rec['email']}, pass={rec['password']}\n")

    # 生成 JSON
    summary = {
        'total': total,
        'related': counts['related'],
        'no_relation': counts['no_relation'],
        'detail': {k: counts[k] for k in priority_keys}
    }
    with open(SUMMARY_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("个人信息关联分析")
    print("=" * 60)

    all_records = []
    
    # 明确指定类型进行解析
    if os.path.isfile(FILE_YAHOO):
        records = analyze_file(FILE_YAHOO, 'yahoo')
        all_records.extend(records)

    if os.path.isfile(FILE_CSDN):
        records = analyze_file(FILE_CSDN, 'csdn')
        all_records.extend(records)

    if not all_records:
        print("[ERROR] 未加载到任何数据")
        return

    write_report(all_records)
    print(f"分析完成，报告: {REPORT_PATH}")
    print(f"汇总: {SUMMARY_JSON}")

if __name__ == '__main__':
    main()