from c_parser import  CParser
from c_translator import MCode
from c_translator import CTranslator
from c_assembler import CAssembler
import os

data = '''
int main(){
    for(int i = 1; i < 10; i++){
        for(int j = 1; j<10; j++){
            printf("%d*%d=%d\t", i, j, i*j);
        }
        printf("\n");
    }
}
        '''

parser = CParser()
ast = parser.parse(data)
ast.show(attrnames=True, nodenames=True)

translator = CTranslator()
translator.visit(ast)
for code in translator.get_codes():
    print(code)
tables = translator.get_tables()
print(tables['symbol_table'])
codes = translator.get_codes()
assembler = CAssembler(tables)
asm = assembler.asm(codes)
print(asm)
with open('hello.s', 'w') as f:
    f.write(asm)

os.system('gcc {filename} -o hello.exe'.format(filename='hello.s'))
os.system('hello.exe')