import sys

from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QPushButton, QLabel, QTextEdit, \
    QVBoxLayout, QHBoxLayout, QGroupBox, QFileDialog
from c_parser import CParser
from c_translator import CTranslator
from c_assembler import CAssembler
import os

class BWCC(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(BWCC, self).__init__(*args, **kwargs)
        self.initUI()
        # self.parser = CParser()
        # self.translator = CTranslator
        # self.assembler = CAssembler

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        btnOpen = QPushButton('打开文件')
        btnCompile = QPushButton('编译')
        btnRun = QPushButton('运行程序')

        vb1 = QVBoxLayout()
        vb2 = QVBoxLayout()
        vb3 = QVBoxLayout()
        vb4 = QVBoxLayout()
        vb5 = QVBoxLayout()
        font = QtGui.QFont()
        font.setFamily("Consolas");
        font.setPointSize(11);
        self.textSrc = QTextEdit()
        self.textSrc.setLineWrapMode(QTextEdit.NoWrap)
        self.textSrc.setFont(font);
        self.textAST = QTextEdit()
        self.textAST.setLineWrapMode(QTextEdit.NoWrap)
        self.textAST.setFont(font)
        self.textCode = QTextEdit()
        self.textCode.setLineWrapMode(QTextEdit.NoWrap)
        self.textCode.setFont(font)
        self.textAsm = QTextEdit()
        self.textAsm.setLineWrapMode(QTextEdit.NoWrap)
        self.textAsm.setFont(font)
        vb1.addWidget(QLabel(' 源程序代码'))
        vb1.addWidget(self.textSrc)
        vb2.addWidget(QLabel(' AST'))
        vb2.addWidget(self.textAST)
        vb3.addWidget(QLabel(' 中间代码'))
        vb3.addWidget(self.textCode)
        vb4.addWidget(QLabel(' 汇编代码'))
        vb4.addWidget(self.textAsm)
        self.textResult = QTextEdit()
        self.textResult.setLineWrapMode(QTextEdit.NoWrap)
        self.textResult.setFont(font)
        vb5.addWidget(QLabel(' 运行结果'))
        vb5.addWidget(self.textResult)

        hBox1 = QHBoxLayout()
        hBox2 = QHBoxLayout()

        hBox1.addWidget(btnOpen)
        hBox1.addWidget(btnCompile)
        hBox1.addWidget(btnRun)
        hBox1.addStretch(1)

        hBox2.addLayout(vb1)
        hBox2.addLayout(vb2)
        hBox2.addLayout(vb3)
        hBox2.addLayout(vb4)

        layout.addLayout(hBox1)
        layout.addLayout(hBox2)
        layout.addLayout(vb5)

        btnOpen.clicked.connect(self.openfile)
        btnCompile.clicked.connect(self.compile)
        btnRun.clicked.connect(self.run)

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.statusBar().showMessage('BWCC编译器已就位！')
        self.setGeometry(100, 100, 1500, 700)
        self.setWindowTitle('BWCC')
        self.show()

    def openfile(self):
        filename = QFileDialog.getOpenFileName(self, '打开源程序', './')
        if filename[0]:
            with open(filename[0], 'r') as f:
                src = f.read()
                self.textSrc.setText(src)
        self.statusBar().showMessage('已打开文件：' + filename[0])

    def compile(self):
        parser = CParser()
        ast = parser.parse(self.textSrc.toPlainText())
        self.textAST.setText(ast.toString(attrnames=True, nodenames=True))
        translator = CTranslator()
        translator.visit(ast)
        codes = translator.get_codes()
        code_text = ''
        for code in codes:
            code_text += str(code) + '\n'
        self.textCode.setText(code_text)
        codes = translator.get_codes()
        tables = translator.get_tables()
        assembler = CAssembler(tables)
        asm = assembler.asm(codes)
        self.textAsm.setText(asm)
        with open('hello.s', 'w') as f:
            f.write(asm)
        os.system('gcc {filename} -o hello.exe'.format(filename='hello.s'))
        self.statusBar().showMessage('编译完成！请点击运行程序。')

    def run(self):
        result = os.popen('hello.exe')
        self.textResult.setText(result.read())
        self.statusBar().showMessage('已成功运行！')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BWCC()
    app.exec_()
