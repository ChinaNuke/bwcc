from c_parser import CParser

data = '''

int main(double args){
    char c = 'B';
    char d[100];
    for (int i = 0; i < 10; i++){
        printf(i);
    }
    if (a>b) printf(">");

}

void printf(int str){
    return 0;
}
        '''

parser = CParser()
ast = parser.parse(data, '<none>')
# ast.show(attrnames=True, nodenames=True)
for decl in ast:
    decl.show(attrnames=True, nodenames=True)
