from pathlib import Path
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QMessageBox
from models import ProjectState
from parsers.bom_parser import parse_bom,group_unique_parts
from parsers.cad_parser import parse_cad
from parsers.gerber_parser import parse_gerber_files
from parsers.odb_parser import parse_odb,select_odb_source
from matching.representative_selector import select_cad_aware_representatives
from matching.reference_matcher import match_representatives
from dimensions.gerber_dimension import derive_project_dimensions,apply_manual_matches
from dimensions.odb_dimension import derive_odb_dimensions,merge_priority
from export.excel_export import export_excel
from export.text_export import export_text
from database.database import init_db
from ui.review_window import ReviewWindow

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("SMT Component Dimension Analyzer"); self.resize(1000,700)
        self.state=ProjectState(); self.db_path=init_db(Path.home()/'.smt_dimension_analyzer'/'app.db')
        root=QWidget(); self.setCentralWidget(root); lay=QVBoxLayout(root)
        self.status=QLabel(); lay.addWidget(self.status)
        row=QHBoxLayout(); lay.addLayout(row)
        for txt,fn in [('Import BOM',self.import_bom),('Import CAD',self.import_cad),('Import Gerber',self.import_gerber),('Analyze',self.analyze),('Review',self.review),('Export',self.export_results)]:
            b=QPushButton(txt); b.clicked.connect(fn); row.addWidget(b)
        self.refresh()

    def refresh(self):
        self.status.setText(f"BOM refs: {len(self.state.bom_records)} | Unique PN: {len(self.state.unique_parts)} | CAD: {len(self.state.cad_records)} | Gerber: {len(self.state.gerber_documents)}")

    def import_bom(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import BOM","","BOM (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        self.state.bom_path=Path(fn); self.state.bom_records=parse_bom(fn); self.state.unique_parts=group_unique_parts(self.state.bom_records)
        if self.state.cad_records: select_cad_aware_representatives(self.state.unique_parts,self.state.cad_records)
        self.refresh()

    def import_cad(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import CAD","","CAD (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        self.state.cad_path=Path(fn); self.state.cad_records=parse_cad(fn)
        if self.state.unique_parts: select_cad_aware_representatives(self.state.unique_parts,self.state.cad_records)
        self.refresh()

    def import_gerber(self):
        files,_=QFileDialog.getOpenFileNames(self,"Import Gerber Files","","Gerber (*.GTL *.GBL *.GTO *.GBO *.GTS *.GBS *.GTP *.GBP *.gbr *.ger *.pho *.art);;All Files (*)")
        if not files:return
        self.state.gerber_paths=[Path(x) for x in files]; self.state.gerber_documents=parse_gerber_files(self.state.gerber_paths); self.refresh()

    def analyze(self):
        if not self.state.unique_parts: QMessageBox.information(self,"Analyze","Import a BOM first."); return
        gerber_results={}
        if self.state.gerber_documents and self.state.cad_records:
            gerber_results=derive_project_dimensions(self.state.unique_parts,self.state.cad_records,self.state.gerber_documents)
            gerber_results=apply_manual_matches(self.state.unique_parts,gerber_results,self.state.manual_gerber_matches)
        odb_results={}
        self.state.dimension_results=merge_priority(odb_results,gerber_results)
        matches=match_representatives(self.state.unique_parts,self.state.cad_records) if self.state.cad_records else []
        QMessageBox.information(self,"Analysis",f"Unique PN/MPN: {len(self.state.unique_parts)}\nCAD matches: {sum(m.status=='MATCHED' for m in matches)}\nResults: {len(self.state.dimension_results)}")

    def review(self):
        ReviewWindow(self.state.unique_parts,self).exec()

    def export_results(self):
        if not self.state.unique_parts: QMessageBox.information(self,"Export","Nothing to export. Import a BOM first."); return
        folder=QFileDialog.getExistingDirectory(self,"Choose export folder")
        if not folder:return
        cad={c.ref:c for c in self.state.cad_records}
        export_excel(Path(folder)/"Shape_Dimensions.xlsx",self.state.unique_parts,cad,self.state.dimension_results)
        export_text(Path(folder)/"Shape_Dimensions.txt",self.state.unique_parts,self.state.dimension_results)
        QMessageBox.information(self,"Export","Shape_Dimensions.xlsx and Shape_Dimensions.txt created.")

def run_app():
    app=QApplication.instance() or QApplication([])
    w=MainWindow(); w.show(); app.exec()
