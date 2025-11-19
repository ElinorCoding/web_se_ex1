# 口令猜测模拟器 (CLI + GUI)

本工具用于研究与教学场景下的离线口令候选生成、评估与针对少量目标的模拟猜解。所有操作均在本地数据集上进行，不与外部服务交互。

## 数据来源
- `code/processed_dataset/csdn_mail_password_username.txt`
- `code/processed_dataset/yahoo_mail_password.txt`

## CLI 脚本 `guess.py` 功能概览
- 训练: 从数据集中统计常见片段与模式
- 生成: 基于统计与启发式生成候选 (`--out` 写出)
- 评估: 批量评估前 K 次猜测命中率 (`--evaluate`)
- 模拟: 针对一个或多个目标逐步猜测并记录命中顺序与耗时 (`--simulate-targets`)

### CLI 示例
```powershell
# 评估数据集整体命中率
python .\code\guess\guess.py --dataset csdn --budget 100000 --evaluate

# 写出 20 万条候选到文件
python .\code\guess\guess.py --dataset yahoo --budget 200000 --out .\guesses.txt

# 模拟三个随机目标
python .\code\guess\guess.py --simulate-targets --random-targets 3 --budget 60000 --demo

# 模拟指定目标并输出指标 JSON
python .\code\guess\guess.py --simulate-targets --target 123456,password,qwerty --budget 300000 --delay-ms 2 --metrics-out .\metrics.json

# 评估并直接生成命中率曲线 (需安装 matplotlib)
python .\code\guess\guess.py --dataset yahoo --budget 150000 --evaluate --plot-hit-rate

# 自定义进度采样与输出路径
python .\code\guess\guess.py --dataset yahoo --budget 150000 --evaluate --progress-interval 5000 --plot-hit-rate --plot-out .\my_curve.png
```

### 关键参数
| 参数 | 说明 |
|------|------|
| `--dataset` | `csdn` / `yahoo` / `auto` 自动选择 |
| `--budget` | 猜测或生成的最大次数 |
| `--out` | 写出生成的候选列表到文件 |
| `--evaluate` | 对全数据集密码集合进行命中率评估 |
| `--simulate-targets` | 启用针对目标的模拟模式 |
| `--target` | 逗号分隔的一组目标口令 |
| `--target-file` | 文件方式提供目标口令，每行一个 |
| `--random-targets N` | 从数据集随机抽 N 个目标 |
| `--demo` | 模拟模式下先打印目标列表 |
| `--delay-ms` | 猜测循环延迟（毫秒），用于演示开销 |
| `--metrics-out` | 输出模拟指标 JSON 文件路径 |
| `--eval-metrics-out` | 评估模式输出详细指标 JSON（含 progress_points 等） |
| `--cracked-out` | 评估模式输出命中口令列表文件 |
| `--plot-hit-rate` | 评估完成后生成命中率-猜测次数折线图（需要 matplotlib） |
| `--plot-out` | 自定义命中率曲线图输出路径 |
| `--progress-interval` | 评估进度采样间隔（影响曲线点密度） |
| `--no-progress` | 评估时不打印终端进度 |

## GUI 脚本 `guess_gui.py`
运行:
```powershell
python .\code\guess\guess_gui.py
```

### GUI 功能
- 数据集选择与模式切换（生成 / 评估 / 模拟）
- 参数输入：猜测上限、延迟、随机目标数量
- 目标输入：文本框、文件加载、随机抽取
- 输出文件与指标文件保存选择
- 实时日志显示与进度条更新，停止按钮可中断任务

### 使用建议
1. 先选择数据集与模式，再设定预算与其它参数。
2. 模拟模式可将少量关心的口令放入文本框，或随机抽取若干进行演示。
3. 若需要记录指标用于报告，请指定 `指标文件` 路径。
4. 生成模式默认仅展示前 100 条，若要获取全部需填写 `输出文件`。

### 典型演示流程
1. 生成模式: 预算 50000 -> 查看前 100 条常见候选。
2. 评估模式: 预算 150000 -> 观察整体命中率。
3. 模拟模式: 输入 `123456` `password` `qwerty` -> 查看被命中的相对次序与平均猜测次数。

## 指标说明（模拟模式）
| 字段 | 含义 |
|------|------|
| `total_targets` | 参与模拟的目标口令总数 |
| `cracked_count` | 被命中的数量 |
| `hit_rate` | 命中率（cracked / total） |
| `guesses_tried` | 实际执行的猜测次数 |
| `time_elapsed_sec` | 总耗时（秒） |
| `average_guesses_to_crack` | 已命中目标的平均首命中猜测序号 |
| `per_target` | 每个目标的首次命中猜测序号（None 表示未命中） |
| `cracked_passwords` | 被命中的目标列表 |

## 指标说明（评估模式）
评估模式在启用 `--evaluate` 时，可选使用扩展函数 `evaluate_with_metrics`（自动在 GUI 与 CLI 内部启用）。其输出 JSON（文件名形如 `eval_metrics_<dataset>_<budget>.json` 或 `eval_metrics_gui_<dataset>_<budget>.json`）包含：

| 字段 | 说明 |
|------|------|
| `tried` | 已尝试猜测总次数（不超过 budget） |
| `cracked` | 命中的数据集口令数量 |
| `hit_rate` | `cracked / total_targets` |
| `cracked_passwords` | 已命中口令列表（排序） |
| `progress_points` | 进度采样点列表，每项含 `guesses, cracked, hit_rate, elapsed_sec, guesses_per_sec, eta_sec` |
| `length_stats` | 长度统计：平均长度、长度直方图（全部/已命中） |
| `percentiles` | 首次命中猜测序号的分位数：p25/p50/p75/p90 |
| `time_elapsed_sec` | 总耗时（秒） |

示例获取末尾命中率曲线:
```python
xs = [pt['guesses'] for pt in metrics['progress_points']]
ys = [pt['hit_rate'] for pt in metrics['progress_points']]
```

## 命中率曲线后处理脚本
为便于在评估完成后独立重绘命中率曲线（无需再次运行大预算评估），新增实用脚本：`temp/plot_yahoo_hit_rate_from_json.py`。

功能：
- 自动在 `code/guess/output/evaluate/` 内查找最新的 `yahoo` 评估 JSON。
- 读取其中的 `progress_points` 绘制折线图（命中率 vs 猜测次数）。
- 输出文件命名：`hit_rate_curve_<dataset>_<budget>.png`，与 CLI 内置逻辑保持一致。

使用示例（PowerShell）：
```powershell
python .\temp\plot_yahoo_hit_rate_from_json.py                 # 使用最新 yahoo JSON
python .\temp\plot_yahoo_hit_rate_from_json.py --file .\code\guess\output\evaluate\eval_metrics_gui_yahoo_1000000000.json
python .\temp\plot_yahoo_hit_rate_from_json.py --input-dir .\code\guess\output\evaluate --dataset yahoo --out-dir .\code\guess\output\evaluate
```

依赖：需要 `matplotlib`；若未安装会收到提示，可通过 `pip install matplotlib` 安装后再运行。


## 安全与伦理提示
本工具仅用于教学与研究环境中的密码强度、模式分析与防御策略讨论。请勿用于任何未授权的真实系统或数据。仅处理仓库中已提供的离线示例数据。

## 后续可扩展点
- 增加可视化图表（需引入 `matplotlib` 等第三方库）
- 增加多线程生成与更细粒度的进度预测
- 支持导出日志与加载上次会话配置

如需进一步功能，请在 issue 或任务中提出。
