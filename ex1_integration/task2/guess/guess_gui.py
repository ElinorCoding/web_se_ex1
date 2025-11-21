"""GUI 前端: 交互式演示 `guess.py` 口令候选生成与评估/模拟

依赖: 仅标准库 (tkinter, threading)

功能:
 1. 数据集选择 (csdn / yahoo / auto)
 2. 模式选择:
    - Generate: 只生成候选并显示前若干条, 可保存全部到文件
    - Evaluate: 对整个数据集评估命中率
    - Simulate: 针对指定/文件/随机抽取目标集合模拟猜解过程, 输出指标
 3. 参数: budget, delay-ms(模拟), random-targets, 保存路径(out/metrics-out)
 4. 目标: 文本框输入多个(换行或逗号), 可选择文件加载, 可随机抽取
 5. 实时日志输出与停止按钮

使用示例 (PowerShell):
  python .\code\guess\guess_gui.py

注意: GUI 调用同目录下的 `guess.py` 中函数, 不重复业务逻辑.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
import json
import random
import importlib.util
import sys

# 动态加载同目录下的 guess.py 以避免包结构限制
GUESS_PATH = os.path.join(os.path.dirname(__file__), 'guess.py')
spec = importlib.util.spec_from_file_location('guess', GUESS_PATH)
guess_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guess_mod)

"""本 GUI 已切换为纯静态模式：不再基于数据集统计生成候选，数据集仅在评估或模拟时用作目标集合来源。"""
# 通过模块引用函数/常量（仅保留静态生成器）
load_dataset = guess_mod.load_dataset
gen_english = guess_mod.gen_english
gen_dates = guess_mod.gen_dates
gen_keyboard_and_repeats = guess_mod.gen_keyboard_and_repeats
interleave_generators = guess_mod.interleave_generators
parallel_interleave_generators = getattr(guess_mod, 'parallel_interleave_generators', None)
evaluate_targets = guess_mod.evaluate_targets
evaluate_with_metrics = getattr(guess_mod, 'evaluate_with_metrics', None)
COMMON_SUFFIX = guess_mod.COMMON_SUFFIX
gen_builtin_high_freq = getattr(guess_mod, 'gen_builtin_high_freq', None)
gen_numeric_exhaustive_upto7 = getattr(guess_mod, 'gen_numeric_exhaustive_upto7', None)
gen_english_wordfreq = getattr(guess_mod, 'gen_english_wordfreq', None)
gen_dates_with_affixes = getattr(guess_mod, 'gen_dates_with_affixes', None)
load_pinyin_surnames = getattr(guess_mod, 'load_pinyin_surnames', None)
gen_pinyin_surnames = getattr(guess_mod, 'gen_pinyin_surnames', None)
gen_simple_alpha_num_combos = getattr(guess_mod, 'gen_simple_alpha_num_combos', None)
HF_ENGLISH = getattr(guess_mod, 'HF_ENGLISH', [])
HF_YEARS = getattr(guess_mod, 'HF_YEARS', [])
HF_KEYBOARD = getattr(guess_mod, 'HF_KEYBOARD', [])
HF_MMDD = getattr(guess_mod, 'HF_MMDD', [])
HF_DDMM = getattr(guess_mod, 'HF_DDMM', [])
HF_YYYYMM = getattr(guess_mod, 'HF_YYYYMM', [])
HF_YYYYMMDD = getattr(guess_mod, 'HF_YYYYMMDD', [])
HF_YYYYYYYY = getattr(guess_mod, 'HF_YYYYYYYY', [])
wrap_with_affixes = getattr(guess_mod, 'wrap_with_affixes', None)

APP_TITLE = "口令猜测模拟器 GUI"

class GuessGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_TITLE)
        # 自适应屏幕的较大默认尺寸，确保所有选项可见
        try:
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            w = max(1200, int(sw * 0.80))
            h = max(850, int(sh * 0.85))
            root.geometry(f"{w}x{h}")
            root.minsize(1100, 800)
        except Exception:
            root.geometry("1200x850")
        self.running = False
        self.thread = None

        self.dataset_var = tk.StringVar(value="auto")
        self.mode_var = tk.StringVar(value="Generate")
        self.budget_var = tk.IntVar(value=50000)
        self.threads_var = tk.IntVar(value=1)
        self.delay_var = tk.IntVar(value=0)
        self.random_targets_var = tk.IntVar(value=0)
        # 默认输出/指标路径 (将在运行时若为空仍自动采用)
        default_out = os.path.join(os.path.dirname(__file__), 'output', 'guesses_gui.txt')
        default_metrics = os.path.join(os.path.dirname(__file__), 'output', 'metrics_gui.json')
        os.makedirs(os.path.join(os.path.dirname(__file__), 'output'), exist_ok=True)
        self.out_path_var = tk.StringVar(value=default_out)
        self.metrics_path_var = tk.StringVar(value=default_metrics)

        self.targets_text = None
        self.progress_label_var = tk.StringVar(value="Ready")
        self.log_text = None

        self._build_ui()
        # 预加载拼音姓氏词典（仅用于 gen_pinyin_surnames）
        self._pinyin_surnames_cache = load_pinyin_surnames() if load_pinyin_surnames else []

    def _build_ui(self):
        # 使用垂直分隔的可调整布局：上部为参数/设置区域，下部为日志输出区域
        main_pane = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        upper = ttk.Frame(main_pane)   # 承载所有控制区块
        lower = ttk.LabelFrame(main_pane, text="日志输出")  # 承载日志输出
        main_pane.add(upper, weight=3)  # 给予上半区更大权重
        main_pane.add(lower, weight=2)  # 下半区为日志

        frm_top = ttk.Frame(upper)
        frm_top.pack(fill=tk.X, padx=6, pady=4)

        ttk.Label(frm_top, text="数据集:").grid(row=0, column=0, sticky="w")
        ds_cb = ttk.Combobox(frm_top, textvariable=self.dataset_var, values=["auto","csdn","yahoo"], width=10)
        ds_cb.grid(row=0, column=1, padx=4)

        ttk.Label(frm_top, text="模式:").grid(row=0, column=2, sticky="w")
        mode_cb = ttk.Combobox(frm_top, textvariable=self.mode_var, values=["Generate","Evaluate","Simulate"], width=12)
        mode_cb.grid(row=0, column=3, padx=4)

        ttk.Label(frm_top, text="猜测上限:").grid(row=0, column=4)
        tk.Entry(frm_top, textvariable=self.budget_var, width=10).grid(row=0, column=5, padx=4)

        ttk.Label(frm_top, text="线程数:").grid(row=0, column=6)
        tk.Entry(frm_top, textvariable=self.threads_var, width=6).grid(row=0, column=7, padx=4)

        ttk.Label(frm_top, text="延迟(ms):").grid(row=0, column=8)
        tk.Entry(frm_top, textvariable=self.delay_var, width=8).grid(row=0, column=9, padx=4)

        ttk.Label(frm_top, text="随机目标数:").grid(row=0, column=10)
        tk.Entry(frm_top, textvariable=self.random_targets_var, width=6).grid(row=0, column=11, padx=4)
        frm_paths = ttk.Frame(upper)
        frm_paths.pack(fill=tk.X, padx=6, pady=4)
        ttk.Label(frm_paths, text="输出文件:").grid(row=0, column=0, sticky="w")
        tk.Entry(frm_paths, textvariable=self.out_path_var, width=50).grid(row=0, column=1, padx=4)
        ttk.Button(frm_paths, text="选择", command=self.choose_out_file).grid(row=0, column=2, padx=4)
        ttk.Label(frm_paths, text="指标文件:").grid(row=1, column=0, sticky="w")
        tk.Entry(frm_paths, textvariable=self.metrics_path_var, width=50).grid(row=1, column=1, padx=4)
        ttk.Button(frm_paths, text="选择", command=self.choose_metrics_file).grid(row=1, column=2, padx=4)

        frm_targets = ttk.LabelFrame(upper, text="目标口令（模拟模式）")
        frm_targets.pack(fill=tk.BOTH, expand=False, padx=6, pady=4)
        # 默认高度略小一点，避免遮挡下方区域；用户可通过整体分隔条调整区域
        self.targets_text = tk.Text(frm_targets, height=4)
        self.targets_text.pack(fill=tk.X, padx=4, pady=4)
        btn_row = ttk.Frame(frm_targets)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="加载文件", command=self.load_targets_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="清空", command=lambda: self.targets_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="随机抽取", command=self.sample_targets).pack(side=tk.LEFT, padx=3)

        frm_actions = ttk.Frame(upper)
        frm_actions.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(frm_actions, text="开始", command=self.start_run).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_actions, text="停止", command=self.stop_run).pack(side=tk.LEFT, padx=4)
        # 进度条
        self.progress = ttk.Progressbar(frm_actions, length=160, mode='determinate')
        self.progress.pack(side=tk.LEFT, padx=8)
        ttk.Button(frm_actions, text="说明", command=self.show_help).pack(side=tk.LEFT, padx=4)
        ttk.Label(frm_actions, textvariable=self.progress_label_var).pack(side=tk.LEFT, padx=10)

        # 将“生成类型”和“前/后缀设置”放在日志之前，避免被日志占据空间
        # 生成类型选择区（顶部中文化）
        frm_types = ttk.LabelFrame(upper, text="生成类型")
        frm_types.pack(fill=tk.X, padx=6, pady=4)
        # 纯静态模式生成器选择
        self.type_vars = {
            'builtin_high_freq': tk.BooleanVar(value=True),
            'english_core': tk.BooleanVar(value=True),
            'dates': tk.BooleanVar(value=True),
            'keyboard_repeats': tk.BooleanVar(value=True),
            'wordfreq': tk.BooleanVar(value=False),
            'pinyin_surnames': tk.BooleanVar(value=False),
            'simple_alpha_num': tk.BooleanVar(value=True),
            'exhaustive_digits': tk.BooleanVar(value=False),
        }
        labels_cn = {
            'builtin_high_freq': '高频合集',
            'english_core': '英文核心',
            'dates': '日期模式',
            'keyboard_repeats': '键盘/重复',
            'wordfreq': '英文词库(wordfreq)',
            'pinyin_surnames': '拼音姓氏',
            'simple_alpha_num': '简单字母数字',
            'exhaustive_digits': '穷举数字(≤7位)',
        }
        row1 = ['builtin_high_freq','english_core','dates','keyboard_repeats']
        row2 = ['wordfreq','pinyin_surnames','simple_alpha_num','exhaustive_digits']
        for i, key in enumerate(row1):
            ttk.Checkbutton(frm_types, text=labels_cn[key], variable=self.type_vars[key]).grid(row=0, column=i, sticky='w', padx=4)
        for i, key in enumerate(row2):
            ttk.Checkbutton(frm_types, text=labels_cn[key], variable=self.type_vars[key]).grid(row=1, column=i, sticky='w', padx=4)
        def select_all():
            for v in self.type_vars.values(): v.set(True)
        def deselect_all():
            for v in self.type_vars.values(): v.set(False)
        btn_grp = ttk.Frame(frm_types)
        btn_grp.grid(row=0, column=len(row1), rowspan=2, padx=8)
        ttk.Button(btn_grp, text="全选", command=select_all).pack(side=tk.TOP, fill=tk.X, pady=2)
        ttk.Button(btn_grp, text="全不选", command=deselect_all).pack(side=tk.TOP, fill=tk.X, pady=2)

        # 统一前/后缀面板（每类型独立前/后缀开关）
        frm_aff2 = ttk.LabelFrame(upper, text="前/后缀设置")
        frm_aff2.pack(fill=tk.X, padx=6, pady=4)
        self.affix_letter_len = tk.IntVar(value=2)
        self.affix_digit_len = tk.IntVar(value=2)
        ttk.Label(frm_aff2, text="字母长度(0-3):").grid(row=0, column=0, sticky='w')
        ttk.Spinbox(frm_aff2, from_=0, to=3, textvariable=self.affix_letter_len, width=5).grid(row=0, column=1, padx=4)
        ttk.Label(frm_aff2, text="数字长度(0-3):").grid(row=0, column=2, sticky='w')
        ttk.Spinbox(frm_aff2, from_=0, to=3, textvariable=self.affix_digit_len, width=5).grid(row=0, column=3, padx=4)
        ttk.Label(frm_aff2, text="类型前/后缀:").grid(row=1, column=0, sticky='w', pady=4)
        self.affix_prefix = {}
        self.affix_suffix = {}
        type_order = ['builtin_high_freq','english_core','dates','keyboard_repeats','wordfreq','pinyin_surnames','simple_alpha_num','exhaustive_digits']
        col = 1
        for t in type_order:
            self.affix_prefix[t] = tk.BooleanVar(value=True if t in ['builtin_high_freq','english_core','dates','keyboard_repeats'] else False)
            self.affix_suffix[t] = tk.BooleanVar(value=True if t in ['builtin_high_freq','english_core','dates','keyboard_repeats'] else False)
            frame = ttk.Frame(frm_aff2)
            frame.grid(row=1, column=col, padx=4, sticky='w')
            ttk.Label(frame, text=labels_cn[t]).pack(anchor='w')
            ttk.Checkbutton(frame, text='前缀', variable=self.affix_prefix[t]).pack(anchor='w')
            ttk.Checkbutton(frame, text='后缀', variable=self.affix_suffix[t]).pack(anchor='w')
            col += 1
        def all_prefix_on():
            for v in self.affix_prefix.values(): v.set(True)
        def all_prefix_off():
            for v in self.affix_prefix.values(): v.set(False)
        def all_suffix_on():
            for v in self.affix_suffix.values(): v.set(True)
        def all_suffix_off():
            for v in self.affix_suffix.values(): v.set(False)
        ctl = ttk.Frame(frm_aff2)
        ctl.grid(row=2, column=0, columnspan=3, sticky='w', pady=4)
        ttk.Button(ctl, text='前缀全开', command=all_prefix_on).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl, text='前缀全关', command=all_prefix_off).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl, text='后缀全开', command=all_suffix_on).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl, text='后缀全关', command=all_suffix_off).pack(side=tk.LEFT, padx=4)

        # 日志输出（带滚动条），放入可调整大小的下半区
        log_container = ttk.Frame(lower)
        log_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        yscroll = ttk.Scrollbar(log_container, orient=tk.VERTICAL)
        self.log_text = tk.Text(log_container, wrap="word", height=10, yscrollcommand=yscroll.set)
        yscroll.config(command=self.log_text.yview)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log("GUI就绪，选择模式后点击开始。")

    # ---------------- run control -----------------
    def start_run(self):
        if self.running:
            messagebox.showinfo("运行中", "已有任务在执行。")
            return
        self.running = True
        self.progress_label_var.set("运行中...")
        self.log("开始执行任务...")
        self.thread = threading.Thread(target=self._run_task, daemon=True)
        self.thread.start()
        self.root.after(200, self._poll_thread)

    def stop_run(self):
        if self.running:
            self.running = False
            self.progress_label_var.set("停止中...")
            self.log("已请求停止，当前循环结束后退出。")

    def _poll_thread(self):
        if self.thread and self.thread.is_alive():
            self.root.after(300, self._poll_thread)
        else:
            if self.running:  # thread ended naturally
                self.running = False
            self.progress_label_var.set("空闲")
            self.log("任务结束。")

    # ---------------- core logic wrapper -----------------
    def _build_generators(self):
        """构建纯静态生成器列表（不依赖任何训练统计）。"""
        gens = []
        # 英文核心（仅高频英文 + 通用后缀）
        def maybe_affix(it, tkey):
            if not wrap_with_affixes:
                return it
            lp = self.affix_prefix[tkey].get()
            ls = self.affix_suffix[tkey].get()
            if not lp and not ls:
                return it
            return wrap_with_affixes(
                it,
                max_letter_len=max(0, min(3, self.affix_letter_len.get())),
                max_digit_len=max(0, min(3, self.affix_digit_len.get())),
                allow_prefix=bool(lp),
                allow_suffix=bool(ls)
            )

        if self.type_vars['english_core'].get():
            base = gen_english([], COMMON_SUFFIX, high_priority=HF_ENGLISH)
            gens.append(maybe_affix(base, 'english_core'))
        if self.type_vars['builtin_high_freq'].get() and gen_builtin_high_freq:
            base = gen_builtin_high_freq(COMMON_SUFFIX)
            gens.append(maybe_affix(base, 'builtin_high_freq'))
        if self.type_vars['dates'].get():
            base = gen_dates(priority_years=HF_YEARS, priority_mmdd=HF_MMDD, priority_ddmm=HF_DDMM, priority_yyyymm=HF_YYYYMM, priority_yyyymmdd=HF_YYYYMMDD, priority_yyyyyyyy=HF_YYYYYYYY)
            # 日期本身也可统一前/后缀
            base = maybe_affix(base, 'dates')
            gens.append(base)
        if self.type_vars['keyboard_repeats'].get():
            base = gen_keyboard_and_repeats(priority=HF_KEYBOARD)
            gens.append(maybe_affix(base, 'keyboard_repeats'))
        if self.type_vars['wordfreq'].get() and gen_english_wordfreq:
            base = gen_english_wordfreq(2000)
            gens.append(maybe_affix(base, 'wordfreq'))
        if self.type_vars['pinyin_surnames'].get() and gen_pinyin_surnames:
            base = gen_pinyin_surnames(self._pinyin_surnames_cache, max_given=2, max_num_affix=3)
            gens.append(maybe_affix(base, 'pinyin_surnames'))
        if self.type_vars['simple_alpha_num'].get() and gen_simple_alpha_num_combos:
            base = gen_simple_alpha_num_combos()
            gens.append(maybe_affix(base, 'simple_alpha_num'))
        if self.type_vars['exhaustive_digits'].get() and gen_numeric_exhaustive_upto7:
            base = gen_numeric_exhaustive_upto7()
            gens.append(maybe_affix(base, 'exhaustive_digits'))
        return gens

    def show_help(self):
        top = tk.Toplevel(self.root)
        top.title("使用说明")
        top.geometry("760x520")
        text = tk.Text(top, wrap='word')
        scrollbar = ttk.Scrollbar(top, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        help_content = """
    【总体描述】
    本界面用于离线口令候选生成、整体评估与针对少量目标的模拟。现已为“纯静态模式”：生成过程不再利用数据集统计，仅依赖内置/词典/穷举规则。数据集只在 Evaluate 或 Simulate 时作为目标集合来源。

    【模式】
    1. Generate: 生成前 Budget 条候选（日志展示前100），可保存到文件。
    2. Evaluate: 在数据集全部口令上评估前 Budget 次猜测命中率，输出指标与命中列表。
    3. Simulate: 针对自定义或随机抽取目标集合模拟猜测过程，记录每个目标首次命中位置与耗时。

    【核心参数】
    Budget: 最大猜测次数。越大耗时越长。
    线程数: >1 启用并行预取（对纯 Python 加速有限）。
    延迟(ms): 模拟模式中每次猜测后的人工延迟。
    随机目标数: 追加从数据集中抽取的目标数量。
    输出/指标文件: 保存生成或模拟指标结果。

    【生成类型（全部静态 + 统一前/后缀）】
    高频合集: 常见弱口令/数字/日期/键盘等原型（不含内建后缀）。
    英文核心: 高频英文词原型（大小写/leet 变体）。
    日期模式: 年份/高频日期片段与多格式原型（可单独加前/后缀）。
    键盘/重复: 键盘路径 + 重复字符原型。
    英文词库(wordfreq): 常用英语词原型（需安装 wordfreq）。
    拼音姓氏: 姓氏 + 名音节组合原型。
    简单字母数字: 1..4位字母/数字枚举 + 简单重复串。
    穷举数字(≤7位): 1..7位所有数字（含前导0）。

    【前/后缀设置】
    可统一设置字母/数字长度(0-3)，并为每一种类型分别勾选是否添加前缀/后缀；“前缀全开/全关”“后缀全开/全关”便于快速切换。
    不再保留单独的“日期+前/后缀”旧选项，所有类型均通过该统一机制控制。

    【输出指标（评估）】
    tried, cracked, hit_rate, progress_points, length_stats, percentiles, time_elapsed_sec, cracked_passwords。

    【模拟指标】
    total_targets, cracked_count, hit_rate, guesses_tried, time_elapsed_sec, average_guesses_to_crack, per_target, cracked_passwords。

    【建议】
    1. 先只开 高频合集 + 英文核心 + 键盘/重复 观察效果。
    2. 需要日期覆盖再启用 日期模式；需要更广英文词再开 wordfreq。
    3. 穷举数字 与 拼音姓氏 属于扩展/深度分析策略，按需启用。
    4. 合理控制 Budget，防止长时间无收益枚举。
    5. 使用多线程前先单线程验证正确性。

    【伦理与合规】仅用于教学研究，不得用于未授权的真实系统密码猜测。
    """
        text.insert('1.0', help_content.strip())
        text.config(state='disabled')


    def _run_task(self):
        try:
            dataset = self.dataset_var.get()
            mode = self.mode_var.get()
            budget = max(1, self.budget_var.get())
            delay_ms = max(0, self.delay_var.get())
            recs = load_dataset(dataset) if mode in ("Evaluate","Simulate") or self.random_targets_var.get() > 0 else []
            gens = self._build_generators()
            if self.threads_var.get() > 1 and parallel_interleave_generators:
                self.log(f"使用并行模式(线程数={self.threads_var.get()})预取候选...")
                guesses_iter = parallel_interleave_generators(gens, budget=budget, dedup=True, threads=self.threads_var.get())
            else:
                guesses_iter = interleave_generators(gens, budget=budget, dedup=True)
            if mode == "Generate":
                self._handle_generate(guesses_iter, budget)
            elif mode == "Evaluate":
                self._handle_evaluate_progress(recs, budget)
            elif mode == "Simulate":
                self._handle_simulate_progress(recs, budget, delay_ms)
            else:
                self.log(f"未知模式: {mode}")
        except Exception as e:
            self.log(f"[错误] {e}")
        finally:
            self.running = False

    def _handle_generate(self, guesses_iter, budget):
        out_path = self.out_path_var.get().strip()
        shown = 0
        total = 0
        self.progress['value'] = 0
        self.progress['maximum'] = budget
        writer = None
        try:
            if out_path:
                os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
                writer = open(out_path, 'w', encoding='utf-8')
            for idx, g in enumerate(guesses_iter, 1):
                total += 1
                if shown < min(100, budget):
                    self.log(g)
                    shown += 1
                if writer:
                    writer.write(g + "\n")
                self.progress['value'] = idx
                if not self.running:
                    break
        except Exception as e:
            self.log(f"[!] 生成/写出失败: {e}")
        finally:
            if writer:
                writer.close()
        if out_path:
            self.log(f"[+] 已保存 {total} 条候选到 {out_path}")
        self.log(f"生成完成，总候选数: {total}")
        if total < budget:
            self.log("[提示] 已达到当前所选生成类型的可生成上限，未达到预算上限。")
            self.log("[建议] 若需更多候选，可在‘生成类型’中启用：穷举数字(≤7位) / 英文词库(wordfreq) / 拼音姓氏；或提高线程数。")

    def _handle_evaluate_progress(self, recs, budget):
        targets = [r['password'] for r in recs]
        gens = self._build_generators()
        if self.threads_var.get() > 1 and parallel_interleave_generators:
            guesses_iter = parallel_interleave_generators(gens, budget=budget, dedup=True, threads=self.threads_var.get())
        else:
            guesses_iter = interleave_generators(gens, budget=budget, dedup=True)
        progress_interval = max(1000, min(10000, budget // 10 if budget >= 1000 else budget))
        eval_dir = os.path.join(os.path.dirname(GUESS_PATH), 'output', 'evaluate')
        os.makedirs(eval_dir, exist_ok=True)
        if evaluate_with_metrics:
            # 在回调中通过 UI 线程安全地更新进度与日志
            def _on_progress(pt):
                def _ui():
                    try:
                        self.progress['value'] = pt['guesses']
                        # 每次间隔记录时输出一行简要进度
                        eta = pt.get('eta_sec')
                        eta_s = f"{eta:.1f}s" if eta is not None else "--"
                        spd = pt.get('guesses_per_sec') or 0.0
                        self.log(f"进度: {pt['guesses']}/{budget} 已破解={pt['cracked']} 命中率={pt['hit_rate']:.4f} 速度={spd:.0f}/s 预计剩余={eta_s}")
                    except Exception:
                        pass
                # 调度到主线程
                try:
                    self.root.after(0, _ui)
                except Exception:
                    pass

            metrics = evaluate_with_metrics(guesses_iter, targets, budget, progress_interval=progress_interval, progress_callback=_on_progress)
            self.log(f"评估完成：tried={metrics['tried']}, cracked={metrics['cracked']}, 命中率={metrics['hit_rate']:.4f} [静态模式]")
            cracked_path = os.path.join(eval_dir, f"cracked_gui_{self.dataset_var.get()}_{budget}.txt")
            metrics_path = os.path.join(eval_dir, f"eval_metrics_gui_{self.dataset_var.get()}_{budget}.json")
            try:
                with open(cracked_path, 'w', encoding='utf-8') as cf:
                    cf.write('\n'.join(metrics['cracked_passwords']))
                self.log(f"[+] 已保存命中口令列表: {cracked_path} 数量={len(metrics['cracked_passwords'])}")
            except Exception as e:
                self.log(f"[!] 写出命中口令失败: {e}")
            try:
                with open(metrics_path, 'w', encoding='utf-8') as mf:
                    json.dump(metrics, mf, ensure_ascii=False, indent=2)
                self.log(f"[+] 已保存评估指标 JSON: {metrics_path}")
            except Exception as e:
                self.log(f"[!] 写出评估指标失败: {e}")
            # 绘制命中率曲线
            try:
                import matplotlib.pyplot as plt
                xs = [pt['guesses'] for pt in metrics['progress_points']]
                ys = [pt['hit_rate'] for pt in metrics['progress_points']]
                if xs and ys:
                    plt.figure(figsize=(5.5,3.5))
                    plt.plot(xs, ys, marker='o', linewidth=1)
                    plt.xlabel('Guesses Tried')
                    plt.ylabel('Hit Rate')
                    plt.title('Hit Rate Curve (GUI Eval)')
                    plt.grid(alpha=0.3)
                    curve_path = os.path.join(eval_dir, f"hit_rate_curve_gui_{self.dataset_var.get()}_{budget}.png")
                    plt.tight_layout()
                    plt.savefig(curve_path, dpi=120)
                    plt.close()
                    self.log(f"[+] 已保存命中率曲线: {curve_path}")
            except Exception as e:
                self.log(f"[!] 绘制命中率曲线失败: {e}")
        else:
            # 回退逻辑
            target_set = set(targets)
            cracked = 0
            tried = 0
            cracked_once = set()
            self.progress['value'] = 0
            self.progress['maximum'] = budget
            for g in guesses_iter:
                tried += 1
                if g in target_set and g not in cracked_once:
                    cracked_once.add(g)
                    cracked += 1
                if tried % 10000 == 0:
                    self.log(f"进度: {tried}/{budget} 已破解={cracked}")
                self.progress['value'] = tried
                if not self.running or tried >= budget:
                    break
            hit_rate = cracked / max(1, len(set(targets)))
            self.log(f"评估完成：tried={tried}, cracked={cracked}, 命中率={hit_rate:.4f}")

    def _parse_targets_text(self):
        raw = self.targets_text.get("1.0", tk.END).strip()
        if not raw:
            return []
        parts = []
        for line in raw.splitlines():
            line = line.strip()
            if not line: continue
            parts.extend([p for p in re_split_multi(line)])
        # 去重
        seen = []
        for p in parts:
            if p not in seen:
                seen.append(p)
        return seen

    def _handle_simulate_progress(self, recs, budget, delay_ms):
        targets = self._parse_targets_text()
        if self.random_targets_var.get() > 0:
            all_pw = list({r['password'] for r in recs if r.get('password')})
            n = self.random_targets_var.get()
            if n >= len(all_pw):
                sampled = all_pw
            else:
                sampled = random.sample(all_pw, n)
            targets.extend(sampled)
        if not targets:
            all_pw = [r['password'] for r in recs if r.get('password')]
            if all_pw:
                targets.append(random.choice(all_pw))
        unique_targets = list(dict.fromkeys(targets))
        target_lookup = set(unique_targets)
        per_target = {pw: None for pw in unique_targets}
        cracked_count = 0
        tried = 0
        delay = max(0, delay_ms) / 1000.0
        gens = self._build_generators()
        if self.threads_var.get() > 1 and parallel_interleave_generators:
            guesses_iter = parallel_interleave_generators(gens, budget=budget, dedup=True, threads=self.threads_var.get())
        else:
            guesses_iter = interleave_generators(gens, budget=budget, dedup=True)
        self.progress['value'] = 0
        self.progress['maximum'] = budget
        start_time = time.time()
        for guess in guesses_iter:
            tried += 1
            if guess in target_lookup and per_target[guess] is None:
                per_target[guess] = tried
                cracked_count += 1
                self.log(f"命中目标: {guess} 于第 {tried} 次猜测")
                if cracked_count == len(unique_targets):
                    self.log("全部目标已命中，提前结束。")
                    break
            if tried % 10000 == 0:
                self.log(f"进度: {tried}/{budget} 已命中={cracked_count}")
            self.progress['value'] = tried
            if delay:
                time.sleep(delay)
            if not self.running or tried >= budget:
                break
        elapsed = time.time() - start_time
        hit_rate = cracked_count / max(1, len(unique_targets))
        avg_guess = (
            sum(idx for idx in per_target.values() if idx is not None) / max(1, cracked_count)
            if cracked_count else 0
        )
        metrics = {
            "total_targets": len(unique_targets),
            "cracked_count": cracked_count,
            "hit_rate": hit_rate,
            "guesses_tried": tried,
            "time_elapsed_sec": elapsed,
            "average_guesses_to_crack": avg_guess,
            "per_target": per_target,
            "cracked_passwords": [pw for pw, idx in per_target.items() if idx is not None]
        }
        self.log("模拟完成。指标如下：")
        self.log(json.dumps(metrics, ensure_ascii=False, indent=2))
        metrics_path = self.metrics_path_var.get().strip()
        if metrics_path:
            try:
                os.makedirs(os.path.dirname(metrics_path) or '.', exist_ok=True)
                with open(metrics_path, 'w', encoding='utf-8') as mf:
                    json.dump(metrics, mf, ensure_ascii=False, indent=2)
                self.log(f"[+] 指标已保存到 {metrics_path}")
            except Exception as e:
                self.log(f"[!] 写出指标失败: {e}")


def re_split_multi(line: str):
    # 支持逗号/空白分隔
    import re
    return [x for x in re.split(r'[\s,]+', line) if x]

    # ---- utility methods (added after refactor restoring missing helpers) ----

def _safe_strip_lines(lines):
    return [l.strip() for l in lines if l.strip()]

def _unique(seq):
    seen=set(); out=[]
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

def _ensure_dir(p):
    d=os.path.dirname(p) or '.'
    os.makedirs(d, exist_ok=True)
    return p

# Inject missing methods into GuessGUI (monkey patch style if class already defined)
def _add_methods_to_GuessGUI():
    def log(self, msg: str):
        try:
            ts=time.strftime('%H:%M:%S')
            self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.log_text.see(tk.END)
        except Exception:
            pass
    def choose_out_file(self):
        path=filedialog.asksaveasfilename(title="选择输出文件", defaultextension=".txt", filetypes=[("Text","*.txt"),("All","*.*")])
        if path:
            self.out_path_var.set(path)
    def choose_metrics_file(self):
        path=filedialog.asksaveasfilename(title="选择指标JSON文件", defaultextension=".json", filetypes=[("JSON","*.json"),("All","*.*")])
        if path:
            self.metrics_path_var.set(path)
    def load_targets_file(self):
        path=filedialog.askopenfilename(title="加载目标文件", filetypes=[("Text","*.txt"),("All","*.*")])
        if not path: return
        try:
            with open(path,'r',encoding='utf-8',errors='ignore') as f:
                lines=f.readlines()
            items=_unique(_safe_strip_lines(lines))
            self.targets_text.delete('1.0', tk.END)
            self.targets_text.insert('1.0','\n'.join(items))
            self.log(f"已加载目标 {len(items)} 条")
        except Exception as e:
            self.log(f"加载目标失败: {e}")
    def sample_targets(self):
        # 抽取少量高频日期或英文词作为演示; 实际按数据集抽取
        try:
            recs=load_dataset(self.dataset_var.get())
            pw=[r['password'] for r in recs if r.get('password')]
            if not pw:
                self.log('数据集中无可用密码记录。'); return
            n=min(10,len(pw))
            sampled=random.sample(pw,n)
            self.targets_text.insert(tk.END, '\n' + '\n'.join(sampled))
            self.log(f"随机追加目标 {n} 条")
        except Exception as e:
            self.log(f"随机抽取失败: {e}")
    for name, fn in {
        'log': log,
        'choose_out_file': choose_out_file,
        'choose_metrics_file': choose_metrics_file,
        'load_targets_file': load_targets_file,
        'sample_targets': sample_targets,
    }.items():
        if not hasattr(GuessGUI, name):
            setattr(GuessGUI, name, fn)

_add_methods_to_GuessGUI()


def main():
    root = tk.Tk()
    app = GuessGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
