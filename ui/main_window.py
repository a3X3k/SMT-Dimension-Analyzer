from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import *
from models import ProjectState
from parsers.cad_parser import inspect_cad,parse_cad
from parsers.bom_parser import inspect_bom,parse_bom,group_unique_parts
from parsers.gerber_parser import parse_gerber_files
from matching.representative_selector import select_cad_aware_representatives
from dimensions.gerber_dimension import derive_project_dimensions
from export.excel_export import export_excel
from export.text_export import export_text
from ui.mapping_dialog import ColumnMappingDialog
from ui.pcb_workspace import PCBWorkspace
from lookup.providers.web_search import lookup_links

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SMT Component Dimension Analyzer — Visual Engineering Review")
        self.resize(1500,900)
        self.state=ProjectState(); self.dx=self.dy=self.da=0.0
        self._build(); self._update_status()

    def _build(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root)
        bar=QHBoxLayout(); outer.addLayout(bar)
        self.cad_btn=QPushButton("Import CAD"); self.cad_btn.clicked.connect(self.import_cad); bar.addWidget(self.cad_btn)
        self.bom_btn=QPushButton("Import BOM"); self.bom_btn.clicked.connect(self.import_bom); bar.addWidget(self.bom_btn)
        self.gerber_btn=QPushButton("Import Gerber"); self.gerber_btn.clicked.connect(self.import_gerber); bar.addWidget(self.gerber_btn)
        self.fit=QPushButton("Fit Board"); self.fit.clicked.connect(lambda:self.workspace.fit_board()); bar.addWidget(self.fit)
        self.refs=QCheckBox("Ref Designators"); self.refs.setChecked(True); self.refs.toggled.connect(lambda v:self.workspace.toggle_refs(v)); bar.addWidget(self.refs)
        self.analyze_top=QPushButton("Analyze Dimensions"); self.analyze_top.clicked.connect(self._analyze); bar.addWidget(self.analyze_top)
        self.export_top=QPushButton("Export Excel + TXT"); self.export_top.clicked.connect(self._export); bar.addWidget(self.export_top)
        bar.addStretch()
        self.status_strip=QLabel(); outer.addWidget(self.status_strip)

        split=QSplitter(); outer.addWidget(split,1)
        self.workspace=PCBWorkspace(); self.workspace.componentClicked.connect(self._select_ref); split.addWidget(self.workspace)
        right=QWidget(); rr=QVBoxLayout(right); split.addWidget(right); split.setSizes([1050,450])
        self.tabs=QTabWidget(); rr.addWidget(self.tabs)
        self._files_tab(); self._alignment_tab(); self._review_tab()

    def _files_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"Files / Mapping")
        l.addWidget(QLabel("<b>Imports are always available from the top toolbar.</b>"))
        self.cad_info=QLabel("CAD: not loaded"); self.cad_info.setWordWrap(True); l.addWidget(self.cad_info)
        self.bom_info=QLabel("BOM: not loaded"); self.bom_info.setWordWrap(True); l.addWidget(self.bom_info)
        self.gerber_info=QLabel("Gerber: not loaded"); self.gerber_info.setWordWrap(True); l.addWidget(self.gerber_info)
        l.addStretch()

    def _alignment_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"CAD ↔ Gerber Alignment")
        l.addWidget(QLabel("CAD stays fixed. Move/rotate the Gerber overlay live. No import acceptance is required."))
        form=QFormLayout(); l.addLayout(form)
        self.xoff=QDoubleSpinBox(); self.yoff=QDoubleSpinBox(); self.aoff=QDoubleSpinBox()
        for s in (self.xoff,self.yoff): s.setRange(-10000,10000); s.setDecimals(4); s.setSingleStep(.01)
        self.aoff.setRange(-360,360); self.aoff.setDecimals(3); self.aoff.setSingleStep(.1)
        form.addRow("Gerber X offset (mm)",self.xoff); form.addRow("Gerber Y offset (mm)",self.yoff); form.addRow("Gerber angle (°)",self.aoff)
        for s in (self.xoff,self.yoff,self.aoff): s.valueChanged.connect(self._alignment_changed)
        n=QGridLayout(); l.addLayout(n)
        for text,dx,dy,da,r,c in [("X -0.01",-.01,0,0,0,0),("X +0.01",.01,0,0,0,1),("Y -0.01",0,-.01,0,1,0),("Y +0.01",0,.01,0,1,1),("A -0.1°",0,0,-.1,2,0),("A +0.1°",0,0,.1,2,1)]:
            b=QPushButton(text); b.clicked.connect(lambda _,x=dx,y=dy,a=da:self._nudge(x,y,a)); n.addWidget(b,r,c)
        l.addStretch()

    def _review_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"Component Review")
        self.table=QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(["Ref","MPN","Package/Type","Body L","Body W","Height","Pins/Pitch","Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.itemSelectionChanged.connect(self._table_selected); l.addWidget(self.table,1)
        self.review_info=QLabel("Import CAD, BOM and Gerber, then Analyze Dimensions."); self.review_info.setWordWrap(True); l.addWidget(self.review_info)
        form=QFormLayout(); self.manual_l=QDoubleSpinBox(); self.manual_w=QDoubleSpinBox()
        for s in (self.manual_l,self.manual_w): s.setRange(0,100); s.setDecimals(4); s.setSingleStep(.01)
        form.addRow("Adjusted body L (mm)",self.manual_l); form.addRow("Adjusted body W (mm)",self.manual_w); l.addLayout(form)
        self.apply_adjust=QPushButton("Apply Manual L/W"); self.apply_adjust.clicked.connect(self._apply_adjust); l.addWidget(self.apply_adjust)
        self.lookup=QPushButton("Search Selected MPN / Datasheet"); self.lookup.clicked.connect(self._lookup); l.addWidget(self.lookup)
        row=QHBoxLayout(); l.addLayout(row)
        self.accept_dim=QPushButton("Use / Accept Dimension"); self.accept_dim.clicked.connect(self._accept_dimension); row.addWidget(self.accept_dim)
        self.reject_dim=QPushButton("Reject / Manual Review"); self.reject_dim.clicked.connect(self._reject_dimension); row.addWidget(self.reject_dim)

    def _update_status(self):
        cad=len(self.state.cad_records); bom=len(self.state.unique_parts); ger=len(self.state.gerber_documents)
        reviewed=sum(1 for x in self.state.dimension_results.values() if getattr(x,"accepted",False))
        self.status_strip.setText(f"CAD: {cad or '—'} | BOM unique parts: {bom or '—'} | Gerber layers: {ger or '—'} | Alignment X {self.dx:+.4f}  Y {self.dy:+.4f}  A {self.da:+.3f}° | Reviewed: {reviewed}/{bom}")
        self.bom_btn.setEnabled(bool(self.state.cad_records))
        self.gerber_btn.setEnabled(bool(self.state.cad_records))
        ready=bool(self.state.cad_records and self.state.unique_parts and self.state.gerber_documents)
        self.analyze_top.setEnabled(ready); self.export_top.setEnabled(bool(self.state.unique_parts))

    def import_cad(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import CAD","","CAD (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        df,det=inspect_cad(fn)
        fields=[("ref","Reference designator",True),("x","X coordinate",True),("y","Y coordinate",True),("rotation","Angle / rotation",True),("layer","Side / layer",False),("mpn","Part number (optional)",False)]
        d=ColumnMappingDialog("CAD Column Mapping",list(df.columns),fields,det,self)
        if d.exec()!=QDialog.Accepted:return
        self.state.cad_path=Path(fn); self.state.cad_records=parse_cad(fn,d.mapping()); self.state.dimension_results={}
        self.cad_info.setText(f"CAD: {Path(fn).name} — {len(self.state.cad_records)} placements")
        self.workspace.set_data(cad=self.state.cad_records); self.workspace.fit_board(); self._update_status()

    def import_bom(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import BOM","","BOM (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        df,det=inspect_bom(fn); fields=[("mpn","Part number / MPN",True),("ref","Reference designator",True)]
        d=ColumnMappingDialog("BOM Column Mapping",list(df.columns),fields,det,self)
        if d.exec()!=QDialog.Accepted:return
        m=d.mapping(); self.state.bom_path=Path(fn); self.state.bom_records=parse_bom(fn,ref_col=m["ref"],pn_col=m["mpn"])
        self.state.unique_parts=group_unique_parts(self.state.bom_records); select_cad_aware_representatives(self.state.unique_parts,self.state.cad_records)
        cadrefs={c.ref.strip().upper() for c in self.state.cad_records}; matched=sum(any(r.strip().upper() in cadrefs for r in p.refs) for p in self.state.unique_parts)
        self.bom_info.setText(f"BOM: {Path(fn).name} — {len(self.state.unique_parts)} unique PNs; {matched} matched to CAD")
        self.state.dimension_results={}; self._populate(); self._update_status()

    def import_gerber(self):
        files,_=QFileDialog.getOpenFileNames(self,"Import Gerber Layers","","Gerber (*.GTL *.GBL *.GTO *.GBO *.GTP *.GBP *.gbr *.ger *.pho *.art);;All Files (*)")
        if not files:return
        self.state.gerber_paths=[Path(x) for x in files]; self.state.gerber_documents=parse_gerber_files(files); self.state.dimension_results={}
        self.gerber_info.setText("Gerber: "+", ".join(f"{d.path.name} [{d.layer}]" for d in self.state.gerber_documents))
        self.workspace.set_data(gerbers=self.state.gerber_documents); self.workspace.fit_board(); self._update_status()

    def _alignment_changed(self):
        self.dx=self.xoff.value(); self.dy=self.yoff.value(); self.da=self.aoff.value()
        self.workspace.set_alignment(self.dx,self.dy,self.da)
        if self.state.dimension_results:
            self.state.dimension_results={}
            for r in range(self.table.rowCount()): self.table.setItem(r,7,QTableWidgetItem("RE-ANALYZE AFTER ALIGNMENT"))
        self._update_status()

    def _nudge(self,x,y,a):
        self.xoff.setValue(self.xoff.value()+x); self.yoff.setValue(self.yoff.value()+y); self.aoff.setValue(self.aoff.value()+a)

    def _populate(self):
        self.table.setRowCount(len(self.state.unique_parts))
        for r,p in enumerate(self.state.unique_parts):
            for col,val in enumerate([p.representative_ref,p.mpn,"","","","","","WAITING"]): self.table.setItem(r,col,QTableWidgetItem(val))
        self.table.resizeColumnsToContents()

    def _select_ref(self,ref):
        for r in range(self.table.rowCount()):
            if self.table.item(r,0) and self.table.item(r,0).text()==ref: self.table.selectRow(r); break
        self.workspace.select_ref(ref)

    def _table_selected(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        p=self.state.unique_parts[r]; self.workspace.select_ref(p.representative_ref); x=self.state.dimension_results.get(p.mpn)
        if not x:return
        self.workspace.show_review_bbox(getattr(x,"body_bbox",None))
        self.manual_l.setValue(float(getattr(x,"length_mm",0) or 0)); self.manual_w.setValue(float(getattr(x,"width_mm",0) or 0))
        self.review_info.setText(f"Ref {p.representative_ref} | {getattr(x,'source','')} | Body {getattr(x,'length_mm',None)} × {getattr(x,'width_mm',None)} mm | Status {getattr(x,'status','')}")

    def _lookup(self):
        r=self.table.currentRow()
        if r<0:return
        menu=QMenu(self)
        for link in lookup_links(self.table.item(r,1).text()):
            a=menu.addAction(link.provider); a.triggered.connect(lambda _,u=link.url:QDesktopServices.openUrl(QUrl(u)))
        menu.exec(self.lookup.mapToGlobal(self.lookup.rect().bottomLeft()))

    def _analyze(self):
        if not (self.state.cad_records and self.state.unique_parts and self.state.gerber_documents):
            QMessageBox.warning(self,"Missing input","Import CAD, BOM and Gerber before analysis."); return
        self.state.dimension_results=derive_project_dimensions(self.state.unique_parts,self.state.cad_records,self.state.gerber_documents)
        for r,p in enumerate(self.state.unique_parts):
            x=self.state.dimension_results.get(p.mpn)
            if not x:continue
            self.table.setItem(r,3,QTableWidgetItem(str(getattr(x,"length_mm","") or ""))); self.table.setItem(r,4,QTableWidgetItem(str(getattr(x,"width_mm","") or "")))
            self.table.setItem(r,6,QTableWidgetItem(f"{getattr(x,'pad_count',None) or ''} / {getattr(x,'pitch_mm',None) or ''}")); self.table.setItem(r,7,QTableWidgetItem(getattr(x,"status","MANUAL REVIEW")))
        self._update_status()

    def _apply_adjust(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if not x:return
        x.length_mm=round(self.manual_l.value(),4); x.width_mm=round(self.manual_w.value(),4); x.source="USER - Manual Body Adjustment"; x.confidence="USER CONFIRMED"; x.status="WAITING FOR USER ACCEPTANCE"; x.accepted=False
        self.table.setItem(r,3,QTableWidgetItem(str(x.length_mm))); self.table.setItem(r,4,QTableWidgetItem(str(x.width_mm))); self.table.setItem(r,7,QTableWidgetItem(x.status)); self._update_status()

    def _accept_dimension(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if x:
            x.accepted=True; x.status="USER ACCEPTED"
            if "User Confirmed" not in x.source:x.source=(x.source+" - User Confirmed").strip(" -")
            self.table.setItem(r,7,QTableWidgetItem(x.status)); self._update_status()

    def _reject_dimension(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if x:x.accepted=False; x.status="MANUAL REVIEW"
        self.table.setItem(r,7,QTableWidgetItem("MANUAL REVIEW")); self._update_status()

    def _export(self):
        folder=QFileDialog.getExistingDirectory(self,"Export folder")
        if not folder:return
        cad={c.ref:c for c in self.state.cad_records}; accepted={k:v for k,v in self.state.dimension_results.items() if getattr(v,"accepted",False)}
        export_excel(Path(folder)/"Shape_Dimensions.xlsx",self.state.unique_parts,cad,accepted); export_text(Path(folder)/"Shape_Dimensions.txt",self.state.unique_parts,accepted)
        QMessageBox.information(self,"Export","Created Shape_Dimensions.xlsx and Shape_Dimensions.txt")

def run_app():
    app=QApplication.instance() or QApplication([]); w=MainWindow(); w.show(); app.exec()
