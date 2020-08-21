from c_translator import WORD_SIZE

code_header = """
	.file	"{filename}"
	.def	___main;	.scl	2;	.type	32;	.endef
"""

cond_dict = {'>': 'g', '<': 'l', '==': 'eq', '>=': 'ge', '<=': 'le', '!=': 'ne'}


class CAssembler(object):
    def __init__(self, tables):
        self.constant_table = tables['constant_table']
        self.symbol_table = tables['symbol_table']
        self.asmtext = ''
        self.lfe_count = -1
        self.lfb_count = 0
        self.cur_func = None

    def _gen_func_header(self, funcname):
        if self.lfe_count > -1:
            self.asmtext += 'LFE1{}:\n'.format(self.lfe_count)
        self.lfe_count = self.lfe_count + 1

        if funcname in [res[0] for res in self.constant_table.values()]:
            self.asmtext += '\t.section .rdata,"dr"\n'
            for key in self.constant_table:
                if self.constant_table[key][0] == funcname:
                    self.asmtext += 'LC{}:\n'.format(self.constant_table[key][1])
                    self.asmtext += '\t.ascii "{}\\0"\n'.format(key)
            self.asmtext += '\t.text\n'

        self.asmtext += '\t.globl\t_{}\n'.format(funcname)
        self.asmtext += '\t.def\t_{}; .scl	2;	.type	32;	.endef\n'.format(funcname)

    def _gen_func_init(self, funcname):
        self.asmtext += '_{}:\n'.format(funcname)
        self.asmtext += 'LFB1{}:\n'.format(self.lfb_count)
        self.lfb_count = self.lfb_count + 1
        self.asmtext += '\t.cfi_startproc\n\tpushl	%ebp\n\t.cfi_def_cfa_offset 8\n\t.cfi_offset 5, -8\n\tmovl	%esp, %ebp\n\t.cfi_def_cfa_register 5\n'
        if self.symbol_table[funcname]['stacksize'] > 0:
            if funcname == 'main':
                self.asmtext += '\tandl	$-16, %esp\n'
            self.asmtext += '\tsubl	${}, %esp\n'.format(self.symbol_table[funcname]['stacksize'])
        if funcname == 'main':
            self.asmtext += '\tcall\t___main\n'

    def _gen_func_exit(self, funcname):
        if funcname == 'main':
            self.asmtext += '\tleave\n'
        else:
            self.asmtext += '\tpopl\t%ebp\n'
        self.asmtext += '\t.cfi_restore 5\n\t.cfi_def_cfa 4, 4\n\tret\n\t.cfi_endproc\n'

    def _gen_code_footer(self):
        if self.lfe_count > -1:
            self.asmtext += 'LFE1{}:\n'.format(self.lfe_count)
        self.lfe_count = self.lfe_count + 1
        self.asmtext += '\t.ident\t"BWCC: (Nuke666.cn BWCC-0.0.1) 6.3.0"\n\t.def\t_printf;	.scl	2;	.type	32;	.endef\n'

    def _get_var(self, sym):
        if sym.isdigit() or (sym[0] == '-' and sym[1:].isdigit()) or sym.startswith('LC'):
            return '$' + sym
        elif sym.startswith('_'):
            return '%eax'
        else: return '{offset}(%esp)'.format(offset=self.symbol_table[self.cur_func]['symbols'][sym] or '')

    def asm(self, codes):
        symbols = None
        for code in codes:
            if code.op == 'func':
                self.cur_func = code.result
                self._gen_func_header(code.result)
                self._gen_func_init(code.result)
                symbols = self.symbol_table[code.result]
            elif code.op == 'endfunc':
                self._gen_func_exit(self.cur_func)
                symbols = None
            elif code.op == 'param':
                # 参数可能为字符串常量、数字常量、变量
                arg = code.arg2
                offset = (code.result - 1 - code.arg1) * WORD_SIZE # 计算参数应放入堆栈中的偏移量
                if offset == 0: offset = ''
                if arg.isdigit() or arg.startswith('LC'):
                    self.asmtext += '\tmovl\t${}, {}(%esp)\n'.format(arg, offset)
                else:
                    self.asmtext += '\tmovl\t{}, %eax\n'.format(self._get_var(arg))
                    self.asmtext += '\tmovl\t%eax, {}(%esp)\n'.format(offset)
            elif code.op == 'call':
                self.asmtext += '\tcall\t_{}\n'.format(code.result)
            elif code.op == 'return':
                self.asmtext += '\tmovl\t{}, %eax\n'.format(self._get_var(code.result) or 0)
            elif code.op == 'label':
                self.asmtext += '{}:\n'.format(code.result)
            elif code.op == 'j':
                self.asmtext += '\tjmp {}\n'.format(code.result)
            elif code.op.startswith('j'):
                self.asmtext += '\tmovl\t{}, %eax\n'.format(self._get_var(code.arg1))
                self.asmtext += '\tcmpl\t{}, %eax\n'.format(self._get_var(code.arg2))
                self.asmtext += '\tj{} {}\n'.format(cond_dict[code.op[1:]], code.result)
            elif code.op == '=':
                if code.arg1.isdigit():
                    self.asmtext += '\tmovl\t${arg}, {var}\n'.format(arg=code.arg1, var=self._get_var(code.result))
                else:
                    self.asmtext += '\tmovl\t{}, %eax\n'.format(self._get_var(code.arg1))
                    self.asmtext += '\tmovl\t%eax, {}\n'.format(self._get_var(code.result))
            elif code.op in ('+', '-', '*'):
                keymap = {'+':'addl', '-': 'subl', '*': 'imull'}
                self.asmtext += '\tmovl\t{}, %eax\n'.format(self._get_var(code.arg1))
                self.asmtext += '\t{}\t{}, %eax\n'.format(keymap[code.op], self._get_var(code.arg2))
                self.asmtext += '\tmovl\t%eax, {}\n'.format(self._get_var(code.result))
            elif code.op in ('/'):
                self.asmtext += '\tmovl\t{}, %eax\n'.format(self._get_var(code.arg1))
                self.asmtext += '\tcltd\n'
                self.asmtext += '\tidivl\t, {}\n'.format(self._get_var(code.arg2))

        self._gen_code_footer()

        return code_header.format(filename='hello.c') + self.asmtext
