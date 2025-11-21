# ex1 使用说明

本目录包含两部分作业：Task1（密码分类与多维度特征分析）与 Task2（离线口令候选生成/评估/模拟）。下文给出目录结构、脚本功能、运行方式与注意事项。


## 目录结构

- Task1
```
ex1_integration/task1/
├─ analyze/
|  ├─ analysis_results/              # 输出：各类分析生成的 JSON 汇总与 TXT 报告
│  ├─ dictionary_order_analysis.py   # 字典序连续字符分析程序
│  ├─ composition_analysis.py        # 字符组成模式分析程序（数字/字母/符号结构）
│  ├─ ...                            # 其他特征分析程序
│  └─ visualize_results.py           # 统一可视化脚本（读取所有分析结果并绘图 —— 需要 matplotlib）
├─ classify/
│  ├─ classify.py                    # 密码分类主脚本（可扩展分类器）
│  ├─ categories/                    # 分类器定义（可按需添加/调整）
│  ├─ classify_result/               # 输出：按数据集拆分的分类结果与汇总
│  └─ tests/                         # 自检用测试（可选）
├─ dicts/
│  ├─ pinyin_surnames.txt            # 拼音姓氏词表
│  └─ pinyin_syllables.txt           # 拼音音节词表
├─ generated_graphs/                 # 输出：各类可视化图表（按分析类型分文件夹）
│  └─ ...           
└─ processed_dataset/
   ├─ csdn_mail_password_username.txt
   └─ yahoo_mail_password.txt
```

- Task2
```
ex1_integration/task2/
└─ guess/
   ├─ guess.py                       # CLI：离线候选生成/评估/模拟
   ├─ guess_gui.py                   # GUI：可视化配置与运行
   ├─ data/                          # 轻量示例数据（优先使用）
   │  ├─ csdn_5000.txt
   │  ├─ yahoo_5000.txt
   │  ├─ pinyin_surnames.txt
   │  └─ pinyin_syllables.txt
   └─ output/                        # 输出：generate/evaluate/simulate
```


## 运行环境
- Python 3.9+
- 仅 Task1 的 `visualize_results.py` 需要 `matplotlib`：
  ```powershell
  pip install matplotlib
  ```


## 快速开始（建议在仓库根目录运行）
以下命令默认工作目录：`C:\Users\Wanderer\AAAUCAS\25-9\Websec\Teamwork1`（仓库根）。

### Task1：密码分类与特征统计分析
1) 分类（示例：CSDN，抽样 1000 行，单线程）
```powershell
python .\ex1_integration\task1\classify\classify.py --dataset csdn --limit 1000 --workers 1 --output-dir .\ex1_integration\task1\classify\classify_result
```
输出：
- `ex1_integration/task1/classify/classify_result/csdn/` 下的各类别文本与 `summary.json`
- 控制台打印各类别计数与占比

2) 密码特征分析（示例：字典顺序分析）
```powershell
python .\ex1_integration\task1\analyze\dictionary_order_analysis.py
```
输出：
- `./ex1_integration/task1/analyze/analysis_results/dictionary_order_report.txt`
- `./ex1_integration/task1/analyze/analysis_results/date_summary.json`

3) 可视化（可选，需 matplotlib）
```powershell
python .\ex1_integration\task1\analyze\visualize_results.py
```
输出：
- `ex1_integration/task1/generated_graphs/` 下各类 PNG 图：
  - 分类占比饼图、各类柱状图、复合特征 TopK、字典序序列/长度/起始字符分布

注意：
- `classify.py` 默认读取 `ex1_integration/task1/processed_dataset/` 下数据；
- `dictionary_order_analysis.py` 采用顶层 `code/processed_dataset/` 的默认路径。如果希望改为使用 `ex1_integration/task1/processed_dataset/`，可自行调整脚本顶部 `FILE_CSDN/FILE_YAHOO` 的路径。


### Task2：候选生成 / 评估 / 模拟
1) 评估模式（示例：CSDN，预算 2000）
```powershell
python .\ex1_integration\task2\guess\guess.py --dataset csdn --budget 2000 --evaluate
```
输出：
- 命中列表与指标 JSON 写入 `ex1_integration/task2/guess/output/evaluate/`

2) 模拟模式（指定/随机目标）
```powershell
# 指定多个目标（逗号分隔），预算 50000，带 2ms 延迟，输出到 metrics.json
python .\ex1_integration\task2\guess\guess.py --simulate-targets --target 123456,password --budget 50000 --delay-ms 2 --metrics-out .\metrics.json

# 从数据集中随机抽取 3 个目标进行模拟
python .\ex1_integration\task2\guess\guess.py --dataset csdn --simulate-targets --random-targets 3 --budget 20000 --demo
```

3) GUI（可视化控制，支持前/后缀统一设置与每类单独开关）
```powershell
python .\ex1_integration\task2\guess\guess_gui.py
```
功能要点：
- 生成类型：高频合集、英文核心、日期、键盘/重复、英文词库、拼音姓氏、简单字母数字、穷举数字
- 前/后缀：统一长度(0–3)与“每种类型独立”前/后缀开关（不会产生“前+本体+后”双侧组合）
- 模式：Generate（仅生成）、Evaluate（评估集命中率）、Simulate（指定目标模拟）
- 进度：速率/ETA/阶段命中统计，支持并行预取与去重


## 可运行性结论（烟雾测试）
已在本机以默认数据做最小化验证：
- `classify.py`（CSDN，limit=1000）能运行并在 `classify_result/csdn/` 下生成输出；
- `dictionary_order_analysis.py` 能生成报告与汇总 JSON；
- `guess.py` 在 `--evaluate` 模式下可运行，生成命中列表与指标 JSON；
- `guess_gui.py` 可启动并正常操作（窗口默认自适应较大尺寸）。

若迁移到其他环境，请确保：
- Python 版本满足要求；
- 需要绘图时安装 `matplotlib`；
- 数据文件路径存在（如需自定义路径，可通过 CLI 参数或修改脚本顶部常量）。


## 常见问题
- 路径不匹配：请在仓库根目录运行命令，或按需修改脚本顶部的默认路径常量。
- 图表中文乱码：可在 `visualize_results.py` 中调整 `plt.rcParams['font.sans-serif']`。
- 性能：Task2 的并行预取对纯 Python 提升有限，优先通过缩小 `budget`、启用去重与精简生成器组合来控制规模。
