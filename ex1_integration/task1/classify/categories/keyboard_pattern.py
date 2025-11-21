NAME = "keyboard_pattern"
DESCRIPTION = "键盘序列（横向与双向斜线，含数字行 Shift 符号，如 qwerty、asdf、qaz、esz、!@#$ 等）"

# 更完整的 QWERTY 键盘行（小写），用于构建坐标网格
ROWS = [
    "`1234567890-=",
    "qwertyuiop[]\\",
    "asdfghjkl;'",
    "zxcvbnm,./",
]

# 方向向量：
#  - 横向左右:      (dr=0, dc=+1/-1)
#  - 纵向上下:      (dr=+1/-1, dc=0)
#  - 斜线双向:      (dr=+1/-1, dc=+1/-1)
DIRS = [
    (0, 1), (0, -1),     # 水平
    (1, 0), (-1, 0),     # 垂直（覆盖如 qaz、wsx、edc 等常见列）
    (1, -1), (-1, 1),    # 仅保留 ↙ 与 ↗，移除 ↘ 与 ↖ 以避免 qsc 一类无意义匹配
]

# 最小长度阈值：横向用 4，纵向/斜线用 3（以满足 qaz/esz 示例）
MIN_LEN_HORIZONTAL = 4
MIN_LEN_DIAG_OR_VERT = 3


def _build_pos_map():
    pos = {}
    for r, row in enumerate(ROWS):
        for c, ch in enumerate(row):
            pos[ch] = (r, c)
    return pos


POS = _build_pos_map()


def _min_len_for_dir(dr, dc):
    return MIN_LEN_HORIZONTAL if dr == 0 and dc != 0 else MIN_LEN_DIAG_OR_VERT


# 将 Shift 符号归一化到未按下 Shift 的基础键，避免漏检与误报
SHIFT_TO_BASE = {
    "~": "`", "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0", "_": "-", "+": "=",
    "{": "[", "}": "]", "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".", "?": "/",
}


def _norm_char(ch: str) -> str:
    # 字母统一小写；符号按 SHIFT_TO_BASE 归一化到基础键
    if "A" <= ch <= "Z":
        ch = ch.lower()
    return SHIFT_TO_BASE.get(ch, ch)


def detect(ctx):
    # 先对整串做大小写与 Shift 符号归一化
    raw = ctx.password
    s = "".join(_norm_char(c) for c in raw)
    # 仅在字符串中包含至少 3 个可映射键时再检测，减少无谓开销
    if sum(1 for ch in s if ch in POS) < 3:
        return False

    # 在每个起点尝试所有方向的“等步长直线”序列
    n = len(s)
    for i in range(n):
        ch = s[i]
        if ch not in POS:
            continue
        r0, c0 = POS[ch]

        for dr, dc in DIRS:
            need = _min_len_for_dir(dr, dc)
            length = 1
            r, c = r0, c0
            j = i + 1
            while j < n:
                chj = s[j]
                if chj not in POS:
                    break
                r += dr
                c += dc
                # 越界或该位置字符与期望不一致则停止
                if r < 0 or r >= len(ROWS):
                    break
                row = ROWS[r]
                if c < 0 or c >= len(row):
                    break
                if row[c] != chj:
                    break
                length += 1
                if length >= need:
                    return True
                j += 1
    return False
