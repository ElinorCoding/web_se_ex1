import os
import json
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt

# 字体设置（尽量兼容中文展示）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'Heiti TC']
plt.rcParams['axes.unicode_minus'] = False

# 目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSIFY_DIR = os.path.join(ROOT, 'classify', 'classify_result')
DICT_DIR = os.path.join(ROOT, '..', 'analysis_results_dictionary_order')
OUT_DIR = os.path.join(ROOT, 'generated_graphs')
os.makedirs(OUT_DIR, exist_ok=True)


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


def _save_pie(name_to_value: Dict[str, int], title: str, path: str, max_slices: int = 10):
    if not name_to_value:
        return
    items = sorted(name_to_value.items(), key=lambda x: x[1], reverse=True)
    top = items[:max_slices]
    rest = sum(v for _, v in items[max_slices:])
    if rest:
        top.append(('其他', rest))
    labels = [k for k, _ in top]
    sizes = [v for _, v in top]
    colors = (essential_colors * ((len(labels) // len(essential_colors)) + 1))[:len(labels)]
    plt.figure(figsize=(7, 7))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path)
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
    pie_out = os.path.join(OUT_DIR, f'classify_{dataset}_category_pie.png')
    # 转换为中文标签供饼图使用（保留数值结构）
    single_counts_cn = { _to_cn(k): v for k, v in single_counts.items() }
    _save_pie(single_counts_cn, f'{dataset} 口令类型占比（单类统计）', pie_out)

    # 柱状图（各类口令频次）
    items = [(_to_cn(k), single_counts.get(k, 0)) for k in order]
    bar_out = os.path.join(OUT_DIR, f'classify_{dataset}_category_bar.png')
    _save_bar(items, f'{dataset} 各类口令频次', '类别', '数量', bar_out, rotate=45)

    # 复合特征 Top K 柱状图
    if combo_counts:
        top_combo_raw = sorted(combo_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        # 转中文组合名
        top_combo = [(_combo_to_cn(k), v) for k, v in top_combo_raw]
        combo_out = os.path.join(OUT_DIR, f'classify_{dataset}_combo_top.png')
        _save_bar(top_combo, f'{dataset} 复合特征组合 Top-15', '组合（+连接）', '数量', combo_out, rotate=60)


# ========== 可视化 字典序 分析 ==========

def visualize_dictionary_order():
    summary_path = os.path.join(DICT_DIR, 'summary.json')
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

        runs_out = os.path.join(OUT_DIR, f'dict_{label}_top_runs.png')
        _save_bar(top_runs, f'{label} 字典序连续序列 Top-{len(top_runs)}', '序列', '次数', runs_out, rotate=60)

        lens_out = os.path.join(OUT_DIR, f'dict_{label}_lengths.png')
        _save_bar(top_lengths, f'{label} 连续段长度分布 Top-{len(top_lengths)}', '长度', '次数', lens_out, rotate=0)

        start_out = os.path.join(OUT_DIR, f'dict_{label}_start_chars.png')
        _save_bar(top_start_chars, f'{label} 连续段起始字符分布 Top-{len(top_start_chars)}', '起始字符', '次数', start_out, rotate=0)


def main():
    # 针对 classify 的 csdn/yahoo 生成图表
    for ds in ['csdn', 'yahoo']:
        visualize_classify(ds)
    # 针对字典序分析生成图表
    visualize_dictionary_order()
    print(f"✅ 图表已输出至: {OUT_DIR}")


if __name__ == '__main__':
    main()
