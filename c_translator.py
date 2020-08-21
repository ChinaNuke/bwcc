import c_ast
import math
from c_parser import CParser

TYPE_WIDTH = {'int': 4, 'char': 1}
WORD_SIZE = 4


class MCode(object):
    """ 四元式类
    (jnz, a, -, p)
    """

    def __init__(self, op, arg1, arg2, result):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.result = result

    def __repr__(self):
        return '({}, {}, {}, {})'.format(self.op, self.arg1 if self.arg1 != None else '-',
                                         self.arg2 if self.arg2 != None else '-',
                                         self.result if self.result != None else '-')
    def __str__(self):
        return self.__repr__()


class CTranslator(object):

    def __init__(self):
        self.codes = []  # 四元式
        self.symbol_table = {}  # 符号名表 {函数名：{symbols:{name: type}, stacksize:xx)}}
        self.func_table = []
        self.constant_table = {}  # 常量表 {常量值：(所属函数， 序号)}
        self.constant_count = 0
        self.temp_count = 0
        self.label_count = 0
        self.cur_func = None

    def get_codes(self):
        for code in self.codes:
            yield code

    def get_tables(self):
        # 根据符号表的类型计算需要初始化的堆栈大小和各个变量的偏移量
        symbols = {}
        for func, table in self.symbol_table.items():
            temp = {}
            offset = stacksize = math.ceil(table['stacksize'] / 16) * 16  # stacksize是16的整数倍
            for name, type in table['symbols'].items():
                offset = offset - TYPE_WIDTH[type]
                temp[name] = offset
                offset = (offset // WORD_SIZE) * WORD_SIZE  # 字对齐
            symbols[func] = {'symbols': temp, 'stacksize': stacksize}
        return {'constant_table': self.constant_table, 'symbol_table': symbols}

    def _newtemp(self, type='int'):
        # TODO: 似乎可以不用临时变量，eax本身就可以作为中间变量
        self.temp_count = self.temp_count + 1
        name = 'T' + str(self.temp_count)
        self.symbol_table[self.cur_func]['symbols'][name] = type
        self.symbol_table[self.cur_func]['stacksize'] += TYPE_WIDTH[type]
        return name

    def _newlabel(self):
        self.label_count = self.label_count + 1
        return 'L' + str(self.label_count)

    def _emit(self, op, arg1, arg2, result):
        self.codes.append(MCode(op, arg1, arg2, result))

    def _emitbranch(self, *args):
        """
        生成无条件分支或有条件分支代码
        Args:
            *args:
        """
        if len(args) == 1:
            self._emit('j', None, None, args[0])
        elif len(args) == 3:
            # TODO：解决对 cond 的自动分析
            cond = args[0]
            if cond.op in ('>', '<', '==', '>=', '<=', '!='):
                self._emit('j' + cond.op, cond.left.name, cond.right.value, args[1])
                self._emit('j', None, None, args[2])
            elif cond.op in ('&&', '||', '!', '&', '|', '~'):
                # TODO
                pass

            # self._emit('j' + args[0].op, args[0].left.name, args[0].right.value, args[1])
            # self._emit('j', None, None, args[2])
        else:
            raise TypeError('生成分支调用参数个数错误！')

    def _emitlabel(self, label):
        self._emit('label', None, None, label)

    def _enter_func(self, funcname):
        self._emit('func', None, None, funcname)
        self.cur_func = funcname
        self.symbol_table[funcname] = {'symbols': {}, 'stacksize': 0}
        self.offset = 0

    def _exit_func(self):
        self._emit('endfunc', None, None, None)
        self.cur_func = None

    def visit(self, node):
        method = 'visit_' + node.__class__.__name__
        return getattr(self, method)(node)

    def visit_FileAST(self, node):
        for ext in node.ext:
            if isinstance(ext, c_ast.FuncDef):
                self.visit(ext)
            else:
                pass

    def visit_DeclList(self, node):
        for decl in node.decls:
            self.visit(decl)

    def visit_Decl(self, node):
        if isinstance(node.type, c_ast.TypeDecl):
            typename = self.visit(node.type)
            self.symbol_table[self.cur_func]['symbols'][node.name] = typename
            self.symbol_table[self.cur_func]['stacksize'] += TYPE_WIDTH[typename]
            if node.init:
                self._emit('=', self.visit(node.init), None, node.name)
        elif isinstance(node.type, c_ast.FuncDecl):
            self.visit(node.type)

    def visit_TypeDecl(self, node):
        return node.type.names[0]

    def visit_FuncDef(self, node):
        self._enter_func(node.decl.name)
        self.visit(node.decl)
        self.visit(node.body)
        self._exit_func()

    def visit_FuncDecl(self, node):
        if node.args:
            for param in node.args.params:
                self.symbol_table[self.cur_func]['symbols'][param.name] = param.type.type.names[0]

    def visit_FuncCall(self, node):
        for i, arg in enumerate(reversed(node.args.exprs)):
            self._emit('param', i, self.visit(arg), len(node.args.exprs))  # result中保存参数的总个数
            self.symbol_table[self.cur_func]['stacksize'] += WORD_SIZE
        self._emit('call', None, None, node.name.name)
        return '_' + node.name.name

    def visit_Compound(self, node):
        for body in node.block_items:
            self.visit(body)

    def visit_If(self, node):
        truelabel = self._newlabel()
        falselabel = self._newlabel() if node.iffalse else None
        endlabel = self._newlabel()

        """
                j>, x, 0, true
                j false
        true:   ...
                j end
        false:  ...
        end:
        """
        self._emitbranch(node.cond, truelabel, falselabel or endlabel)
        self._emitlabel(truelabel)
        self.visit(node.iftrue)  # true执行体
        self._emitbranch(endlabel)

        if node.iffalse:
            self._emitlabel(falselabel)
            self.visit(node.iffalse)  # false执行体
        self._emitlabel(endlabel)

    def visit_While(self, node):
        beginlabel = self._newlabel()
        truelabel = self._newlabel()
        falselabel = self._newlabel()
        """
        begin:  j>, x, 0, true
                j false
        true:   ...
                j begin
        false:
        """
        self._emitlabel(beginlabel)
        self._emitbranch(node.cond, truelabel, falselabel)
        self._emitlabel(truelabel)
        self.visit(node.stmt)
        self._emitbranch(beginlabel)
        self._emitlabel(falselabel)

    def visit_For(self, node):
        beginlabel = self._newlabel()
        truelabel = self._newlabel()
        falselabel = self._newlabel()
        """
                ...(initialize)
        begin:  j>, x, 0, true
                j false
        true:   ...
                ...(next)
                j begin
        false:
        """
        self.visit(node.init)  # 跟 While 就差在这
        self._emitlabel(beginlabel)
        self._emitbranch(node.cond, truelabel, falselabel)
        self._emitlabel(truelabel)
        self.visit(node.stmt)
        self.visit(node.next)  # 还有着
        self._emitbranch(beginlabel)
        self._emitlabel(falselabel)

    def visit_Assignment(self, node):
        left = node.lvalue.name
        right = self.visit(node.rvalue)
        self._emit('=', right, None, left)

    def visit_BinaryOp(self, node):
        temp = self._newtemp()
        self._emit(node.op, self.visit(node.left), self.visit(node.right), temp)
        return temp

    def visit_UnaryOp(self, node):
        orign = self.visit(node.expr)
        if len(node.op) == 1:  # 单纯的+和-
            if node.op == '+':
                return orign
            elif node.op == '-':
                if orign.isdigit():
                    return '-' + orign
                else:
                    temp = self._newtemp()
                    self._emit(node.op, str(0), orign, temp)
                    return temp
        else:  # ++、--等
            temp = self._newtemp()
            op = node.op[-1]
            self._emit(op, orign, str(1), temp)
            self._emit('=', temp, None, orign)
            if node.op.startswith('p'):
                return orign
            else:
                return temp

    def visit_Constant(self, node):
        # TODO: 加入对String的处理
        if node.type == 'string':
            s = node.value[1:-1]
            if s not in self.constant_table:
                self.constant_table[s] = (self.cur_func, self.constant_count)
                self.constant_count += 1
            return 'LC' + str(self.constant_table[s][1])
        return node.value

    def visit_ID(self, node):
        return node.name

    def visit_Return(self, node):
        self._emit('return', None, None, self.visit(node.expr))
