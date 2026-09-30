from PySide6.QtWidgets import QDialog,QVBoxLayout,QTableWidget,QTableWidgetItem
class ReviewWindow(QDialog):
    def __init__(self, parts, parent=None):
        super().__init__(parent); self.setWindowTitle("Component Review"); self.resize(900,500); lay=QVBoxLayout(self)
        table=QTableWidget(len(parts),9); table.setHorizontalHeaderLabels(["PN","Ref","Package","Length","Width","Height","Source","Confidence","Status"])
        for r,p in enumerate(parts):
            vals=[p.mpn,p.representative_ref,"","","","","","","NOT AVAILABLE / MANUAL REVIEW"]
            for c,v in enumerate(vals): table.setItem(r,c,QTableWidgetItem(str(v)))
        table.resizeColumnsToContents(); lay.addWidget(table)
