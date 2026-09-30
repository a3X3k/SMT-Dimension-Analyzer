from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QComboBox,QDialogButtonBox

class ColumnMappingDialog(QDialog):
    def __init__(self, columns, required, detected=None, parent=None):
        super().__init__(parent); self.setWindowTitle("Column Mapping"); self._boxes={}; lay=QVBoxLayout(self); detected=detected or {}
        for key,label in required:
            lay.addWidget(QLabel(label)); box=QComboBox(); box.addItems([""]+list(columns))
            if detected.get(key) in columns: box.setCurrentText(detected[key])
            self._boxes[key]=box; lay.addWidget(box)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); lay.addWidget(buttons)
    def mapping(self):
        return {k:b.currentText() for k,b in self._boxes.items() if b.currentText()}
