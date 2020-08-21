# ------------------------------------------------
# bwcc: c_parser.py
#
# CParser class: 语法分析，同时构造抽象语法树
# ------------------------------------------------
from ply import yacc
import c_ast
from c_lexer import CLexer
from utils import BaseParser, Coord, ParseError


class CParser(BaseParser):
    """ 语法分析器，生成抽象语法树。

    调用 parse() 对文本进行语法分析，获得抽象语法树。返回值是一个包含若干个
    翻译单元的列表。

    Attributes:

    """
    def __init__(self, lex_optimize=False, yacc_optimize=False):
        """ 创建 CParser 对象并初始化。
        """
        self.clex = CLexer(
            error_func = self._lex_error_func,
            on_lbrace_func = self._lex_on_lbrace_func,
            on_rbrace_func = self._lex_on_rbrace_func,
            type_lookup_func = self._lex_type_lookup_func)

        self.clex.build(optimize=lex_optimize)

        # TODO: 这个好像没有用到
        self.tokens = self.clex.tokens
        
        # 在此列表中的规则会自动生成一条后缀为 _opt 的规则
        # 
        rules_with_opt = [
            'assignment_expression',
            'declaration_list',
            'expression',
            'identifier_list',
            'init_declarator_list',
            'initializer_list',
            'block_item_list',
            'type_qualifier_list',
            'declaration_specifiers'
        ]

        for rule in rules_with_opt:
            self._create_opt_rule(rule)
             
        self.cparser = yacc.yacc(module=self, start='translation_unit_or_empty',
                                 debug=True,optimize=yacc_optimize)

        # 名称范围栈
        # 如果 _scope_stack[n][name]为True，则 name 在当前范围内被定义为 type
        # 如果为 False，则 name 在当前范围内被定义为 identifier
        # 如果不存在，则 name 未在此范围内定义
        # _scope_stack[-1] 表示当前所在的范围
        self._scope_stack = [dict()]

    def parse(self, text, filename=''):
        """ 解析C语言代码并生成抽象语法树
        """
        self.clex.filename = filename
        return self.cparser.parse(input=text, lexer=self.clex)

    #################### PRIVATE ####################

    def _push_scope(self):
        self._scope_stack.append(dict())

    def _pop_scope(self):
        assert len(self._scope_stack) > 1
        self._scope_stack.pop()

    def _add_typedef_name(self, name, coord):
        """ 在当前范围内将 name 添加为一个 typedef_name。
        """
        # 只有 name 在当前范围内没有定义或者已定义为 type 时才可以定义
        # 若在此范围内已定义其为 identifier，则不能再定义为 type
        # 
        if not self._scope_stack[-1].get(name, True):
            self._parse_error("%r在此范围内已被定义为identifier，"
                "不能再被定义为type" % name, coord)
        self._scope_stack[-1][name] = True

    def _add_identifier(self, name, coord):
        """ 在当前范围内将 name 添加为一个 identifier。
        """
        # 只有name在当前范围内没有定义或者已定义为identifier时才可以定义
        # 若在此范围内已定义其为type，则不能再定义为identifier
        # 
        if self._scope_stack[-1].get(name, False):
            self._parse_error("%r在此范围内已被定义为type，"
                "不能再被定义为identifier" % name, coord)
        self._scope_stack[-1][name] = False

    def _is_type_in_scope(self, name):
        """ 判断name是否在 scope 中已被定义为 type 
        """
        for scope in reversed(self._scope_stack):
            # 如果在多个范围内都定义过则根据所在最近的范围判断
            in_scope = scope.get(name)
            if in_scope is not None: return in_scope
        return False

    def _lex_on_lbrace_func(self):
        self._push_scope()

    def _lex_on_rbrace_func(self):
        self._pop_scope()

    def _lex_type_lookup_func(self, name):
        return self._is_type_in_scope(name)

    def _lex_error_func(self, msg, line, column):
        self._parse_error(msg, self._coord(line, column))

    def _get_lookahead_token(self):
        return self.clex.last_token

    def _type_modify_decl(self, decl, modifier):
        """ 修改 declaration 的修饰符。

        declaration 是一个结点链的结构，TypeDecl 在链的最末端，而修饰它的内容都在
        它的前面。
        此函数将新的 modifier 插入到原先的 modifiers 末尾，即 TypeDecl 的前面。

        NOTE: 函数可能会修改 decl 和 modifier

        Args:
            decl: 可能是一个 TypeDecl，也可能是一个已经被修饰的结点链
            modifier: 修饰符，如 ArrayDecl， FuncDecl等

        Returns:
            修改后的 declaration 结点链。
        """
        modifier_head = modifier
        modifier_tail = modifier

        while modifier_tail.type:
            modifier_tail = modifier_tail.type

        if isinstance(decl, c_ast.TypeDecl):
            modifier_tail.type = decl
            return modifier
        else:
            decl_tail = decl

            while not isinstance(decl_tail.type, c_ast.TypeDecl):
                decl_tail = decl_tail.type

            # 把modifier的修饰词插到decl原来的修饰词末尾
            # 
            modifier_tail.type = decl_tail.type
            decl_tail.type = modifier_head
            return decl

    def _fix_decl_name_type(self, decl, typename):
        """ 修正 declaration.

        因为 type 是在最外层识别的，所以最内层的 TypeDecl 并没有 type.
        同时声明的 name 位于最内层的 TypeDecl 中,因此整个 declaration 没有 name.
        这个函数是主要为了解决这两个问题。

        Args:
            decl: 以 Typedef 或 Decl 为首的结点链
            typename: 包含一个或多个 type-specifier 结点的列表，可以是一个
                IdentifierType，Enum 或 Struct

        Returns:
            修正后的 declaration
        """
        # 获取最内层的 TypeDecl
        # 
        type = decl.type
        while not isinstance(type, c_ast.TypeDecl):
            type = type.type

        decl.name = type.declname
        type.quals = decl.quals

        # 只允许多个 IdentifierType
        # 或者单个 其它Type
        # 比如，不允许出现 int enum ..
        # 
        for tn in typename:
            if not isinstance(tn, c_ast.IdentifierType):
                if len(typename) > 1:
                    self._parse_error('不合法的多类型说明', tn.coord)
                else:
                    type.type = tn
                    return decl
        
        if not typename:
            # 函数声明可以不写 type，缺省值为 int
            # 
            if isinstance(decl.type, c_ast.FuncDecl):
                type.type = c_ast.IdentifierType(['int'], coord=decl.coord)
            else:
                self._parse_error('声明中缺少类型', decl.coord)
        else:
            # 将多个类型名合并成一个 IdentifierType 结点
            # 
            type.type = c_ast.IdentifierType(
                [name for id in typename for name in id.names],
                coord=typename[0].coord
            )
        return decl    

    def _add_declaration_specifier(self, declspec, newspec, kind, append=False):
        spec = declspec or dict(qual=[], storage=[], type=[], function=[])
        spec[kind].append(newspec) if append else spec[kind].insert(0, newspec)
        return spec

    def _build_declarations(self, spec, decls, typedef_namespace=False):
        """ 构建 declarations.

        Args:
            spec: 一个 dict: {qual=[], storage=[], type=[], function=[]}
                来自 declaration_specifiers
            decls: dict 列表：[{decl=, init=}]，来自 init_declarator_list
            typedef_namespace:

        Returns:
            构建好的 declarations 列表，元素为 Typedef 或 Decl.
        """
        is_typedef = 'typedef' in spec['storage']
        declarations = []

        for decl in decls:
            assert decl['decl'] is not None
            if is_typedef:
                declaration = c_ast.Typedef(
                    name=None,
                    quals=spec['qual'],
                    storage=spec['storage'],
                    type=decl['decl'],
                    coord=decl['decl'].coord
                )
            else:
                declaration = c_ast.Decl(
                    name=None,
                    quals=spec['qual'],
                    storage=spec['storage'],
                    funcspec=spec['function'],
                    type=decl['decl'],
                    init = decl.get('init'),
                    bitsize=None,   # TODO: Parser全部测试完成后删除此参数
                    coord=decl['decl'].coord
                )

            if isinstance(declaration.type, 
                          (c_ast.Struct, c_ast.IdentifierType)):
                fixed_decl = declaration
            else:
                fixed_decl = self._fix_decl_name_type(declaration, spec['type'])

            # 添加到 scope 中，在语法分析器中使用
            # 
            if typedef_namespace:
                if is_typedef:
                    self._add_typedef_name(fixed_decl.name, fixed_decl.coord)
                else:
                    self._add_identifier(fixed_decl.name, fixed_decl.coord)

            declarations.append(fixed_decl)

        return declarations

    def _build_function_definition(self, spec, decl, param_decls, body):
        """ 构建函数定义。

        Args:
            spec: 函数类型说明
            decl: 函数声明
            param_decls:
            body: 函数体

        Returns:
            一个 FuncDef 结点。
        """
        declaration = self._build_declarations(
            spec=spec,
            decls=[dict(decl=decl, init=None)],
            typedef_namespace=True
        )[0]

        return c_ast.FuncDef(
            decl=declaration,
            param_decls=param_decls,
            body=body,
            coord=decl.coord
        )

    # 规定运算符的优先级和结合性（升序）
    # 参考 https://zh.cppreference.com/w/c/language/operator_precedence
    #
    precedence = (
        ('left', 'LOR'),
        ('left', 'LAND'),
        ('left', 'OR'),
        ('left', 'XOR'),
        ('left', 'AND'),
        ('left', 'EQ', 'NE'),
        ('left', 'GT', 'GE', 'LT', 'LE'),
        ('left', 'RSHIFT', 'LSHIFT'),
        ('left', 'PLUS', 'MINUS'),
        ('left', 'TIMES', 'DIVIDE', 'MOD')
    )

    # 文法规则
    #
    '''

    # def p_function_specifier(self, p):

    def p_type_name(self, p):
        """ type_name   : specifier_qualifier_list abstract_declarator_opt """
        typename = c_ast.Typename(
            name='',
            quals=p[1]['qual'],
            type=p[2] or c_ast.TypeDecl(None, None, None),
            coord=self._token_coord(p, 2)
        )
        p[0] = self._fix_decl_name_type(typename, p[1]['type'])

    def p_abstract_declarator_1(self, p):
        """ abstract_declarator : pointer """
        p[0] = self._type_modify_decl(
            decl=c_ast.TypeDecl(None, None, None),
            modifier=p[1]
        )

    def p_abstract_declarator_2(self, p):
        """ abstract_declarator : pointer direct_abstract_declarator """
        p[0] = self._type_modify_decl(p[2], p[1])

    def p_abstract_declarator_3(self, p):
        """ abstract_declarator : direct_abstract_declarator """
        p[0] = p[1]

    def p_direct_abstract_declarator_1(self, p):
        """ direct_abstract_declarator  : LPAREN abstract_declarator RPAREN """
        p[0] = p[2]

    def p_direct_abstract_declarator_2(self, p):
        """ direct_abstract_declarator  : direct_abstract_declarator LBRACKET assignment_expression_opt RBRACKET """
        arr = c_ast.ArrayDecl(
            type=None,
            dim=p[3],
            # dim_quals=[],
            coord=p[1].coord
        )
        p[0] = self._type_modify_decl(p[1], arr)

    def p_direct_abstract_declarator_3(self, p):
        """ direct_abstract_declarator  : LBRACKET type_qualifier_list_opt assignment_expression_opt RBRACKET """
        quals = p[2] or []
        p[0] = c_ast.ArrayDecl(
            type=c_ast.TypeDecl(None, None, None),
            dim=p[3],
            # dim_quals=quals,
            coord=self._token_coord(p, 1)
        )

    def p_direct_abstract_declarator_4(self, p):
        """ direct_abstract_declarator  : direct_abstract_declarator LBRACKET TIMES RBRACKET """
        arr = c_ast.ArrayDecl(
            type=None,
            dim=c_ast.ID(p[3], self._token_coord(p, 3)),
            dim_quals=[],
            coord=p[1].coord
        )
        p[0] = self._type_modify_decl(decl=p[1], modifier=arr)

    def p_direct_abstract_declarator_5(self, p):
        """ direct_abstract_declarator  : LBRACKET TIMES RBRACKET """
        p[0] = c_ast.ArrayDecl(
            type=c_ast.TypeDecl(None, None, None),
            dim=c_ast.ID(p[3], self._token_coord(p, 3)),
            coord=self._token_coord(p, 1)
        )

    def p_direct_abstract_declarator_6(self, p):
        """ direct_abstract_declarator  : direct_abstract_declarator LPAREN parameter_type_list_opt RPAREN """
        func = c_ast.FuncDecl(
            args=p[3],
            type=None,
            coord=p[1].coord
        )
        p[0] = self._type_modify_decl(p[1], func)

    def p_direct_abstract_declarator_7(self, p):
        """ direct_abstract_declarator  : LPAREN parameter_type_list_opt RPAREN """
        p[0] = c_ast.FuncDecl(
            args=p[2],
            type=c_ast.TypeDecl(None, None, None),
            coord=self._token_coord(p, 1)
        )



    '''

    ###### external deinitions 部分 ######
    def p_translation_unit_or_empty(self, p):
        """ translation_unit_or_empty   : translation_unit
                                        | empty
        """
        if p[1] is None:
            p[0] = c_ast.FileAST([])
        else:
            p[0] = c_ast.FileAST(p[1])

    def p_translation_unit(self, p):
        """ translation_unit    : external_declaration
                                | translation_unit external_declaration
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[1].extend(p[2])
            p[0] = p[1]

    def p_external_declaration_1(self, p):
        """ external_declaration    : function_defination """
        p[0] = [p[1]]

    def p_external_declaration_2(self, p):
        """ external_declaration    : declaration """
        p[0] = p[1]

    def p_function_defination(self, p):
        """ function_defination     : declaration_specifiers declarator declaration_list_opt compound_statement
        """
        spec = p[1]

        p[0] = self._build_function_definition(
            spec=spec,
            decl=p[2],
            param_decls=p[3],
            body=p[4])

    # NOTE: declaration 本身就是列表
    # 
    def p_declaration_list(self, p):
        """ declaration_list    : declaration
                                | declaration_list declaration
        """
        p[0] = p[1] if len(p) == 2 else p[1] + p[2]

    ###### statement 部分 ######

    # 不考虑 labeled 语句
    # 不考虑 switch 语句

    def p_statement(self, p):
        """ statement   : expression_statement
                        | compound_statement
                        | selection_statement
                        | iteration_statement
                        | jump_statement
        """
        p[0] = p[1]

    def p_compound_statement(self, p):
        """ compound_statement  : brace_open block_item_list_opt brace_close """
        p[0] = c_ast.Compound(block_items=p[2], coord=self._token_coord(p, 1))

    def p_block_item_list(self, p):
        """ block_item_list : block_item
                            | block_item_list block_item
        """
        if len(p) == 3: assert p[2] != [None]   # TODO: 测试用代码，完成后移除
        
        p[0] = p[1] if (len(p) == 2 or p[2] == [None]) else p[1] + p[2]

    def p_block_item(self, p):
        """ block_item  : declaration
                        | statement
        """
        p[0] = p[1] if isinstance(p[1], list) else [p[1]]

    def p_expression_statement(self, p):
        """ expression_statement    : expression_opt SEMI """
        if p[1] is None:
            p[0] = c_ast.EmptyStatement(self._token_coord(p, 2))
        else:
            p[0] = p[1]

    def p_selection_statement_1(self, p):
        """ selection_statement : IF LPAREN expression RPAREN statement """
        p[0] = c_ast.If(p[3], p[5], None, self._token_coord(p, 1))

    def p_selection_statement_2(self, p):
        """ selection_statement : IF LPAREN expression RPAREN statement ELSE statement """
        p[0] = c_ast.If(p[3], p[5], p[7], self._token_coord(p, 1))

    def p_iteration_statement_1(self, p):
        """ iteration_statement : WHILE LPAREN expression RPAREN statement """
        p[0] = c_ast.While(p[3], p[5], self._token_coord(p, 1))

    def p_iteration_statement_2(self, p):
        """ iteration_statement : DO statement WHILE LPAREN expression RPAREN SEMI """
        p[0] = c_ast.DoWhile(p[5], p[2], self._token_coord(p, 1))

    def p_iteration_statement_3(self, p):
        """ iteration_statement : FOR LPAREN expression_opt SEMI expression_opt SEMI expression_opt RPAREN statement """
        p[0] = c_ast.For(p[3], p[5], p[7], p[9], self._token_coord(p, 1))

    def p_iteration_statement_4(self, p):
        """ iteration_statement : FOR LPAREN declaration expression_opt SEMI expression_opt RPAREN statement """
        p[0] = c_ast.For(c_ast.DeclList(p[3], self._token_coord(p, 1)),
                         p[4], p[6], p[8], self._token_coord(p, 1))

    def p_jump_statement_1(self, p):
        """ jump_statement  : BREAK SEMI """
        p[0] = c_ast.Break(self._token_coord(p, 1))

    def p_jump_statement_2(self, p):
        """ jump_statement  : CONTINUE SEMI """
        p[0] = c_ast.Continue(self._token_coord(p, 1))

    def p_jump_statement_3(self, p):
        """ jump_statement  : RETURN expression SEMI
                            | RETURN SEMI
        """
        p[0] = c_ast.Return(p[2] if len(p) == 4 else None, 
                            self._token_coord(p, 1))

    ###### declaration 部分 ######

    # 不考虑 init_declarator_list 为空的情况
    # NOTE: declaration 是一个列表
    # 
    def p_declaration(self, p):
        """ declaration : declaration_specifiers init_declarator_list SEMI """
        spec = p[1]

        decls = self._build_declarations(
            spec=spec, decls=p[2], 
            typedef_namespace=True)
        p[0] = decls

    def p_init_declarator_list(self, p):
        """ init_declarator_list    : init_declarator
                                    | init_declarator_list COMMA init_declarator
        """
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

    # init_declarator 是一个 dict
    # 
    def p_init_declarator(self, p):
        """ init_declarator : declarator
                            | declarator EQUALS initializer
        """
        p[0] = dict(decl=p[1], init=(p[3] if len(p) == 4 else None))


    ###### declarator 部分 ######

    def p_declarator(self, p):
        """ declarator  : direct_declarator
                        | pointer direct_declarator
        """
        p[0] = p[1] if len(p) == 2 else self._type_modify_decl(p[2], p[1])
    
    def p_direct_declarator_1(self, p):
        """ direct_declarator   : ID """
        p[0] = c_ast.TypeDecl(
            declname=p[1],
            type=None,
            quals=None,
            coord=self._token_coord(p, 1))

    def p_direct_declarator_2(self, p):
        """ direct_declarator   : LPAREN declarator RPAREN """
        p[0] = p[2]

    def p_direct_declarator_3(self, p):
        """ direct_declarator   : direct_declarator LBRACKET type_qualifier_list_opt assignment_expression_opt RBRACKET """
        arr = c_ast.ArrayDecl(
            type=None,
            dim=p[4],
            dim_quals=p[3] or [],
            coord=p[1].coord)

        p[0] = self._type_modify_decl(decl=p[1], modifier=arr)
    
    def p_direct_declarator_4(self, p):
        """ direct_declarator   : direct_declarator LBRACKET STATIC type_qualifier_list assignment_expression RBRACKET
                                | direct_declarator LBRACKET type_qualifier_list STATIC assignment_expression RBRACKET
        """
        dim_quals = p[3] + [p[4]] if isinstance(p[3], list) else p[4] + [p[3]]
        arr = c_ast.ArrayDecl(
            type=None,
            dim=p[5],
            dim_quals=dim_quals,
            coord=p[1].coord)

        p[0] = self._type_modify_decl(decl=p[1], modifier=arr)

    def p_direct_declarator_6(self, p):
        """ direct_declarator   : direct_declarator LPAREN identifier_list_opt RPAREN
                                | direct_declarator LPAREN parameter_type_list RPAREN
        """
        func = c_ast.FuncDecl(args=p[3], type=None, coord=p[1].coord)

        # TODO: 可以考虑移除此部分

        if self._get_lookahead_token().type == "LBRACE":
            if func.args is not None:
                for param in func.args.params:
                    self._add_identifier(param.name, param.coord)

        p[0] = self._type_modify_decl(decl=p[1], modifier=func)

    def p_identifier_list(self, p):
        """ identifier_list : identifier
                            | identifier_list COMMA identifier
        """
        if len(p) == 2:
            p[0] = c_ast.ParamList([p[1]], p[1].coord)
        else:
            p[1].params.append(p[3])
            p[0] = p[1]

    # 形参列表，函数声明时使用
    # 
    def p_parameter_type_list(self, p):
        """ parameter_type_list : parameter_list """
        p[0] = p[1]

    def p_parameter_list(self, p):
        """ parameter_list  : parameter_declaration
                            | parameter_list COMMA parameter_declaration
        """
        if len(p) == 2:
            p[0] = c_ast.ParamList([p[1]], p[1].coord)
        else:
            p[1].params.append(p[3])
            p[0] = p[1]

    def p_parameter_declaration_1(self, p):
        """ parameter_declaration   : declaration_specifiers declarator
        """
        spec = p[1]

        # 形参缺省类型为 int
        # 
        if not spec['type']:
            spec['type'] = [c_ast.IdentifierType(['int'], 
                           coord=self._token_coord(p, 1))]
        
        # _build_declarations() 函数返回一个 list
        # 而此处只涉及一个 declaration 
        p[0] = self._build_declarations(spec=spec, decls=[dict(decl=p[2])])[0]

    # TODO

    # def p_parameter_declaration_2(self, p):
    #     """ parameter_declaration   : declaration_specifiers abstract_declarator_opt """
    #     if not spec['type']:
    #         spec['type'] = [c_ast.IdentifierType(
    #             ['int'], coord=self._token_coord(p, 1))]
    #         #

    # 需要注意的是，declaration_specifiers 是一个 dict
    # 而不是像其它的非终结符一样是一个 Node
    # 
    def p_declaration_specifiers_1(self, p):
        """ declaration_specifiers  : storage_class_specifier declaration_specifiers_opt """
        p[0] = self._add_declaration_specifier(p[2], p[1], 'storage')

    def p_declaration_specifiers_2(self, p):
        """ declaration_specifiers  : type_specifier declaration_specifiers_opt """
        p[0] = self._add_declaration_specifier(p[2], p[1], 'type')

    def p_declaration_specifiers_3(self, p):
        """ declaration_specifiers  : type_qualifier declaration_specifiers_opt """
        p[0] = self._add_declaration_specifier(p[2], p[1], 'qual')
  
    # 例如 char * const * p，意为 pointer to const pointer to char
    # char ** const p，意为 const pointer to pointer to char
    # 所以，最前面的 pointer 应该在最内层
    # 
    def p_pointer(self, p):
        """ pointer : TIMES type_qualifier_list_opt
                    | TIMES type_qualifier_list_opt pointer
        """
        nested = c_ast.PtrDecl(
            quals=p[2] or [],
            type=None,
            coord=self._token_coord(p, 1)
        )
        if len(p) > 3:
            tail_type = p[3]
            while tail_type.type is not None:
                tail_type = tail_type.type
            tail_type.type = nested
            p[0] = p[3]
        else:
            p[0] = nested

    def p_type_qualifier_list(self, p):
        """ type_qualifier_list : type_qualifier
                                | type_qualifier_list type_qualifier
        """
        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[2]]

    def p_type_qualifier(self, p):
        """ type_qualifier  : CONST
                            | VOLATILE
        """
        p[0] = p[1]

    def p_storage_class_specifier(self, p):
        """ storage_class_specifier : AUTO
                                    | REGISTER
                                    | STATIC
                                    | EXTERN
                                    | TYPEDEF
        """
        p[0] = p[1]

    # 不考虑 Union
    # 
    def p_type_specifier(self, p):
        """ type_specifier  : type_specifier_simple
                            | enum_specifier
                            | struct_specifier
        """
        p[0] = p[1]

    def p_type_specifier_simple(self, p):
        """ type_specifier_simple       : VOID
                                        | CHAR
                                        | SHORT
                                        | INT
                                        | LONG
                                        | FLOAT
                                        | DOUBLE
                                        | SIGNED
                                        | UNSIGNED
                                        | TYPEID
        """
        p[0] = c_ast.IdentifierType([p[1]], coord=self._token_coord(p, 1))


    ###### enum 部分 ######

    def p_enum_specifier_1(self, p):
        """ enum_specifier  : ENUM ID """
        p[0] = c_ast.Enum(p[2], None, self._token_coord(p, 1))

    def p_enum_specifier_2(self, p):
        """ enum_specifier  : ENUM brace_open enumerator_list brace_close
        """
        p[0] = c_ast.Enum(None, p[3], self._token_coord(p, 1))

    def p_enum_specifier_3(self, p):
        """ enum_specifier  : ENUM ID brace_open enumerator_list brace_close
        """
        p[0] = c_ast.Enum(p[2], p[4], self._token_coord(p, 1))

    def p_enumerator_list(self, p):
        """ enumerator_list : enumerator
                            | enumerator_list COMMA
                            | enumerator_list COMMA enumerator
        """
        if len(p) == 2:
            p[0] = c_ast.EnumeratorList([p[1]], p[1].coord)
        elif len(p) == 3:
            p[0] = p[1]
        else:
            p[1].enumerators.append(p[3])
            p[0] = p[1]

    def p_enumerator(self, p):
        """ enumerator  : ID
                        | ID EQUALS constant_expression
        """
        if len(p) == 2:
            enumerator = c_ast.Enumerator(
                        p[1], None,
                        self._token_coord(p, 1))
        else:
            enumerator = c_ast.Enumerator(
                        p[1], p[3],
                        self._token_coord(p, 1))
        
        # 在当前范围内将其声明为 identifier，防止后续出现重复的名字
        self._add_identifier(enumerator.name, enumerator.coord)

        p[0] = enumerator


    ###### struct 部分 ######

    def p_struct_specifier_1(self, p):
        """ struct_specifier    : STRUCT ID
        """
        p[0] = c_ast.Struct(
            name=p[2], 
            decls=None,
            coord=self._token_coord(p, 2)
        )

    def p_struct_specifier_2(self, p):
        """ struct_specifier    : STRUCT brace_open struct_declaration_list brace_close
        """
        p[0] = c_ast.Struct(
            name=None, 
            decls=p[3],
            coord=self._token_coord(p, 2)
        )

    def p_struct_specifier_3(self, p):
        """ struct_specifier    : STRUCT ID brace_open struct_declaration_list brace_close
        """
        p[0] = c_ast.Struct(
            name=p[2],
            decls=p[4],
            coord=self._token_coord(p, 2)
        )

    def p_struct_declaration_list(self, p):
        """ struct_declaration_list : struct_declaration
                                    | struct_declaration_list struct_declaration
        """
        if len(p) == 2:
            p[0] = p[1] or []
        else:
            p[0] = p[1] + (p[2] or [])

    # 一个 list 或 None
    # 
    def p_struct_declaration(self, p):
        """ struct_declaration  : specifier_qualifier_list struct_declarator_list SEMI
        """
        spec = p[1]
        assert 'typedef' not in spec['storage']
        #
        # TODO 这块给写漏了

    # specifier-qualifier-list 是一个 dict，
    # dict 中包含 quals，storage，type 三个 list
    # specifier-qualifier-list 至少要包含一个 type-specifier
    # [!] 第一条的意义尚不明确
    # 
    def p_specifier_qualifier_list_1(self, p):
        """ specifier_qualifier_list    : specifier_qualifier_list type_specifier """
        p[0] = p[1].type.append(p[2])
        # p[0] = self._add_declaration_specifier(p[1], p[2], 'type', append=True)

    def p_specifier_qualifier_list_2(self, p):
        """ specifier_qualifier_list    : specifier_qualifier_list type_qualifier """
        p[0] = p[1].qual.append(p[2])
        # p[0] = self._add_declaration_specifier(p[1], p[2], 'qual', append=True)

    def p_specifier_qualifier_list_3(self, p):
        """ specifier_qualifier_list    : type_specifier """
        p[0] = dict(qual=[], sotrage=[], type=[p[1]], function=[])
        # p[0] = self._add_declaration_specifier(None, p[1], 'type')

    def p_specifier_qualifier_list_4(self, p):
        """ specifier_qualifier_list    : type_qualifier_list type_specifier """
        p[0] = dict(qual=[p[1]], sotrage=[], type=[p[1]], function=[])
        # p[0] = self._add_declaration_specifier(
        #     declspec=dict(qual=p[1], storage=[], type=[], function=[]),
        #     newspec=p[2],
        #     kind='type',
        #     append=True
        # )

    def p_struct_declarator_list(self, p):
        """ struct_declarator_list  : struct_declarator
                                    | struct_declarator COMMA struct_declarator
        """
        p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]

    # 不考虑 bit fields
    # 
    def p_struct_declarator(self, p):
        """ struct_declarator   : declarator """
        p[0] = p[1]


    # def p_typedef_name(self, p):
    #     """ typedef_name    : TYPEID """
    #     p[0] = c_ast.IdentifierType([p[1]], coord=self._token_coord(p, 1))

    
    ###### initializer部分 ######

    # 不考虑designator
    # 
    def p_initializer_1(self, p):
        """ initializer : assignment_expression """
        p[0] = p[1]

    def p_initializer_2(self, p):
        """ initializer : brace_open initializer_list_opt brace_close
                        | brace_open initializer_list COMMA brace_close
        """
        if p[2] is None:
            p[0] = c_ast.InitList([], self._token_coord(p, 1))
        else:
            p[0] = p[2]

    def p_initializer_list(self, p):
        """ initializer_list    : initializer
                                | initializer_list COMMA initializer
        """
        if len(p) == 2:
            p[0] = c_ast.InitList([p[1]], p[1].coord)
        else:
            p[1].exprs.append(p[3])
            p[0] = p[1]


    ###### expression 部分 ######

    def p_constant_expression(self, p):
        """ constant_expression : conditional_expression """
        p[0] = p[1]

    # 表达式
    # 例如  a = 1
    # 或    a = 1, b = 2, c
    # 
    def p_expression(self, p):
        """ expression  : assignment_expression
                        | expression COMMA assignment_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            if not isinstance(p[1], c_ast.ExprList):
                p[1] = c_ast.ExprList([p[1]], p[1].coord)
            p[1].exprs.append(p[3])
            p[0] = p[1]

    # 赋值表达式（优先级14）
    # C语言标准规定，赋值运算符的左运算数必须是一元（第 2 级非转型）表达式。
    # 
    def p_assignment_expression(self, p):
        """ assignment_expression   : conditional_expression
                                    | unary_expression assignment_operator assignment_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = c_ast.Assignment(p[2], p[1], p[3], p[1].coord)

    # 赋值运算符
    # 
    def p_assignment_operator(self, p):
        """ assignment_operator : EQUALS
                                | XOREQUAL
                                | TIMESEQUAL
                                | DIVEQUAL
                                | MODEQUAL
                                | PLUSEQUAL
                                | MINUSEQUAL
                                | LSHIFTEQUAL
                                | RSHIFTEQUAL
                                | ANDEQUAL
                                | OREQUAL
        """
        p[0] = p[1]

    # 三元条件表达式（优先级13）
    # 例如：a > b ? a : b
    # 
    def p_conditional_expression(self, p):
        """ conditional_expression  : binary_expression
                                    | binary_expression CONDOP expression COLON conditional_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = c_ast.TernaryOp(p[1], p[3], p[5], p[1].coord)

    # 二元表达式（优先级3-12）
    # 将优先级3到12的二元表达式的归约都列于此
    # 它们在归约时的优先级关系和结合性由前面的 precedence元组规定
    # 
    def p_binary_expression(self, p):
        """ binary_expression   : cast_expression
                                | binary_expression TIMES binary_expression
                                | binary_expression DIVIDE binary_expression
                                | binary_expression MOD binary_expression
                                | binary_expression PLUS binary_expression
                                | binary_expression MINUS binary_expression
                                | binary_expression LSHIFT binary_expression
                                | binary_expression RSHIFT binary_expression
                                | binary_expression GT binary_expression
                                | binary_expression GE binary_expression
                                | binary_expression LT binary_expression
                                | binary_expression LE binary_expression
                                | binary_expression EQ binary_expression
                                | binary_expression NE binary_expression
                                | binary_expression AND binary_expression
                                | binary_expression XOR binary_expression
                                | binary_expression OR binary_expression
                                | binary_expression LAND binary_expression
                                | binary_expression LOR binary_expression
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = c_ast.BinaryOp(p[2], p[1], p[3], p[1].coord)

    # 类型转换表达式（优先级2）
    # 例如 (int)bar
    # 由于C语言标准中规定前缀自增与自减的运算数不能是转型
    # 所以对转型的归约单独列出
    # 
    def p_cast_expression_1(self, p):
        """ cast_expression : unary_expression """
        p[0] = p[1]

# 
    # def p_cast_expression_2(self, p):
    #     """ cast_expression : LPAREN type_name RPAREN cast_expression """
    #     p[0] = c_ast.Cast(p[2], p[4], self._token_coord(p, 1))

    # 一元表达式（优先级2）
    # 包含对前缀自增和自减的归约
    # 以及对其它一元运算符的归约
    # 
    def p_unary_expression_1(self, p):
        """ unary_expression    : postfix_expression """
        p[0] = p[1]

    def p_unary_expression_2(self, p):
        """ unary_expression    : PLUSPLUS unary_expression
                                | MINUSMINUS unary_expression
                                | unary_operator cast_expression
        """
        p[0] = c_ast.UnaryOp(p[1], p[2], p[2].coord)


    def p_unary_operator(self, p):
        """ unary_operator  : AND
                            | TIMES
                            | PLUS
                            | MINUS
                            | NOT
                            | LNOT
        """
        p[0] = p[1]

    # 实参列表，函数调用时使用
    # 
    def p_argument_expression_list(self, p):
        """ argument_expression_list    : assignment_expression
                                        | argument_expression_list COMMA assignment_expression
        """
        if len(p) == 2:
            p[0] = c_ast.ExprList([p[1]], p[1].coord)
        else:
            p[1].exprs.append(p[3])
            p[0] = p[1]

    # 后缀表达式（优先级1）
    # 包含对数组引用、函数调用和Struct结构引用
    # 以及后缀自增和自减的归约
    # 
    def p_postfix_expression_1(self, p):
        """ postfix_expression  : primary_expression """
        p[0] = p[1]

    def p_postfix_expression_2(self, p):
        """ postfix_expression  : postfix_expression LBRACKET expression RBRACKET """
        p[0] = c_ast.ArrayRef(p[1], p[3], p[1].coord)

    def p_postfix_expression_3(self, p):
        """ postfix_expression  : postfix_expression LPAREN argument_expression_list RPAREN
                                | postfix_expression LPAREN RPAREN
        """
        p[0] = c_ast.FuncCall(p[1], p[3] if len(p) == 5 else None, p[1].coord)

    def p_postfix_expression_4(self, p):
        """ postfix_expression  : postfix_expression PERIOD identifier
                                | postfix_expression ARROW identifier
        """
        # field = c_ast.ID(p[3], self._token_coord(p, 3))
        # p[0] = c_ast.StructRef(p[1], p[2], field, p[1].coord)
        p[0] = c_ast.StructRef(p[1], p[2], p[3], p[1].coord)

    def p_postfix_expression_5(self, p):
        """ postfix_expression  : postfix_expression PLUSPLUS
                                | postfix_expression MINUSMINUS
        """
        # 添加前缀p以表示这是后缀的运算符，与上面前缀的进行区分
        p[0] = c_ast.UnaryOp('p' + p[2], p[1], p[1].coord)

    # 基本表达式，优先级最高
    # 表达式加括号后优先级也成为最高
    #
    def p_primary_expression_1(self, p):
        """ primary_expression  : identifier
                                | constant
                                | string_literal
        """
        p[0] = p[1]
    
    def p_primary_expression_2(self, p):
        """ primary_expression  : LPAREN expression RPAREN """
        p[0] = p[2]

    # def p_offsetof_member_designator

    def p_identifier(self, p):
        """ identifier : ID """
        p[0] = c_ast.ID(p[1], self._token_coord(p, 1))

    # 整数、浮点数和字符常量
    #
    def p_constant_1(self, p):
        """ constant : INT_CONST """
        uCount = 0
        lCount = 0
        for x in p[1][-3:]:
            if x in ('l', 'L'):
                lCount += 1
            elif x in ('u', 'U'):
                uCount += 1
        if uCount > 1:
            raise ValueError('常量尾缀错误，含有多于1个u/U')
        elif lCount > 2:
            raise ValueError('常量尾缀错误，含有多余2个l/L')
        prefix = 'unsigned ' * uCount + 'long ' * lCount
        p[0] = c_ast.Constant(prefix + 'int', p[1], self._token_coord(p, 1))

    def p_constant_2(self, p):
        """ constant : FLOAT_CONST """
        if p[1][-1] in ('f', 'F'):
            t = 'float'
        elif p[1][-1] in ('l', 'L'):
            t = 'long double'
        else:
            t = 'double'
        p[0] = c_ast.Constant(t, p[1], self._token_coord(p, 1))

    def p_constant_3(self, p):
        """ constant : CHAR_CONST """
        p[0] = c_ast.Constant('char', p[1], self._token_coord(p, 1))

    # 字符串
    #
    def p_string_literal(self, p):
        """ string_literal : STRING_LITERAL """
        p[0] = c_ast.Constant(
            'string', p[1].replace('\n', '\\n'), self._token_coord(p, 1))

    def p_brace_open(self, p):
        """ brace_open : LBRACE """
        p[0] = p[1]
        p.set_lineno(0, p.lineno(1))

    def p_brace_close(self, p):
        """ brace_close : RBRACE """
        p[0] = p[1]
        p.set_lineno(0, p.lineno(1))

    # 定义空字 ε
    #
    def p_empty(self, p):
        """ empty : """
        p[0] = None

    # 错误处理
    #
    def p_error(self, p):
        if p:
            self._parse_error(
                '在 {} 之前'.format(p.value),
                self._coord(lineno=p.lineno,
                            column=self.clex.token_column(p))
            )
        else:
            self._parse_error('到达文件结尾', self.clex.filename)
