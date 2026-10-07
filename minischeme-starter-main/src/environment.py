"""环境：变量绑定表 + 指向外层环境的指针。

一层环境就是一个"作用域"（全局、lambda 调用时新建的一层、let 的一层）。
查找变量时先看本层，找不到就顺着 ``parent`` 往外找——这正是词法作用域的实现。
"""

from errors import SchemeError


class Environment:
    """链式作用域环境。"""

    __slots__ = ("_bindings", "parent")

    def __init__(self, parent=None):
        self._bindings = {}  # 名字(str) -> 值
        self.parent = parent

    def define(self, name, value):
        """在当前层建立/覆盖绑定（``define``、``let``、lambda 形参都用它）。"""
        self._bindings[name.name] = value
        return value

    def lookup(self, name):
        """按名字取变量值，逐层向外查；都没有则报错。"""
        environment = self
        while environment is not None:
            bindings = environment._bindings
            if name.name in bindings:
                return bindings[name.name]
            environment = environment.parent
        raise SchemeError("未定义的符号：%s" % name.name)
