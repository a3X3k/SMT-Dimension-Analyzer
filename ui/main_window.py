from pathlib import Path
from PySide6.QtCore import Qt,QUrl
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
        super().__init__(); self.setWindowTitle("SMT Component Dimension Analyzer — Visual Engineering Review"); self.resize(1500,900)
        self.state=ProjectState(); self.accepted={"cad":False,"bom":False,"gerber":False,"alignment":False}
        self.dx=self.dy=self.da=0.; self._build(); self._gate()

    def _build(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root)
        title=QLabel("<b>CAD → BOM → Gerber → Alignment → Body/Pin Review → Export</b>"); outer.addWidget(title)
        self.stage=QLabel(); outer.addWidget(self.stage)
        split=QSplitter(); outer.addWidget(split,1)
        left=QWidget(); ll=QVBoxLayout(left); split.addWidget(left)
        self.workspace=PCBWorkspace(); self.workspace.componentClicked.connect(self._select_ref); ll.addWidget(self.workspace,1)
        tools=QHBoxLayout(); ll.addLayout(tools)
        self.fit=QPushButton("Fit Board"); self.fit.clicked.connect(self.workspace.fit_board); tools.addWidget(self.fit)
        self.refs=QCheckBox("Reference designators"); self.refs.setChecked(True); self.refs.toggled.connect(self.workspace.toggle_refs); tools.addWidget(self.refs)
        tools.addStretch()
        right=QWidget(); rr=QVBoxLayout(right); split.addWidget(right); split.setSizes([1050,450])
        self.tabs=QTabWidget(); rr.addWidget(self.tabs)
        self._import_tab(); self._alignment_tab(); self._review_tab()

    def _import_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"1. Import & Accept")
        self.cad_btn=QPushButton("1  Import CAD + Define Reference / X / Y / Angle / Side"); self.cad_btn.clicked.connect(self.import_cad); l.addWidget(self.cad_btn)
        self.cad_info=QLabel("CAD not loaded"); self.cad_info.setWordWrap(True); l.addWidget(self.cad_info)
        self.cad_accept=QPushButton("✓ Accept CAD"); self.cad_accept.clicked.connect(lambda:self._accept("cad")); l.addWidget(self.cad_accept)
        l.addWidget(self._line())
        self.bom_btn=QPushButton("2  Import BOM + Define Part Number / Reference"); self.bom_btn.clicked.connect(self.import_bom); l.addWidget(self.bom_btn)
        self.bom_info=QLabel("BOM not loaded"); self.bom_info.setWordWrap(True); l.addWidget(self.bom_info)
        self.bom_accept=QPushButton("✓ Accept BOM Matching"); self.bom_accept.clicked.connect(lambda:self._accept("bom")); l.addWidget(self.bom_accept)
        l.addWidget(self._line())
        self.gerber_btn=QPushButton("3  Import Gerber Layers"); self.gerber_btn.clicked.connect(self.import_gerber); l.addWidget(self.gerber_btn)
        self.gerber_info=QLabel("Gerber not loaded"); self.gerber_info.setWordWrap(True); l.addWidget(self.gerber_info)
        self.gerber_accept=QPushButton("✓ Accept Gerber Layers"); self.gerber_accept.clicked.connect(lambda:self._accept("gerber")); l.addWidget(self.gerber_accept); l.addStretch()

    def _alignment_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"2. CAD ↔ Gerber")
        l.addWidget(QLabel("CAD stays fixed. Move/rotate the Gerber overlay until the geometry matches."))
        form=QFormLayout(); l.addLayout(form)
        self.xoff=QDoubleSpinBox(); self.yoff=QDoubleSpinBox(); self.aoff=QDoubleSpinBox()
        for s in (self.xoff,self.yoff): s.setRange(-10000,10000); s.setDecimals(4); s.setSingleStep(.01)
        self.aoff.setRange(-360,360); self.aoff.setDecimals(3); self.aoff.setSingleStep(.1)
        form.addRow("Gerber X offset (mm)",self.xoff); form.addRow("Gerber Y offset (mm)",self.yoff); form.addRow("Gerber angle (°)",self.aoff)
        for s in (self.xoff,self.yoff,self.aoff): s.valueChanged.connect(self._alignment_changed)
        nudge=QGridLayout(); l.addLayout(nudge)
        for text,dx,dy,da,r,c in [("X -0.01",-.01,0,0,0,0),("X +0.01",.01,0,0,0,1),("Y -0.01",0,-.01,0,1,0),("Y +0.01",0,.01,0,1,1),("A -0.1°",0,0,-.1,2,0),("A +0.1°",0,0,.1,2,1)]:
            b=QPushButton(text); b.clicked.connect(lambda _,x=dx,y=dy,a=da:self._nudge(x,y,a)); nudge.addWidget(b,r,c)
        self.align_accept=QPushButton("✓ Accept CAD ↔ Gerber Alignment"); self.align_accept.clicked.connect(lambda:self._accept("alignment")); l.addWidget(self.align_accept); l.addStretch()

    def _review_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"3. Component Review")
        self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["Ref","MPN","Package/Type","Body L","Body W","Height","Pins/Pitch","Status"]); self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.itemSelectionChanged.connect(self._table_selected); l.addWidget(self.table,1)
        self.lookup=QPushButton("Search selected MPN on Internet / Datasheet"); self.lookup.clicked.connect(self._lookup); l.addWidget(self.lookup)
        row=QHBoxLayout(); l.addLayout(row)
        self.analyze=QPushButton("Analyze Silkscreen / Paste"); self.analyze.clicked.connect(self._analyze); row.addWidget(self.analyze)
        self.accept_dim=QPushButton("✓ Accept Selected Dimension"); self.accept_dim.clicked.connect(self._accept_dimension); row.addWidget(self.accept_dim)
        self.reject_dim=QPushButton("Reject / Manual Review"); self.reject_dim.clicked.connect(self._reject_dimension); row.addWidget(self.reject_dim)
        self.export=QPushButton("Export Accepted Results — Excel + TXT"); self.export.clicked.connect(self._export); l.addWidget(self.export)

    def _line(self):
        x=QFrame(); x.setFrameShape(QFrame.HLine); return x
    def _accept(self,key):
        self.accepted[key]=True
        if key=="cad": self.cad_btn.setEnabled(False)
        if key=="bom": self.bom_btn.setEnabled(False)
        if key=="gerber": self.gerber_btn.setEnabled(False)
        if key=="alignment": self.xoff.setEnabled(False); self.yoff.setEnabled(False); self.aoff.setEnabled(False)
        self._gate()
    def _invalidate_from(self,key):
        order=["cad","bom","gerber","alignment"]; i=order.index(key)
        for k in order[i:]: self.accepted[k]=False
        self._gate()
    def _gate(self):
        self.cad_accept.setEnabled(bool(self.state.cad_records) and not self.accepted["cad"])
        self.bom_btn.setEnabled(self.accepted["cad"] and not self.accepted["bom"])
        self.bom_accept.setEnabled(bool(self.state.unique_parts) and not self.accepted["bom"])
        self.gerber_btn.setEnabled(self.accepted["bom"] and not self.accepted["gerber"])
        self.gerber_accept.setEnabled(bool(self.state.gerber_documents) and not self.accepted["gerber"])
        ready=self.accepted["gerber"]; self.align_accept.setEnabled(ready and not self.accepted["alignment"])
        for s in (self.xoff,self.yoff,self.aoff): s.setEnabled(ready and not self.accepted["alignment"])
        self.analyze.setEnabled(self.accepted["alignment"]); self.lookup.setEnabled(self.accepted["bom"])
        self.accept_dim.setEnabled(self.accepted["alignment"]); self.reject_dim.setEnabled(self.accepted["alignment"])
        self.export.setEnabled(self.accepted["alignment"])
        done=[k.upper()+" ✓" for k,v in self.accepted.items() if v]
        self.stage.setText("Accepted gates: "+("  |  ".join(done) if done else "None — start with CAD"))

    def import_cad(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import CAD","","CAD (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        df,det=inspect_cad(fn); fields=[("ref","Reference designator",True),("x","X coordinate",True),("y","Y coordinate",True),("rotation","Angle / rotation",True),("layer","Side / layer",False),("mpn","Part number (optional)",False)]
        d=ColumnMappingDialog("CAD Column Mapping",list(df.columns),fields,det,self)
        if d.exec()!=QDialog.Accepted:return
        self.state.cad_path=Path(fn); self.state.cad_records=parse_cad(fn,d.mapping()); self.state.dimension_results={}
        self.cad_info.setText(f"{Path(fn).name} — {len(self.state.cad_records)} placements. Blue crosses/boxes and reference designators are CAD data.")
        self.workspace.set_data(cad=self.state.cad_records); self.workspace.fit_board(); self._invalidate_from("cad")

    def import_bom(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import BOM","","BOM (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        df,det=inspect_bom(fn); fields=[("mpn","Part number / MPN",True),("ref","Reference designator",True)]
        d=ColumnMappingDialog("BOM Column Mapping",list(df.columns),fields,det,self)
        if d.exec()!=QDialog.Accepted:return
        m=d.mapping(); self.state.bom_path=Path(fn); self.state.bom_records=parse_bom(fn,ref_col=m["ref"],pn_col=m["mpn"]); self.state.unique_parts=group_unique_parts(self.state.bom_records)
        select_cad_aware_representatives(self.state.unique_parts,self.state.cad_records)
        cadrefs={c.ref.strip().upper() for c in self.state.cad_records}; matched=sum(any(r.strip().upper() in cadrefs for r in p.refs) for p in self.state.unique_parts)
        self.bom_info.setText(f"{Path(fn).name} — {len(self.state.unique_parts)} unique PNs; {matched} have at least one CAD reference.")
        self._populate(); self._invalidate_from("bom")

    def import_gerber(self):
        files,_=QFileDialog.getOpenFileNames(self,"Import Gerber Layers","","Gerber (*.GTL *.GBL *.GTO *.GBO *.GTP *.GBP *.gbr *.ger *.pho *.art);;All Files (*)")
        if not files:return
        self.state.gerber_paths=[Path(x) for x in files]; self.state.gerber_documents=parse_gerber_files(files)
        desc=", ".join(f"{d.path.name}: {d.layer}" for d in self.state.gerber_documents)
        self.gerber_info.setText(desc); self.workspace.set_data(gerbers=self.state.gerber_documents); self.workspace.fit_board(); self._invalidate_from("gerber")

    def _alignment_changed(self):
        self.dx=self.xoff.value(); self.dy=self.yoff.value(); self.da=self.aoff.value(); self.workspace.set_alignment(self.dx,self.dy,self.da)
        if self.accepted["alignment"]: self.accepted["alignment"]=False; self._gate()
    def _nudge(self,x,y,a): self.xoff.setValue(self.xoff.value()+x); self.yoff.setValue(self.yoff.value()+y); self.aoff.setValue(self.aoff.value()+a)

    def _populate(self):
        self.table.setRowCount(len(self.state.unique_parts))
        for r,p in enumerate(self.state.unique_parts):
            vals=[p.representative_ref,p.mpn,"","","","","","WAITING"]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
        self.table.resizeColumnsToContents()

    def _select_ref(self,ref):
        for r in range(self.table.rowCount()):
            if self.table.item(r,0) and self.table.item(r,0).text()==ref: self.table.selectRow(r); break
        self.workspace.select_ref(ref)
    def _table_selected(self):
        r=self.table.currentRow()
        if r>=0 and self.table.item(r,0): self.workspace.select_ref(self.table.item(r,0).text())
    def _lookup(self):
        r=self.table.currentRow()
        if r<0:return
        mpn=self.table.item(r,1).text(); links=lookup_links(mpn)
        menu=QMenu(self)
        for link in links:
            a=menu.addAction(link.provider); a.triggered.connect(lambda _,u=link.url:QDesktopServices.openUrl(QUrl(u)))
        menu.exec(self.lookup.mapToGlobal(self.lookup.rect().bottomLeft()))

    def _analyze(self):
        self.state.dimension_results=derive_project_dimensions(self.state.unique_parts,self.state.cad_records,self.state.gerber_documents)
        for r,p in enumerate(self.state.unique_parts):
            x=self.state.dimension_results.get(p.mpn)
            if x:
                self.table.setItem(r,3,QTableWidgetItem(str(getattr(x,"length_mm","") or ""))); self.table.setItem(r,4,QTableWidgetItem(str(getattr(x,"width_mm","") or "")))
                self.table.setItem(r,7,QTableWidgetItem(getattr(x,"status","MANUAL REVIEW")))
        QMessageBox.information(self,"Analysis","Silkscreen/paste proposals generated. Review visually and accept or reject each component. Pad/paste geometry is not automatically treated as physical lead/body geometry.")

    def _accept_dimension(self):
        r=self.table.currentRow()
        if r>=0:self.table.setItem(r,7,QTableWidgetItem("USER ACCEPTED"))
    def _reject_dimension(self):
        r=self.table.currentRow()
        if r>=0:self.table.setItem(r,7,QTableWidgetItem("MANUAL REVIEW"))
    def _export(self):
        folder=QFileDialog.getExistingDirectory(self,"Export folder")
        if not folder:return
        cad={c.ref:c for c in self.state.cad_records}; export_excel(Path(folder)/"Shape_Dimensions.xlsx",self.state.unique_parts,cad,self.state.dimension_results); export_text(Path(folder)/"Shape_Dimensions.txt",self.state.unique_parts,self.state.dimension_results)
        QMessageBox.information(self,"Export","Created Shape_Dimensions.xlsx and Shape_Dimensions.txt")

def run_app():
    app=QApplication.instance() or QApplication([]); w=MainWindow(); w.show(); app.exec()
