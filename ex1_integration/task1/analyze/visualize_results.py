import os
import json
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt

# 字体设置（尽量兼容中文展示）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'Heiti TC']
plt.rcParams['axes.unicode_minus'] = False


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSIFY_DIR = os.path.join(ROOT, 'classify', 'classify_result')
ANALYSIS_DIR = os.path.join(ROOT, 'analyze', 'analysis_results')

# 主输出目录
OUT_DIR = os.path.join(ROOT, 'generated_graphs')

# 子输出目录
OUT_CLASSIFY = os.path.join(OUT_DIR, 'classify')
OUT_DICT = os.path.join(OUT_DIR, 'dictionary_order')
OUT_KEYBOARD = os.path.join(OUT_DIR, 'keyboard')
OUT_COMPOSITION = os.path.join(OUT_DIR, 'composition')
OUT_DATE = os.path.join(OUT_DIR, 'date')
OUT_ENGLISH = os.path.join(OUT_DIR, 'english')
OUT_ENTROPY = os.path.join(OUT_DIR, 'entropy')
OUT_PERSONAL = os.path.join(OUT_DIR, 'personal_info')

# 创建所有目录
for d in [OUT_DIR, OUT_CLASSIFY, OUT_DICT, OUT_KEYBOARD, OUT_COMPOSITION, OUT_DATE, OUT_ENGLISH, OUT_ENTROPY, OUT_PERSONAL]:
    os.makedirs(d, exist_ok=True)

def _save_bar(items: List[Tuple[str, int]], title: str, xlabel: str, ylabel: str, path: str, rotate: int = 45):
    if not items:
        return
    labels = [str(k) for k, _ in items]
    values = [v for _, v in items]
    plt.figure(figsize=(10, 5))
    plt.bar(labels, values, color='steelblue')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if rotate:
        plt.xticks(rotation=rotate)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


essential_colors = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
    '#edc949', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab',
]

COLORS_PASTEL = ['#fdbf6f', '#fb9a99', '#b2df8a', '#a6cee3', '#cab2d6', '#ffff99']

# 英文分类名 -> 中文映射
CATEGORY_CN = {
    'numeric_only': '纯数字',
    'date_like': '日期',
    'dictionary_order': '字典序连续',
    'keyboard_pattern': '键盘模式',
    'english_word': '英文单词',
    'pinyin': '拼音',
    'repeated_chars': '重复字符',
    'partial_like_user_or_mail': '与用户/邮箱部分相似',
    'same_as_user_or_mail': '与用户/邮箱完全相同',
    'other': '其他',
}

def _to_cn(name: str) -> str:
    return CATEGORY_CN.get(name, name)

def _combo_to_cn(combo_key: str) -> str:
    parts = combo_key.split('+')
    return '+'.join(_to_cn(p) for p in parts)

def _save_pie(name_to_value: Dict[str, int], title: str, path: str, max_slices: int = 10, colors=None):
    if not name_to_value:
        return
    items = sorted(name_to_value.items(), key=lambda x: x[1], reverse=True)
    top = items[:max_slices]
    rest = sum(v for _, v in items[max_slices:])
    if rest:
        top.append(('其他', rest))
        
    labels = [k for k, _ in top]
    sizes = [v for _, v in top]
    
    # 如果未指定颜色，使用默认 Pastel 色盘循环
    if not colors:
        # 确保 COLORS_PASTEL 已定义，如果没有定义，使用默认颜色
        local_colors = COLORS_PASTEL if 'COLORS_PASTEL' in globals() else None
        if local_colors:
            colors = (local_colors * ((len(labels) // len(local_colors)) + 1))[:len(labels)]
    
    plt.figure(figsize=(7, 7))
    
    # 绘制饼图
    wedges, texts, autotexts = plt.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                       startangle=140, colors=colors, 
                                       pctdistance=0.85, labeldistance=1.1)
    
    # 优化字体显示
    plt.setp(texts, size=10)
    plt.setp(autotexts, size=10, weight="bold", color="black")
    
    plt.title(title, pad=15)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


# ========== 可视化 classify 结果 ==========

def visualize_classify(dataset: str):
    dataset_dir = os.path.join(CLASSIFY_DIR, dataset)
    summary_path = os.path.join(dataset_dir, 'summary.json')
    if not os.path.isfile(summary_path):
        print(f"[WARN] 未找到 {summary_path}")
        return
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    single_counts: Dict[str, int] = data.get('single_counts') or data.get('counts') or {}
    order: List[str] = data.get('order') or list(single_counts.keys())
    combo_counts: Dict[str, int] = data.get('combo_counts') or {}

    # 饼状图（口令类型占比）
    pie_out = os.path.join(OUT_CLASSIFY, f'classify_{dataset}_category_pie.png')
    # 转换为中文标签供饼图使用（保留数值结构）
    single_counts_cn = { _to_cn(k): v for k, v in single_counts.items() }
    _save_pie(single_counts_cn, f'{dataset} 口令类型占比（单类统计）', pie_out)

    # 柱状图（各类口令频次）
    items = [(_to_cn(k), single_counts.get(k, 0)) for k in order]
    bar_out = os.path.join(OUT_CLASSIFY, f'classify_{dataset}_category_bar.png')
    _save_bar(items, f'{dataset} 各类口令频次', '类别', '数量', bar_out, rotate=45)

    # 复合特征 Top K 柱状图
    if combo_counts:
        top_combo_raw = sorted(combo_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        # 转中文组合名
        top_combo = [(_combo_to_cn(k), v) for k, v in top_combo_raw]
        combo_out = os.path.join(OUT_CLASSIFY, f'classify_{dataset}_combo_top.png')
        _save_bar(top_combo, f'{dataset} 复合特征组合 Top-15', '组合（+连接）', '数量', combo_out, rotate=60)


# ========== 可视化 字典序 分析 ==========

def visualize_dictionary_order():
    summary_path = os.path.join(ANALYSIS_DIR, 'dictionary_order_summary.json')
    if not os.path.isfile(summary_path):
        print(f"[WARN] 未找到 {summary_path}")
        return
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    datasets = data.get('datasets', [])
    for item in datasets:
        label = item.get('label', 'dataset')
        top_runs = item.get('top_runs', [])
        top_lengths = item.get('top_lengths', [])
        top_start_chars = item.get('top_start_chars', [])

        runs_out = os.path.join(OUT_DICT, f'{label}_top_runs.png')
        _save_bar(top_runs, f'{label} 字典序连续序列 Top-{len(top_runs)}', '序列', '次数', runs_out, rotate=60)

        lens_out = os.path.join(OUT_DICT, f'{label}_lengths.png')
        _save_bar(top_lengths, f'{label} 连续段长度分布 Top-{len(top_lengths)}', '长度', '次数', lens_out, rotate=0)

        start_out = os.path.join(OUT_DICT, f'{label}_start_chars.png')
        _save_bar(top_start_chars, f'{label} 连续段起始字符分布 Top-{len(top_start_chars)}', '起始字符', '次数', start_out, rotate=0)


# ========== 可视化 键盘模式 分析 ==========

def visualize_keyboard():
    summary_path = os.path.join(ANALYSIS_DIR, 'keyboard_summary.json')
    if not os.path.isfile(summary_path):
        print(f"[WARN] 未找到 {summary_path}")
        return
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    datasets = data.get('datasets', [])
    for item in datasets:
        label = item.get('label', 'dataset')

        # 1. 类型分布柱状图
        type_dist = item.get('type_distribution', {})
        if type_dist:
            type_items = [(k, v) for k, v in type_dist.items()]
            type_out = os.path.join(OUT_KEYBOARD, f'{label}_type_ratio.png')
            _save_bar(type_items, f'{label} Keyboard Pattern Types', 'Pattern Type', 'Password Count', type_out, rotate=0)
        
        # 2. Top 序列柱状图
        top_seqs = item.get('top_sequences', [])
        if top_seqs:
            seqs_out = os.path.join(OUT_KEYBOARD, f'{label}_topseqs.png')
            _save_bar(top_seqs, f'{label} Top Keyboard Sequences', 'Keyboard Sequence', 'Frequency', seqs_out, rotate=45)


# ========== 可视化 密码构成 分析 ==========

def visualize_composition():
    """
    可视化密码构成与结构分析结果
    """
    summary_path = os.path.join(ANALYSIS_DIR, 'composition_summary.json')
    if not os.path.isfile(summary_path):
        print(f"[WARN] 未找到 {summary_path}")
        return
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    datasets = data.get('datasets', [])
    for item in datasets:
        label = item.get('label', 'dataset')
        
        # 1. 密码长度分布直方图
        length_dist = item.get('length_distribution', [])
        if length_dist:
            lengths, counts = zip(*length_dist)
            plt.figure(figsize=(8, 4))
            plt.bar(lengths, counts, color='steelblue', edgecolor='black')
            plt.title(f'{label} Password Length Distribution')
            plt.xlabel('Password Length')
            plt.ylabel('Count')
            plt.grid(axis='y', alpha=0.3)
            plt.tight_layout()
            plt.savefig(os.path.join(OUT_COMPOSITION, f'{label}_length_distribution.png'))
            plt.close()
        
        # 2. 字符类型占比饼图
        type_dist = item.get('type_distribution', {})
        if type_dist:
            labels = []
            sizes = []
            for type_name, info in type_dist.items():
                labels.append(f"{type_name}\n({info['ratio']:.1f}%)")
                sizes.append(info['count'])
            
            plt.figure(figsize=(6, 6))
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            plt.title(f'{label} Character Type Distribution')
            plt.tight_layout()
            plt.savefig(os.path.join(OUT_COMPOSITION, f'{label}_char_types.png'))
            plt.close()
        
        # 3. Top 结构模式柱状图
        top_patterns = item.get('top_patterns', [])
        if top_patterns:
            patterns_out = os.path.join(OUT_COMPOSITION, f'{label}_pattern_top{len(top_patterns)}.png')
            _save_bar(top_patterns, f'{label} Top-{len(top_patterns)} Password Patterns', 'Pattern', 'Count', patterns_out, rotate=45)
        

# ========== 可视化 日期分析 结果 ==========

def visualize_date():
    """
    可视化日期模式分析结果
    """
    summary_path = os.path.join(ANALYSIS_DIR, 'date_summary.json')
    if not os.path.isfile(summary_path):
        print(f"[WARN] 未找到 {summary_path}")
        return
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for item in data.get('datasets', []):
        label = item.get('label', 'dataset')
        
        # 1. 年份分布 
        year_dist = item.get('year_dist', [])
        if year_dist:
            # 图表横轴按大小排列
            year_dist_sorted = sorted(year_dist, key=lambda x: x[1], reverse=True)
            out_path = os.path.join(OUT_DATE, f'{label}_year_distribution.png')
            _save_bar(year_dist_sorted, f'{label}_year_distribution Top-{len(year_dist)}', None, 'count', out_path, rotate=45)
        
        # 2. 日期格式分布 
        fmt_dist = item.get('format_dist', [])
        if fmt_dist:
            out_path = os.path.join(OUT_DATE, f'{label}_format_distribution.png')
            _save_bar(fmt_dist, f'{label}_format_distribution', None, 'count', out_path, rotate=0)

        # 3. 月日分布 
        md_dist = item.get('monthday_dist', [])
        if md_dist:
            out_path = os.path.join(OUT_DATE, f'{label}_monthday_distribution.png')
            _save_bar(md_dist, f'{label}_monthday_distribution Top-{len(md_dist)}', None, 'count', out_path, rotate=45)

        # 4. 结构模式分布
        struct_dist = item.get('structure_dist', [])
        if struct_dist:
            out_path = os.path.join(OUT_DATE, f'{label}_structure_distribution.png')
            _save_bar(struct_dist, f'{label}_structure_distribution Top-{len(struct_dist)}', None, 'count', out_path, rotate=45)


# ========== 可视化 英文单词分析 结果 ==========

def visualize_english():
    """
    可视化英文单词分析结果
    """
    summary_path = os.path.join(ANALYSIS_DIR, 'english_word_summary.json')
    if not os.path.isfile(summary_path):
        print(f"[WARN] 未找到 {summary_path}")
        return

    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for item in data.get('datasets', []):
        label = item.get('label', 'dataset')
        
        # 1. Top 单词柱状图
        top_words = item.get('top_words', [])
        if top_words:
            out_path = os.path.join(OUT_ENGLISH, f'{label}_top_words.png')
            _save_bar(top_words, f'{label}_Top-{len(top_words)}_Word', None, 'count', out_path, rotate=45)
            
        # 2. 大小写模式饼图
        case_dist = item.get('case_dist', [])
        if case_dist:
            # 转换为字典供 _save_pie 使用
            case_dict = {k: v for k, v in case_dist}
            out_path = os.path.join(OUT_ENGLISH, f'{label}_case_patterns_pie.png')
            _save_pie(case_dict, f'{label}_Word_Case_Patterns_Distribution', out_path)
            
            # 也可以生成柱状图
            out_bar_path = os.path.join(OUT_ENGLISH, f'{label}_case_patterns_bar.png')
            _save_bar(case_dist, f'{label}_Word_Case_Patterns_Distribution', None, 'count', out_bar_path, rotate=0)


# ========== 可视化 熵分析 结果 ==========

def visualize_entropy():
    summary_path = os.path.join(ANALYSIS_DIR, 'entropy_summary.json')
    if not os.path.isfile(summary_path): return
    with open(summary_path, 'r', encoding='utf-8') as f: data = json.load(f)
    
    for item in data.get('datasets', []):
        label = item.get('label', 'dataset')
        
        # 1. 熵值分布直方图
        hist_data = item.get('histogram', [])
        if hist_data:
            out_path = os.path.join(OUT_ENTROPY, f'{label}_entropy_distribution.png')
            
            counts = [v for _, v in hist_data]
            
            # 自动判断精度
            if len(counts) > 30: # 高精度模式 (0.1)
                bin_width = 0.1
                line_width = 0.3  # 线条更细，避免黑色边框盖住颜色
                x_limit = 5.0     # 熵值通常不会超过 5，聚焦显示
            else: # 低精度模式 (0.5)
                bin_width = 0.5
                line_width = 0.8
                x_limit = 8.0

            num_bins = len(counts)
            x_positions = [i * bin_width for i in range(num_bins)]
            
            plt.figure(figsize=(12, 6)) # 加宽画布
            
            # 绘制
            plt.bar(x_positions, counts, width=bin_width, align='edge', 
                    color='#80cdc1', edgecolor='black', linewidth=line_width, alpha=0.9)
            
            plt.title(f'Entropy Distribution - {label}', pad=15)
            plt.xlabel('Entropy (bits/char)')
            plt.ylabel('Count')
            
            # 优化 X 轴刻度：每 0.5 显示一个刻度，但只标记整数
            # 这样网格线会更密一些，便于读数
            major_ticks = range(0, int(x_limit) + 2)
            plt.xticks(major_ticks)
            plt.xlim(0, x_limit)
            
            # 关键：Y轴使用科学计数法，防止数字太长
            plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
            
            plt.grid(axis='y', linestyle='--', alpha=0.4)
            plt.tight_layout()
            plt.savefig(out_path, dpi=200) # 提高分辨率
            plt.close()


# ========== 可视化 个人信息关联分析 结果 ==========

def visualize_personal_info():
    """
    可视化个人信息关联分析结果
    """
    summary_path = os.path.join(ANALYSIS_DIR, 'personal_info_summary.json')
    if not os.path.isfile(summary_path):
        print(f"[WARN] 未找到 {summary_path}")
        return

    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 1. 关联 vs 无关联 概览饼图
    related = data.get('related', 0)
    no_relation = data.get('no_relation', 0)
    
    if related + no_relation > 0:
        pie_data = {'Related': related, 'No Relation': no_relation}
        out_path = os.path.join(OUT_PERSONAL, 'relation_overview_pie.png')
        # 使用附件风格配色：Related(绿色), No Relation(橙色)
        _save_pie(pie_data, 'Password-User Info Relation Overview', out_path, 
                  colors=['#66c2a5', '#fc8d62'])

    # 2. 关联类型详细分布 柱状图
    detail = data.get('detail', {})
    if detail:
        # 按数量倒序排列
        sorted_detail = sorted(detail.items(), key=lambda x: x[1], reverse=True)
        out_path = os.path.join(OUT_PERSONAL, 'relation_types_bar.png')
        
        # === 修改：移除 color 参数 ===
        _save_bar(sorted_detail, 'Relation Types Distribution', 'Relation Type', 'Count', 
                  out_path, rotate=45)



def main():
    # 针对 classify 的 csdn/yahoo 生成图表
    for ds in ['csdn', 'yahoo']:
        visualize_classify(ds)
    # 针对字典序分析生成图表
    visualize_dictionary_order()
    # 针对键盘模式分析生成图表
    visualize_keyboard()
    # 针对密码构成分析生成图表
    visualize_composition()
    # 针对日期模式分析生成图表
    visualize_date()
    # 针对英文单词分析生成图表
    visualize_english()
    # 针对熵分析生成图表
    visualize_entropy()
    # 针对个人信息关联分析生成图表
    visualize_personal_info()
    print(f"图表已输出至: {OUT_DIR}")

if __name__ == '__main__':
    main()
