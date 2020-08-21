# -----------------------------------------------
# bwcc: utils.py
#
# BaseParser 类和用到的其它工具
# -----------------------------------------------


class ParseError(Exception):
    pass


class Coord(object):
    """ 文法符号的坐标。

    Attributes:
        file: 文法符号所在的文件名
        line: 文法符号所在的行
        column: 文法符号所在的列（可选）
    """
    __slots__ = ('file', 'line', 'column', '__weakref__')

    def __init__(self, file, line, column=None):
        self.file = file
        self.line = line
        self.column = column

    def __str__(self):
        str = "{}:{}".format(self.file, self.line)
        if self.column:
            str += "({})".format(self.column)
        return str


class BaseParser(object):
    """ 作为PLY语法分析器的基础类，提供和语言无关的一些基本功能
    """
    def _create_opt_rule(self, rulename):
        """ 为指定的规则创建一条可选规则。

        给定 rulename，自动创建一条名为 rulename_opt 的规则作为可选规则
        """
        optname = rulename + '_opt'

        def optrule(self, p):
            p[0] = p[1]

        optrule.__doc__ = '%s : empty\n| %s' % (optname, rulename)
        optrule.__name__ = 'p_%s' % optname
        setattr(self.__class__, optrule.__name__, optrule)

    def _coord(self, lineno, column=None):
        """ 构造文法符号的坐标
        """
        return Coord(
            file=self.clex.filename,
            line=lineno,
            column=column
        )

    def _token_coord(self, p, token_idx):
        """ 寻找产生式中第 token_idx 个文法符号的坐标
        """
        last_cr = p.lexer.lexer.lexdata.rfind('\n', 0, p.lexpos(token_idx))
        if last_cr < 0:
            last_cr = -1
        column = (p.lexpos(token_idx) - last_cr)
        return self._coord(p.lineno(token_idx), column)

    def _parse_error(self, msg, coord):
        raise ParseError("{}: {}".format(coord, msg))
