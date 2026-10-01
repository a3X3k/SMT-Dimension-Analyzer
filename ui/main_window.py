from pathlib import Path
from PySide6.QtCore import QUrl,Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import *
from models import ProjectState,CadRecord
from parsers.cad_parser import inspect_cad,parse_cad
from parsers.odb_parser import parse_odb
from parsers.bom_parser import inspect_bom,parse_bom,group_unique_parts
from parsers.gerber_parser import parse_gerber_files
from matching.representative_selector import select_cad_aware_representatives
from dimensions.gerber_dimension import derive_project_dimensions
from dimensions.odb_dimension import derive_odb_dimensions, merge_priority
from dimensions.shape_model import build_project_shapes
from export.excel_export import export_excel
from export.text_export import export_text
from ui.pcb_workspace import PCBWorkspace
from lookup.providers.web_search import lookup_links
from lookup.mpn_lookup import lookup_mpn

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
        self.cad_btn=QPushButton("1. Import CAD / ODB++"); self.cad_btn.clicked.connect(self.import_cad); bar.addWidget(self.cad_btn)
        self.bom_btn=QPushButton("2. Import BOM"); self.bom_btn.clicked.connect(self.import_bom); bar.addWidget(self.bom_btn)
        self.gerber_btn=QPushButton("3. Import Gerber"); self.gerber_btn.clicked.connect(self.import_gerber); bar.addWidget(self.gerber_btn)
        self.fit=QPushButton("Fit Board"); self.fit.clicked.connect(lambda:self.workspace.fit_board()); bar.addWidget(self.fit)
        self.measure_btn=QPushButton("Measure"); self.measure_btn.setCheckable(True); self.measure_btn.toggled.connect(lambda v:self.workspace.set_measure_mode(v)); bar.addWidget(self.measure_btn)
        self.refs=QCheckBox("Ref Designators"); self.refs.setChecked(True); self.refs.toggled.connect(lambda v:self.workspace.toggle_refs(v)); bar.addWidget(self.refs)
        self.mpn_top=QPushButton("Lookup MPN"); self.mpn_top.clicked.connect(self._lookup_structured); bar.addWidget(self.mpn_top)
        self.analyze_top=QPushButton("4. Analyze Dimensions"); self.analyze_top.clicked.connect(self._analyze); bar.addWidget(self.analyze_top)
        self.export_top=QPushButton("Export Excel + TXT"); self.export_top.clicked.connect(self._export); bar.addWidget(self.export_top)
        bar.addStretch()
        self.status_strip=QLabel(); outer.addWidget(self.status_strip)
        self.next_step=QLabel("Next: import CAD data"); self.next_step.setStyleSheet("font-weight:600; padding:6px;"); outer.addWidget(self.next_step)

        split=QSplitter(); outer.addWidget(split,1)
        self.workspace=PCBWorkspace(); self.workspace.componentClicked.connect(self._select_ref); self.workspace.measurementChanged.connect(self._measurement_changed); split.addWidget(self.workspace)
        right=QWidget(); rr=QVBoxLayout(right); split.addWidget(right); split.setSizes([1050,450])
        self.tabs=QTabWidget(); rr.addWidget(self.tabs)
        self._files_tab(); self._layers_tab(); self._alignment_tab(); self._review_tab()

    def _files_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"Imported Data")
        l.addWidget(QLabel("<b>Columns are detected automatically from file headings. No manual mapping is required.</b>"))
        self.cad_info=QLabel("CAD: not loaded"); self.cad_info.setWordWrap(True); l.addWidget(self.cad_info)
        self.bom_info=QLabel("BOM: not loaded"); self.bom_info.setWordWrap(True); l.addWidget(self.bom_info)
        self.gerber_info=QLabel("Gerber: not loaded"); self.gerber_info.setWordWrap(True); l.addWidget(self.gerber_info)
        l.addStretch()

    def _layers_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"Gerber Layers")
        l.addWidget(QLabel("Show/hide each file or correct its detected engineering layer type. Changes apply immediately."))
        op=QHBoxLayout(); l.addLayout(op); op.addWidget(QLabel("Gerber opacity"))
        self.gerber_opacity=QSlider(Qt.Horizontal); self.gerber_opacity.setRange(5,100); self.gerber_opacity.setValue(85); self.gerber_opacity.valueChanged.connect(lambda v:self.workspace.set_gerber_opacity(v/100)); op.addWidget(self.gerber_opacity)
        self.opacity_label=QLabel("85%"); self.gerber_opacity.valueChanged.connect(lambda v:self.opacity_label.setText(f"{v}%")); op.addWidget(self.opacity_label)
        self.layer_table=QTableWidget(0,3); self.layer_table.setHorizontalHeaderLabels(["Visible","Gerber File","Assigned Type"])
        self.layer_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); l.addWidget(self.layer_table,1)

    def _refresh_layers(self):
        types=["Top Silkscreen","Bottom Silkscreen","Top Solder Mask","Bottom Solder Mask","Top Paste","Bottom Paste","Top Copper","Bottom Copper","Other / Ignore"]
        self.layer_table.setRowCount(len(self.state.gerber_documents))
        for r,d in enumerate(self.state.gerber_documents):
            vis=QCheckBox(); vis.setChecked(True); vis.toggled.connect(lambda on,p=str(d.path):self.workspace.set_layer_visible(p,on))
            box=QWidget(); bl=QHBoxLayout(box); bl.setContentsMargins(8,0,0,0); bl.addWidget(vis); bl.addStretch(); self.layer_table.setCellWidget(r,0,box)
            self.layer_table.setItem(r,1,QTableWidgetItem(d.path.name))
            combo=QComboBox(); combo.addItems(types)
            if d.layer not in types: combo.insertItem(0,d.layer)
            combo.setCurrentText(d.layer); combo.currentTextChanged.connect(lambda value,doc=d:self._assign_layer(doc,value)); self.layer_table.setCellWidget(r,2,combo)

    def _assign_layer(self,doc,value):
        doc.layer=value
        self.state.dimension_results={}; self.state.shape_models={}
        self.gerber_info.setText("Gerber: "+", ".join(f"{d.path.name} [{d.layer}]" for d in self.state.gerber_documents))
        self.workspace.redraw(); self._update_status()

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
        nav=QHBoxLayout(); l.addLayout(nav)
        prev=QPushButton("◀ Previous"); prev.clicked.connect(lambda:self._move_review(-1)); nav.addWidget(prev)
        self.ref_search=QLineEdit(); self.ref_search.setPlaceholderText("Find Ref / MPN"); self.ref_search.returnPressed.connect(self._find_component); nav.addWidget(self.ref_search,1)
        nxt=QPushButton("Next ▶"); nxt.clicked.connect(lambda:self._move_review(1)); nav.addWidget(nxt)
        self.table=QTableWidget(0,10)
        self.table.setHorizontalHeaderLabels(["Ref","MPN","Manufacturer","Package/Type","Body L (mm)","Body W (mm)","Body H (mm)","Paste Pads / Pitch Candidate (mm)","Dimension Source / Confidence","Review Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.itemSelectionChanged.connect(self._table_selected); l.addWidget(self.table,1)
        self.review_info=QLabel("Import CAD, BOM and Gerber, then Analyze Dimensions."); self.review_info.setWordWrap(True); l.addWidget(self.review_info)
        form=QFormLayout(); self.manual_l=QDoubleSpinBox(); self.manual_w=QDoubleSpinBox()
        for s in (self.manual_l,self.manual_w): s.setRange(0,100); s.setDecimals(4); s.setSingleStep(.01)
        form.addRow("Adjusted body L (mm)",self.manual_l); form.addRow("Adjusted body W (mm)",self.manual_w); l.addLayout(form)
        l.addWidget(QLabel("Engineering units: millimetres (mm) only."))
        self.apply_adjust=QPushButton("Apply Manual L/W"); self.apply_adjust.clicked.connect(self._apply_adjust); l.addWidget(self.apply_adjust)
        self.lookup=QPushButton("Search Selected MPN / Datasheet"); self.lookup.clicked.connect(self._lookup); l.addWidget(self.lookup)
        row=QHBoxLayout(); l.addLayout(row)
        self.accept_dim=QPushButton("Use / Accept Dimension"); self.accept_dim.clicked.connect(self._accept_dimension); row.addWidget(self.accept_dim)
        self.reject_dim=QPushButton("Reject / Manual Review"); self.reject_dim.clicked.connect(self._reject_dimension); row.addWidget(self.reject_dim)

    def _update_status(self):
        cad=len(self.state.cad_records); bom=len(self.state.unique_parts); ger=len(self.state.gerber_documents)
        reviewed=sum(1 for x in self.state.dimension_results.values() if getattr(x,"accepted",False))
        self.status_strip.setText(f"CAD: {cad or '—'} | BOM unique parts: {bom or '—'} | Gerber layers: {ger or '—'} | Alignment X {self.dx:+.4f} mm  Y {self.dy:+.4f} mm  A {self.da:+.3f}° | Reviewed: {reviewed}/{bom}")
        has_cad=bool(self.state.cad_records); has_bom=bool(self.state.unique_parts); has_gerber=bool(self.state.gerber_documents)
        self.bom_btn.setEnabled(has_cad)
        self.gerber_btn.setEnabled(has_cad)
        ready=has_cad and has_bom and has_gerber
        self.analyze_top.setEnabled(ready); self.export_top.setEnabled(has_bom)
        if not has_cad: self.next_step.setText("Next: 1. Import CAD")
        elif not has_bom: self.next_step.setText("CAD loaded ✓   Next: 2. Import BOM")
        elif not has_gerber: self.next_step.setText("CAD ✓   BOM ✓   Next: 3. Import Gerber")
        else: self.next_step.setText("CAD ✓   BOM ✓   Gerber ✓   Next: 4. Analyze Dimensions")

    def _load_odb(self, path):
        doc=parse_odb(path)
        records=[
            CadRecord(
                ref=x.ref, mpn=x.mpn, x=x.x, y=x.y, rotation=x.rotation,
                layer=x.side,
                raw={"source":"ODB++","package":x.package,"length_mm":x.length_mm,
                     "width_mm":x.width_mm,"height_mm":x.height_mm,
                     "source_file":x.source_file, **(x.raw or {})}
            )
            for x in doc.components if x.ref
        ]
        if not records:
            details="\n".join(doc.warnings) if doc.warnings else "No component placement records were found."
            QMessageBox.warning(self,"ODB++ import",f"ODB++ was opened, but no supported component placements were found.\n\n{details}")
            return False
        self.state.odb_path=Path(path); self.state.cad_path=None
        self.state.cad_records=records; self.state.dimension_results={}; self.state.shape_models={}
        self.cad_info.setText(f"CAD: {Path(path).name} [ODB++] — {len(records)} placements; {len(doc.jobs)} job(s), {len(doc.steps)} step(s) — working units: mm")
        self.workspace.set_data(cad=records); self.workspace.fit_board(); self._update_status()
        self.tabs.setCurrentIndex(0)
        return True

    def import_cad(self):
        choice=QMessageBox(self)
        choice.setWindowTitle("1. Import CAD / ODB++")
        choice.setText("Choose the CAD data source.")
        file_btn=choice.addButton("CAD File (XLSX / XLS / CSV / TXT)",QMessageBox.ActionRole)
        odb_btn=choice.addButton("ODB++ Archive",QMessageBox.ActionRole)
        folder_btn=choice.addButton("ODB++ Folder",QMessageBox.ActionRole)
        choice.addButton(QMessageBox.Cancel)
        choice.exec()
        clicked=choice.clickedButton()
        if clicked==odb_btn:
            fn,_=QFileDialog.getOpenFileName(self,"Import ODB++ Archive","","ODB++ Archives (*.tgz *.tar.gz *.tar *.zip);;All Files (*)")
            if fn:self._load_odb(fn)
            return
        if clicked==folder_btn:
            folder=QFileDialog.getExistingDirectory(self,"Import Extracted ODB++ Folder")
            if folder:self._load_odb(folder)
            return
        if clicked!=file_btn:return
        fn,_=QFileDialog.getOpenFileName(self,"Import CAD","","CAD (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        df,det=inspect_cad(fn)
        required=("ref","x","y","rotation")
        if not all(det.get(k) for k in required):
            missing=", ".join(k.upper() for k in required if not det.get(k))
            QMessageBox.warning(self,"CAD headings not recognized",f"Required CAD heading(s) not recognized: {missing}.\n\nExpected headings include Reference/RefDes, X location, Y location, and Angle/Rotation.")
            return
        self.state.cad_path=Path(fn); self.state.odb_path=None
        self.state.cad_records=parse_cad(fn); self.state.dimension_results={}; self.state.shape_models={}
        self.cad_info.setText(f"CAD: {Path(fn).name} — {len(self.state.cad_records)} placements — units: mm")
        self.workspace.set_data(cad=self.state.cad_records); self.workspace.fit_board(); self._update_status()
        if not self.state.cad_records:
            QMessageBox.warning(self,"CAD import","No CAD placement records were found. Check the file headings and data.")
        else:
            self.tabs.setCurrentIndex(0)

    def import_bom(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import BOM","","BOM (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        df,det=inspect_bom(fn)
        if not det.get("mpn") or not det.get("ref"):
            missing=", ".join(x for x in ("Part Number / MPN" if not det.get("mpn") else "", "Reference" if not det.get("ref") else "") if x)
            QMessageBox.warning(self,"BOM headings not recognized",f"Required BOM heading(s) not recognized: {missing}.\n\nThe software maps BOM columns automatically from their headings.")
            return
        self.state.bom_path=Path(fn); self.state.bom_records=parse_bom(fn)
        self.state.unique_parts=group_unique_parts(self.state.bom_records); select_cad_aware_representatives(self.state.unique_parts,self.state.cad_records)
        cadrefs={c.ref.strip().upper() for c in self.state.cad_records}; matched=sum(any(r.strip().upper() in cadrefs for r in p.refs) for p in self.state.unique_parts)
        self.bom_info.setText(f"BOM: {Path(fn).name} — {len(self.state.unique_parts)} unique PNs; {matched} matched to CAD")
        self.state.dimension_results={}; self.state.shape_models={}; self._populate(); self._update_status()

    def import_gerber(self):
        files,_=QFileDialog.getOpenFileNames(self,"Import Gerber Layers","","Gerber (*.GTL *.GBL *.GTO *.GBO *.GTP *.GBP *.gbr *.ger *.pho *.art);;All Files (*)")
        if not files:return
        self.state.gerber_paths=[Path(x) for x in files]; self.state.gerber_documents=parse_gerber_files(files); self.state.dimension_results={}; self.state.shape_models={}
        self.gerber_info.setText("Gerber: "+", ".join(f"{d.path.name} [{d.layer}]" for d in self.state.gerber_documents))
        self.workspace.set_data(gerbers=self.state.gerber_documents); self._refresh_layers(); self.workspace.fit_board(); self._update_status()

    def _measurement_changed(self,text):
        if text:self.statusBar().showMessage(text)
        else:self.statusBar().clearMessage()

    def _alignment_changed(self):
        self.dx=self.xoff.value(); self.dy=self.yoff.value(); self.da=self.aoff.value()
        self.workspace.set_alignment(self.dx,self.dy,self.da)
        if self.state.dimension_results:
            self.state.dimension_results={}; self.state.shape_models={}
            for r in range(self.table.rowCount()): self.table.setItem(r,9,QTableWidgetItem("RE-ANALYZE AFTER ALIGNMENT"))
        self._update_status()

    def _nudge(self,x,y,a):
        self.xoff.setValue(self.xoff.value()+x); self.yoff.setValue(self.yoff.value()+y); self.aoff.setValue(self.aoff.value()+a)

    def _populate(self):
        self.table.setRowCount(len(self.state.unique_parts))
        for r,p in enumerate(self.state.unique_parts):
            for col,val in enumerate([p.representative_ref,p.mpn,"","","","","","","","WAITING"]): self.table.setItem(r,col,QTableWidgetItem(val))
        self.table.resizeColumnsToContents()

    def _move_review(self,step):
        if not self.table.rowCount(): return
        r=self.table.currentRow()
        r=(0 if r<0 else r+step)%self.table.rowCount()
        self.table.selectRow(r); self._zoom_selected()

    def _find_component(self):
        q=self.ref_search.text().strip().upper()
        if not q:return
        for r in range(self.table.rowCount()):
            if any(self.table.item(r,c) and q in self.table.item(r,c).text().upper() for c in (0,1)):
                self.table.selectRow(r); self._zoom_selected(); return

    def _zoom_selected(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        self.workspace.zoom_to_ref(self.state.unique_parts[r].representative_ref)

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
        self.review_info.setText(f"Ref {p.representative_ref} | Source {getattr(x,'source','')} | Confidence {getattr(x,'confidence','') or 'NONE'} | Body {getattr(x,'length_mm',None)} × {getattr(x,'width_mm',None)} mm | Status {getattr(x,'status','')} | Accepted {'YES' if getattr(x,'accepted',False) else 'NO'}")

    def _lookup_structured(self):
        if not self.state.unique_parts:return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for r,p in enumerate(self.state.unique_parts):
                data=lookup_mpn(p.mpn); self.state.mpn_lookup_results[p.mpn]=data
                self.table.setItem(r,2,QTableWidgetItem(data.manufacturer))
                self.table.setItem(r,3,QTableWidgetItem(data.package_type))
                self.table.setItem(r,8,QTableWidgetItem(data.source or "MPN lookup"))
                if data.status!="EXACT MPN MATCH" and not self.state.dimension_results.get(p.mpn):
                    self.table.setItem(r,9,QTableWidgetItem(data.status))
        finally:
            QApplication.restoreOverrideCursor()
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        QMessageBox.information(self,"MPN Lookup","Structured lookup complete. Exact matches populate manufacturer/package/source. Unverified physical dimensions remain blank.")

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
        analysis_docs=[d for d in self.state.gerber_documents if d.layer!="Other / Ignore"]
        gerber_results=derive_project_dimensions(self.state.unique_parts,self.state.cad_records,analysis_docs,alignment=(self.dx,self.dy,self.da))
        if self.state.odb_path:
            odb_results=derive_odb_dimensions(self.state.unique_parts,parse_odb(self.state.odb_path))
            self.state.dimension_results=merge_priority(odb_results,gerber_results)
        else:
            self.state.dimension_results=gerber_results
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        for r,p in enumerate(self.state.unique_parts):
            x=self.state.dimension_results.get(p.mpn)
            if not x:continue
            self.table.setItem(r,4,QTableWidgetItem(str(getattr(x,"length_mm","") or ""))); self.table.setItem(r,5,QTableWidgetItem(str(getattr(x,"width_mm","") or "")))
            self.table.setItem(r,6,QTableWidgetItem(str(getattr(x,"height_mm","") or "")))
            self.table.setItem(r,7,QTableWidgetItem(f"{getattr(x,'pad_count',None) or ''} / {getattr(x,'pitch_mm',None) or ''}"))
            shape=self.state.shape_models.get(p.mpn)
            if shape and shape.package_type:self.table.setItem(r,3,QTableWidgetItem(f"{shape.package_type} [{shape.package_family}]"))
            elif shape:self.table.setItem(r,3,QTableWidgetItem(shape.package_family))
            self.table.setItem(r,8,QTableWidgetItem(f"{getattr(x,'source','')} / {getattr(x,'confidence','') or 'NONE'}"))
            self.table.setItem(r,9,QTableWidgetItem(getattr(x,"status","MANUAL REVIEW")))
        self._update_status()

    def _apply_adjust(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if not x:return
        x.length_mm=round(self.manual_l.value(),4); x.width_mm=round(self.manual_w.value(),4); x.source="USER - Manual Body Adjustment"; x.confidence="USER CONFIRMED"; x.status="WAITING FOR USER ACCEPTANCE"; x.accepted=False
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        self.table.setItem(r,4,QTableWidgetItem(str(x.length_mm))); self.table.setItem(r,5,QTableWidgetItem(str(x.width_mm))); self.table.setItem(r,8,QTableWidgetItem(f"{x.source} / {x.confidence}")); self.table.setItem(r,9,QTableWidgetItem(x.status)); self._update_status()

    def _accept_dimension(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if x:
            x.accepted=True; x.status="USER ACCEPTED"
            if "User Confirmed" not in x.source:x.source=(x.source+" - User Confirmed").strip(" -")
            self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
            self.table.setItem(r,9,QTableWidgetItem(x.status)); self._update_status()

    def _reject_dimension(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if x:x.accepted=False; x.status="MANUAL REVIEW"
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        self.table.setItem(r,9,QTableWidgetItem("MANUAL REVIEW")); self._update_status()

    def _export(self):
        folder=QFileDialog.getExistingDirectory(self,"Export folder")
        if not folder:return
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        cad={c.ref:c for c in self.state.cad_records}; accepted={k:v for k,v in self.state.dimension_results.items() if getattr(v,"accepted",False)}
        export_excel(Path(folder)/"Shape_Dimensions.xlsx",self.state.unique_parts,cad,accepted); export_text(Path(folder)/"Shape_Dimensions.txt",self.state.unique_parts,accepted,self.state.shape_models)
        QMessageBox.information(self,"Export","Created Shape_Dimensions.xlsx and Shape_Dimensions.txt")

def run_app():
    app=QApplication.instance() or QApplication([]); w=MainWindow(); w.show(); app.exec()
