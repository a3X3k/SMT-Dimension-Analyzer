from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel
class ManualGerberMatchWindow(QDialog):
    def __init__(self,state,db_path,parent=None):
        super().__init__(parent); self.setWindowTitle('Manual CAD ↔ Gerber Matching'); self.resize(900,600)
        lay=QVBoxLayout(self); lay.addWidget(QLabel('Manual Gerber matching workspace.'))
