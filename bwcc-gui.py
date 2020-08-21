import sys
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QGridLayout, QPushButton, QLabel, QTextEdit, \
    QVBoxLayout, QHBoxLayout, QGroupBox, QFileDialog
from c_parser import CParser
from c_translator import CTranslator
from c_assembler import CAssembler

class BWCC(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(BWCC, self).__init__(*args, **kwargs)
        self.initUI()
        self.parser = CParser()
        self.translator = CTranslator
        self.assembler = CAssembler

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
        self.textSrc = QTextEdit()
        self.textSrc.setLineWrapMode(QTextEdit.NoWrap)
        self.textAST = QTextEdit()
        self.textAST.setLineWrapMode(QTextEdit.NoWrap)
        self.textCode = QTextEdit()
        self.textCode.setLineWrapMode(QTextEdit.NoWrap)
        self.textAsm = QTextEdit()
        self.textAsm.setLineWrapMode(QTextEdit.NoWrap)
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

    def compile(self):
        # self.textAsm.setText(self.textSrc.toPlainText())
        ast = self.parser.parse(self.textSrc.toPlainText())
        self.textAsm.setText(ast)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BWCC()
    app.exec_()
