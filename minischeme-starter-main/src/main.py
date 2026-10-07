"""mini-Scheme 解释器入口（spec §2 的 CLI 约定）。

用法::

    python3 src/main.py [文件1.scm 文件2.scm ...]

* 按顺序求值每个文件里的顶层表达式，每个结果独占一行打印；
* 结果为 None（``display``、``newline``、没有假分支的 ``if``）时不打印；
* 多个文件共享同一个全局环境；不给参数时从标准输入读取。
"""

import os
import sys

# 直接运行 `python3 src/main.py` 时，保证同目录的模块能被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from environment import Environment  # noqa: E402
from errors import SchemeError  # noqa: E402
from evaluator import evaluate  # noqa: E402
from library import install_builtins  # noqa: E402
from parser import parse  # noqa: E402
from printer import to_write_string  # noqa: E402


def run_source(source, environment):
    """流水线：文本 → 词 → 表达式 → 值 → 打印。"""
    if source.startswith("\ufeff"):  # 容忍带 BOM 的 UTF-8 文件
        source = source[1:]
    for expression in parse(source):
        value = evaluate(expression, environment)
        if value is not None:
            sys.stdout.write(to_write_string(value) + "\n")


def main(argv):
    _configure_streams()
    # Scheme 的递归（以及 map/filter 这类写在语言里的高阶函数）会按数据规模
    # 加深 Python 调用栈，这里放宽上限，避免长列表被 Python 的默认限制打断。
    # 实测 3 万层 Scheme 递归仍能正常返回（出错时也会被下面的 RecursionError 接住）。
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 200000))

    environment = Environment()
    install_builtins(environment)

    paths = argv[1:]
    try:
        if not paths:
            run_source(sys.stdin.read(), environment)
        else:
            for path in paths:
                with open(path, "r", encoding="utf-8-sig") as handle:
                    run_source(handle.read(), environment)
    except SchemeError as error:
        sys.stdout.flush()
        print("错误：%s" % error, file=sys.stderr)
        return 1
    except RecursionError:
        sys.stdout.flush()
        print("错误：递归层数过深（超出解释器可处理的深度）", file=sys.stderr)
        return 1
    except OSError as error:
        sys.stdout.flush()
        print("无法读取文件：%s" % error, file=sys.stderr)
        return 1

    sys.stdout.flush()
    return 0


def _configure_streams():
    """固定 UTF-8 与 ``\\n``，保证输出与期望结果逐字节一致。

    Windows 上标准输出默认会把 ``\\n`` 翻译成 ``\\r\\n``，而且默认编码可能是
    GBK；这里显式关掉翻译、统一成 UTF-8，程序在不同平台上输出就完全一样。
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass  # 被重定向成不支持 reconfigure 的对象时忽略即可


if __name__ == "__main__":
    sys.exit(main(sys.argv))
