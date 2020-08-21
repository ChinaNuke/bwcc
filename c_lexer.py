# ------------------------------------------------
# bwcc: c_lexer.py
#
# CLexer class: C语言的词法分析器
# ------------------------------------------------
from ply import lex
from ply.lex import TOKEN


class CLexer(object):
    """ 词法分析器，完成对C语言输入的词法分析。

    调用input()设定需要进行词法分析的字符串，调用build()构建词法分析器，调用token()
    获得下一个识别到的token。

    Attributes:
        last_token: 词法分析器识别到的最后一个token
    """

    def __init__(self, error_func, on_lbrace_func, on_rbrace_func, 
                 type_lookup_func):
        """ 创建 CLexer 对象。

        Args:
            error_func: 供词法分析遇到错误时调用的函数
            on_lbrace_func, on_rbrace_func: 遇到LBRACE或RBRACE时调用的函数，
                用于动态调整当前所在的范围。
            type_lookup_func: 查看字符串是否已通过typedef定义过，如已定义过，
                则返回True.
        """
        self.error_func = error_func
        self.on_lbrace_func = on_lbrace_func
        self.on_rbrace_func = on_rbrace_func
        self.type_lookup_func = type_lookup_func
        # self.filename = ''

        # 保存从 self.token() 返回的最后一个token
        self.last_token = None

    def build(self, **kwargs):
        """ 构建词法分析器，必须在创建对象后调用
        """
        self.lexer = lex.lex(module=self, **kwargs)

    def input(self, text):
        self.lexer.input(text)

    def token(self):
        self.last_token = self.lexer.token()
        return self.last_token

    def token_column(self, token):
        """ 查找token所在的列，用于报告错误位置
        """
        last_cr = self.lexer.lexdata.rfind('\n', 0, token.lexpos)
        return token.lexpos - last_cr

    #################### PRIVATE ####################

    def _error(self, msg, token):
        """ 调用语法分析器的出错处理方法进行出错处理。
        """
        location = (token.lineno, self.token_column(token))
        self.error_func(msg, location[0], location[1])
        self.lexer.skip(1)  # 跳过出错的字符继续向前分析

    # C11关键字（部分）
    # 参考自 https://en.cppreference.com/w/c/keyword
    #
    keywords = (
        'AUTO', 'BREAK', 'CHAR', 'CONST', 'CONTINUE', 'DO', 'DOUBLE', 
        'ELSE', 'ENUM', 'EXTERN', 'FLOAT', 'FOR', 'IF', 'INT', 'LONG',
        'REGISTER', 'RETURN', 'SHORT', 'SIGNED', 'STATIC', 'STRUCT',
        'TYPEDEF', 'UNSIGNED', 'VOID', 'VOLATILE', 'WHILE'
    )

    keyword_map = {keyword.lower(): keyword for keyword in keywords}

    # 可识别的所有 TOKENS
    #
    tokens = keywords + (
        # 标识符
        'ID',

        # 使用typedef定义的类型ID
        'TYPEID',

        # 常量
        'INT_CONST', 'FLOAT_CONST', 'CHAR_CONST',

        # 字符串
        'STRING_LITERAL',

        # 运算符
        'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MOD', 'OR', 'AND',
        'NOT', 'XOR', 'LSHIFT', 'RSHIFT', 'LOR', 'LAND', 'LNOT',
        'LT', 'LE', 'GT', 'GE', 'EQ', 'NE', 'PLUSPLUS', 'MINUSMINUS',

        # 赋值符号
        'EQUALS', 'PLUSEQUAL', 'MINUSEQUAL', 'TIMESEQUAL', 'DIVEQUAL',
        'MODEQUAL', 'LSHIFTEQUAL', 'RSHIFTEQUAL', 'ANDEQUAL',
        'OREQUAL', 'XOREQUAL',

        'ARROW',

        # 条件运算符（?）
        'CONDOP',

        # 分隔符
        'LPAREN', 'RPAREN',         # ( )
        'LBRACKET', 'RBRACKET',     # [ ]
        'LBRACE', 'RBRACE',         # { }
        'COMMA', 'PERIOD',          # , .
        'SEMI', 'COLON'             # ; :
    )

    ##
    ## 正则匹配规则
    ##

    # 标识符
    identifier = r'[a-zA-Z_][0-9a-zA-Z_]*'

    # 整数常量（只考虑十进制）
    integer_suffix_opt = r'(([uU]ll)|([uU]LL)|(ll[uU]?)|(LL[uU]?)|([uU][lL])|([lL][uU]?)|[uU])?'
    decimal_constant = '(0'+integer_suffix_opt+')|([1-9][0-9]*'+integer_suffix_opt+')'

    # 浮点数常量
    exponent_part = r'([eE][-+]?[0-9]+)'
    fractional_constant = r'([0-9]*\.[0-9]+)|([0-9]+\.)'
    floating_constant = '(((('+fractional_constant+')' + \
        exponent_part+'?)|([0-9]+'+exponent_part+'))[FfLl]?)'

    # 字符
    char_const = r"'[^'\\\n]'"
    bad_char_const = r"''"

    # escape_sequence_start_in_string = r"""(\\[0-9a-zA-Z._~!=&\^\-\\?'"])"""
    # string_char = r"""([^"\\\n]|""" + escape_sequence_start_in_string + ')'
    # string_literal = '"' + string_char + '*"'

    # 字符串（未考虑转义）
    # string_literal = r'"[^"\\\n]*"'
    string_literal = r'"[^"]*"'

    ##
    ## TOKEN识别规则
    ##

    # 忽略空格和TAB
    t_ignore = ' \t'

    # 换行
    def t_NEWLINE(self, t):
        r'\n+'
        t.lexer.lineno += t.value.count("\n")

    # 运算符
    t_PLUS = r'\+'
    t_MINUS = r'-'
    t_TIMES = r'\*'
    t_DIVIDE = r'/'
    t_MOD = r'%'
    t_OR = r'\|'
    t_AND = r'&'
    t_NOT = r'~'
    t_XOR = r'\^'
    t_LSHIFT = r'<<'
    t_RSHIFT = r'>>'
    t_LOR = r'\|\|'
    t_LAND = r'&&'
    t_LNOT = r'!'
    t_LT = r'<'
    t_GT = r'>'
    t_LE = r'<='
    t_GE = r'>='
    t_EQ = r'=='
    t_NE = r'!='
    t_PLUSPLUS = r'\+\+'
    t_MINUSMINUS = r'--'

    # 赋值符号
    t_EQUALS = r'='
    t_TIMESEQUAL = r'\*='
    t_DIVEQUAL = r'/='
    t_MODEQUAL = r'%='
    t_PLUSEQUAL = r'\+='
    t_MINUSEQUAL = r'-='
    t_LSHIFTEQUAL = r'<<='
    t_RSHIFTEQUAL = r'>>='
    t_ANDEQUAL = r'&='
    t_OREQUAL = r'\|='
    t_XOREQUAL = r'\^='

    t_ARROW = r'->'

    # 条件运算符
    t_CONDOP = r'\?'

    # 分隔符
    t_LPAREN = r'\('
    t_RPAREN = r'\)'
    t_LBRACKET = r'\['
    t_RBRACKET = r'\]'
    t_COMMA = r','
    t_PERIOD = r'\.'
    t_SEMI = r';'
    t_COLON = r':'

    @TOKEN(r'\{')
    def t_LBRACE(self, t):
        self.on_lbrace_func()
        return t

    @TOKEN(r'\}')
    def t_RBRACE(self, t):
        self.on_rbrace_func()
        return t

    t_STRING_LITERAL = string_literal

    @TOKEN(floating_constant)
    def t_FLOAT_CONST(self, t):
        return t

    @TOKEN(decimal_constant)
    def t_INT_CONST(self, t):
        return t

    @TOKEN(char_const)
    def t_CHAR_CONST(self, t):
        return t

    @TOKEN(bad_char_const)
    def t_BAD_CHAR_CONST(self, t):
        msg = "非法的字符常量 %s" % t.value
        self._error(msg, t)

    @TOKEN(identifier)
    def t_ID(self, t):
        t.type = self.keyword_map.get(t.value, "ID")
        if t.type == 'ID' and self.type_lookup_func(t.value):
            t.type = 'TYPEID'
        return t

    def t_error(self, t):
        msg = "非法的字符 '%s'" % t.value[0]
        self._error(msg, t)
