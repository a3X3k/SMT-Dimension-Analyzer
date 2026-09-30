from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QDialogButtonBox,QLabel

class ColumnMappingDialog(QDialog):
    def __init__(self,title,columns,fields,detected=None,parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.resize(460,280)
        detected=detected or {}; lay=QVBoxLayout(self)
        lay.addWidget(QLabel("Define exactly which imported column represents each engineering field."))
        form=QFormLayout(); lay.addLayout(form); self.boxes={}
        choices=["<Not used>"]+list(columns)
        for key,label,required in fields:
            box=QComboBox(); box.addItems(choices)
            guess=detected.get(key)
            if guess in columns: box.setCurrentText(guess)
            self.boxes[key]=box; form.addRow(label+(" *" if required else ""),box)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); lay.addWidget(buttons)
        self.required={k for k,_,req in fields if req}
    def _accept(self):
        missing=[k for k in self.required if self.boxes[k].currentIndex()==0]
        if missing:
            self.setWindowTitle("Required mapping missing: "+", ".join(missing)); return
        self.accept()
    def mapping(self):
        return {k:(b.currentText() if b.currentIndex()>0 else None) for k,b in self.boxes.items()}
