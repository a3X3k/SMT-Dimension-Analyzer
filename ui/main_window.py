from pathlib import Path
from PySide6.QtCore import QUrl,Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import *
from models import ProjectState
from parsers.cad_parser import inspect_cad,parse_cad
from parsers.bom_parser import inspect_bom,parse_bom,group_unique_parts
from parsers.gerber_parser import parse_gerber_files
from matching.representative_selector import select_cad_aware_representatives
from dimensions.gerber_dimension import derive_project_dimensions
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
        self.state=ProjectState(); self.dx=self.dy=self.da=0.0; self.alignment_confirmed=False
        self._side_alignments={}
        self._build(); self._update_status()

    def _build(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root)
        bar=QHBoxLayout(); outer.addLayout(bar)
        self.cad_btn=QPushButton("1. Import CAD"); self.cad_btn.clicked.connect(self.import_cad); bar.addWidget(self.cad_btn)
        self.bom_btn=QPushButton("2. Import BOM"); self.bom_btn.clicked.connect(self.import_bom); bar.addWidget(self.bom_btn)
        self.gerber_btn=QPushButton("3. Import Gerber Layers"); self.gerber_btn.clicked.connect(self.import_gerber); bar.addWidget(self.gerber_btn)
        bar.addWidget(QLabel("Board side:"))
        self.side_selector=QComboBox(); self.side_selector.addItems(["Top","Bottom"])
        self.side_selector.currentTextChanged.connect(self._switch_board_side); bar.addWidget(self.side_selector)
        self.fit=QPushButton("Fit Board"); self.fit.clicked.connect(lambda:self.workspace.fit_board()); bar.addWidget(self.fit)
        self.measure_btn=QPushButton("Measure"); self.measure_btn.setCheckable(True); self.measure_btn.toggled.connect(lambda v:self.workspace.set_measure_mode(v)); bar.addWidget(self.measure_btn)
        self.refs=QCheckBox("Ref Designators"); self.refs.setChecked(True); self.refs.toggled.connect(lambda v:self.workspace.toggle_refs(v)); bar.addWidget(self.refs)
        self.mpn_top=QPushButton("Lookup MPN"); self.mpn_top.clicked.connect(self._lookup_structured); bar.addWidget(self.mpn_top)
        self.analyze_top=QPushButton("4. Start PAD Match / Derive Dimensions"); self.analyze_top.clicked.connect(self._analyze); bar.addWidget(self.analyze_top)
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
        l.addWidget(QLabel("<b>CAD column mappings can be reviewed and corrected during import.</b>"))
        self.cad_info=QLabel("CAD: not loaded"); self.cad_info.setWordWrap(True); l.addWidget(self.cad_info)
        self.bom_info=QLabel("BOM: not loaded"); self.bom_info.setWordWrap(True); l.addWidget(self.bom_info)
        self.gerber_info=QLabel("Gerber: not loaded"); self.gerber_info.setWordWrap(True); l.addWidget(self.gerber_info)
        l.addStretch()

    def _layers_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"Gerber Layers")
        l.addWidget(QLabel("Import multiple Gerber files at once. Select Top/Bottom above to view one face; toggle each layer below."))
        more=QPushButton("Add More Gerber Layers"); more.clicked.connect(lambda:self.import_gerber(append=True)); l.addWidget(more)
        op=QHBoxLayout(); l.addLayout(op); op.addWidget(QLabel("Gerber opacity"))
        self.gerber_opacity=QSlider(Qt.Horizontal); self.gerber_opacity.setRange(5,100); self.gerber_opacity.setValue(85); self.gerber_opacity.valueChanged.connect(lambda v:self.workspace.set_gerber_opacity(v/100)); op.addWidget(self.gerber_opacity)
        self.opacity_label=QLabel("85%"); self.gerber_opacity.valueChanged.connect(lambda v:self.opacity_label.setText(f"{v}%")); op.addWidget(self.opacity_label)
        self.layer_table=QTableWidget(0,3); self.layer_table.setHorizontalHeaderLabels(["Visible","Gerber File","Assigned Type"])
        self.layer_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch); l.addWidget(self.layer_table,1)

    def _refresh_layers(self):
        types=["Top Silkscreen","Bottom Silkscreen","Top Solder Mask","Bottom Solder Mask","Top Paste","Bottom Paste","Top Copper","Bottom Copper","Other / Ignore"]
        self.layer_table.setRowCount(len(self.state.gerber_documents))
        for r,d in enumerate(self.state.gerber_documents):
            vis=QCheckBox(); vis.setChecked(str(d.path) in self.workspace.visible_layers); vis.toggled.connect(lambda on,p=str(d.path):self.workspace.set_layer_visible(p,on))
            box=QWidget(); bl=QHBoxLayout(box); bl.setContentsMargins(8,0,0,0); bl.addWidget(vis); bl.addStretch(); self.layer_table.setCellWidget(r,0,box)
            self.layer_table.setItem(r,1,QTableWidgetItem(d.path.name))
            combo=QComboBox(); combo.addItems(types)
            if d.layer not in types: combo.insertItem(0,d.layer)
            combo.setCurrentText(d.layer); combo.currentTextChanged.connect(lambda value,doc=d:self._assign_layer(doc,value)); self.layer_table.setCellWidget(r,2,combo)

    def _assign_layer(self,doc,value):
        doc.layer=value
        self.state.dimension_results={}; self.state.shape_models={}
        for row in range(self.table.rowCount()):
            self.table.setItem(row,10,QTableWidgetItem("RE-ANALYZE AFTER LAYER CHANGE"))
            for col in (4,5,6,7,8,9,11):
                self.table.setItem(row,col,QTableWidgetItem(""))
        self.review_info.setText("Gerber layer assignment changed. Re-analyze dimensions before accepting or exporting results.")
        self.workspace.show_review_bbox(None)
        # Diagnose import-scale mismatches using actual CAD/Gerber geometry, not
        # the selected units label or the scene's visual crosshair positions.
        cad_points=[(c.x,c.y) for c in self.state.cad_records if c.x is not None and c.y is not None]
        gerber_bounds=[d.bounds() for d in self.state.gerber_documents if d.bounds() is not None]
        if len(cad_points)>1 and gerber_bounds:
            cad_width=max(x for x,y in cad_points)-min(x for x,y in cad_points)
            gerber_width=max(b[2] for b in gerber_bounds)-min(b[0] for b in gerber_bounds)
            if cad_width>0 and gerber_width>0 and gerber_width/cad_width>10:
                # If the CAD was accidentally scaled as mils, re-read the
                # original file in mm only when its width matches the Gerber.
                try:
                    original=parse_cad(self.state.cad_path,units="mm")
                    xs=[c.x for c in original if c.x is not None]
                    source_width=max(xs)-min(xs) if len(xs)>1 else 0
                    if source_width and 0.5 <= source_width/gerber_width <= 2.0:
                        self.state.cad_records=original
                        self.workspace.set_data(cad=original)
                        cad_width=source_width
                except (ValueError,KeyError,IndexError):
                    pass
                if gerber_width/cad_width>10:
                    QMessageBox.warning(self,"CAD/Gerber coordinate mismatch",
                        f"CAD width: {cad_width:.3f} mm; Gerber width: {gerber_width:.3f} mm. "
                        "Check the CAD coordinate mapping and source units; automatic alignment was not applied.")
        self.gerber_info.setText("Gerber: "+", ".join(f"{d.path.name} [{d.layer}]" for d in self.state.gerber_documents))
        self.workspace.redraw(); self._update_status()

    def _alignment_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"CAD ↔ Gerber Alignment")
        l.addWidget(QLabel("Adjust CAD and Gerber origin crosshairs independently. X/Y values are in millimetres."))
        form=QFormLayout(); l.addLayout(form)
        self.xoff=QDoubleSpinBox(); self.yoff=QDoubleSpinBox(); self.aoff=QDoubleSpinBox()
        for s in (self.xoff,self.yoff): s.setRange(-10000,10000); s.setDecimals(4); s.setSingleStep(.01)
        self.aoff.setRange(-360,360); self.aoff.setDecimals(3); self.aoff.setSingleStep(.1)
        form.addRow("Gerber X offset (mm)",self.xoff); form.addRow("Gerber Y offset (mm)",self.yoff); form.addRow("Gerber angle (°)",self.aoff)
        for s in (self.xoff,self.yoff,self.aoff): s.valueChanged.connect(self._alignment_changed)
        n=QGridLayout(); l.addLayout(n)
        for text,dx,dy,da,r,c in [("X -0.01",-.01,0,0,0,0),("X +0.01",.01,0,0,0,1),("Y -0.01",0,-.01,0,1,0),("Y +0.01",0,.01,0,1,1),("A -0.1°",0,0,-.1,2,0),("A +0.1°",0,0,.1,2,1)]:
            b=QPushButton(text); b.clicked.connect(lambda _,x=dx,y=dy,a=da:self._nudge(x,y,a)); n.addWidget(b,r,c)
        origins=QFormLayout(); l.addLayout(origins)
        self.cad_origin_x=QDoubleSpinBox(); self.cad_origin_y=QDoubleSpinBox()
        self.gerber_origin_x=QDoubleSpinBox(); self.gerber_origin_y=QDoubleSpinBox()
        for spin in (self.cad_origin_x,self.cad_origin_y,self.gerber_origin_x,self.gerber_origin_y):
            spin.setRange(-10000,10000); spin.setDecimals(4); spin.setSingleStep(.1)
            spin.valueChanged.connect(self._crosshair_changed)
        origins.addRow("CAD origin X (mm)",self.cad_origin_x)
        origins.addRow("CAD origin Y (mm)",self.cad_origin_y)
        origins.addRow("Gerber origin X (mm)",self.gerber_origin_x)
        origins.addRow("Gerber origin Y (mm)",self.gerber_origin_y)
        self.alignment_status=QLabel("Alignment not confirmed")
        l.addWidget(self.alignment_status)
        confirm=QPushButton("Confirm Alignment / Enable PAD Match")
        confirm.clicked.connect(self._confirm_alignment)
        l.addWidget(confirm)
        l.addStretch()

    def _confirm_alignment(self):
        if not self.state.cad_records or not self.state.gerber_documents:
            QMessageBox.warning(self,"Alignment","Import CAD and Gerber before confirming alignment.")
            return
        self.alignment_confirmed=True
        self.alignment_status.setText("Alignment confirmed — PAD matching enabled")
        self._save_side_alignment()
        self._update_status()

    def _review_tab(self):
        w=QWidget(); l=QVBoxLayout(w); self.tabs.addTab(w,"Component Review")
        nav=QHBoxLayout(); l.addLayout(nav)
        prev=QPushButton("◀ Previous"); prev.clicked.connect(lambda:self._move_review(-1)); nav.addWidget(prev)
        self.ref_search=QLineEdit(); self.ref_search.setPlaceholderText("Find Ref / MPN"); self.ref_search.returnPressed.connect(self._find_component); nav.addWidget(self.ref_search,1)
        nxt=QPushButton("Next ▶"); nxt.clicked.connect(lambda:self._move_review(1)); nav.addWidget(nxt)
        self.table=QTableWidget(0,12)
        self.table.setHorizontalHeaderLabels(["Ref","MPN","Manufacturer","Package/Type","Body L (mm)","Body W (mm)","Body H (mm)","Paste Envelope L×W (mm)","Paste Pad L×W / Count / Pitch (mm)","Dimension Source / Confidence","Review Status","Paste Evidence"])
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
        ready=has_cad and has_bom and has_gerber and self.alignment_confirmed
        self.analyze_top.setEnabled(ready); self.export_top.setEnabled(has_bom)
        if not has_cad: self.next_step.setText("Next: 1. Import CAD")
        elif not has_bom: self.next_step.setText("CAD loaded ✓   Next: 2. Import BOM")
        elif not has_gerber: self.next_step.setText("CAD ✓   BOM ✓   Next: 3. Import Gerber")
        else: self.next_step.setText("CAD ✓   BOM ✓   Gerber ✓   Next: 4. Analyze Dimensions")

    def import_cad(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import CAD","","CAD (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        try:
            df,det=inspect_cad(fn)
            from ui.mapping_dialog import ColumnMappingDialog
            fields=[("ref","Reference / RefDes",True),("x","X Coordinate",True),
                    ("y","Y Coordinate",True),("rotation","Angle / Rotation",True),
                    ("mpn","Part Number / MPN",False),("layer","Top / Bottom / Mirror",False)]
            dialog=ColumnMappingDialog("Confirm CAD column mapping",list(df.columns),fields,det,self)
            if dialog.exec()!=QDialog.Accepted:return
            units,ok=QInputDialog.getItem(self,"CAD coordinate units","Coordinates in source file:",["Millimetres (mm)","Mils (1/1000 inch)"],0,False)
            if not ok:return
            unit_key="mils" if units.startswith("Mils") else "mm"
            records=parse_cad(fn,mapping=dialog.mapping(),units=unit_key)
            if not records:
                QMessageBox.warning(self,"CAD import","No CAD placement records found.");return
        except Exception as exc:
            QMessageBox.warning(self,"CAD import error",str(exc));return
        self._side_alignments.clear()
        self.alignment_confirmed=False
        self.alignment_status.setText("Alignment not confirmed")
        self.state.cad_path=Path(fn)
        self.state.cad_records=records
        # A new CAD file defines a new board: discard all dependent prior data.
        self.state.bom_path=None; self.state.bom_records=[]; self.state.unique_parts=[]
        self.state.gerber_paths=[]; self.state.gerber_documents=[]
        self.state.dimension_results={}; self.state.shape_models={}
        self.state.mpn_lookup_results={}; self.state.manual_gerber_matches={}
        self.dx=self.dy=self.da=0.0
        for spin in (self.xoff,self.yoff,self.aoff):
            spin.blockSignals(True); spin.setValue(0.0); spin.blockSignals(False)
        self.workspace.set_alignment(0,0,0)
        self.side_selector.setCurrentText("Top")
        self.workspace.set_data(cad=records,gerbers=[])
        self.layer_table.setRowCount(0); self.table.setRowCount(0)
        self.bom_info.setText('BOM: not loaded')
        self.gerber_info.setText('Gerber: not loaded')
        self.cad_info.setText(f"CAD: {Path(fn).name} — {len(records)} placements — coordinates converted to mm")
        self.workspace.fit_board();self._update_status()
        self.tabs.setCurrentIndex(0)

    def import_bom(self):
        fn,_=QFileDialog.getOpenFileName(self,"Import BOM","","BOM (*.xlsx *.xls *.csv *.txt)")
        if not fn:return
        df,det=inspect_bom(fn)
        if not det.get("mpn") or not det.get("ref"):
            missing=", ".join(x for x in ("Part Number / MPN" if not det.get("mpn") else "", "Reference" if not det.get("ref") else "") if x)
            QMessageBox.warning(self,"BOM headings not recognized",f"Required BOM heading(s) not recognized: {missing}.\n\nThe software maps BOM columns automatically from their headings.")
            return
        from matching.bom_cad_matcher import match_bom_to_cad
        try:
            records=parse_bom(fn)
            stats=match_bom_to_cad(self.state.cad_records,records)
        except ValueError as exc:
            QMessageBox.warning(self,"BOM reference matching",str(exc))
            return
        self.state.bom_path=Path(fn);self.state.bom_records=records
        self.state.unique_parts=group_unique_parts(records)
        select_cad_aware_representatives(self.state.unique_parts,self.state.cad_records)
        self.bom_info.setText(
            f"BOM: {Path(fn).name} — {len(self.state.unique_parts)} unique PNs; "
            f"{len(stats['matched'])} references matched to CAD; "
            f"{len(stats['bom_only'])} BOM-only; {len(stats['cad_only'])} CAD-only")
        self.state.dimension_results={}; self.state.shape_models={}; self._populate(); self._update_status()

    def _switch_board_side(self,side):
        self._restore_side_alignment(side)
        self.workspace.set_board_side(side)
        self.workspace.show_review_bbox(None)
        self.workspace.fit_board()

    def _save_side_alignment(self):
        if not hasattr(self,"_side_alignments") or not hasattr(self,"cad_origin_x"):
            return
        side=self.workspace.board_side
        self._side_alignments[side]=(
            self.xoff.value(),self.yoff.value(),self.aoff.value(),
            self.cad_origin_x.value(),self.cad_origin_y.value(),
            self.gerber_origin_x.value(),self.gerber_origin_y.value(),
            self.alignment_confirmed)

    def _restore_side_alignment(self,side):
        if not hasattr(self,"_side_alignments"):
            self._side_alignments={}
        if side==self.workspace.board_side:return
        values=self._side_alignments.get(side,(0.0,)*7+(False,))
        from PySide6.QtCore import QSignalBlocker
        spins=(self.xoff,self.yoff,self.aoff,self.cad_origin_x,self.cad_origin_y,
               self.gerber_origin_x,self.gerber_origin_y)
        blockers=[QSignalBlocker(spin) for spin in spins]
        for spin,value in zip(spins,values[:7]):spin.setValue(value)
        del blockers
        self.dx,self.dy,self.da=values[:3]
        self.alignment_confirmed=values[7]
        self.workspace.set_alignment(self.dx,self.dy,self.da)
        self.workspace.set_crosshair_origins(*values[3:7])
        self.alignment_status.setText(
            "Alignment confirmed — PAD matching enabled" if self.alignment_confirmed
            else "Alignment not confirmed for "+side)
        self._update_status()

    def import_gerber(self,append=False):
        files,_=QFileDialog.getOpenFileNames(self,"Import Gerber Layers","","Gerber (*.GTL *.GBL *.GTO *.GBO *.GTS *.GBS *.GTP *.GBP *.gbr *.ger *.pho *.art);;All Files (*)")
        if not files:return
        existing=self.state.gerber_paths if append else []
        paths=list(dict.fromkeys([*existing,*(Path(x) for x in files)]))
        previous_visible=set(self.workspace.visible_layers) if append else set()
        self.state.gerber_paths=paths; self.state.gerber_documents=parse_gerber_files(paths); self.state.dimension_results={}; self.state.shape_models={}
        self._side_alignments.clear()
        self.alignment_confirmed=False; self.alignment_status.setText("Gerber layers changed — confirm alignment")
        self.workspace.set_data(gerbers=self.state.gerber_documents)
        if append:
            self.workspace.visible_layers=previous_visible | {str(p) for p in paths if p not in existing}
        self.gerber_info.setText("Gerber: "+", ".join(f"{d.path.name} [{d.layer}]" for d in self.state.gerber_documents))
        self._refresh_layers(); self.workspace.fit_board(); self._update_status()

    def _measurement_changed(self,text):
        if text:self.statusBar().showMessage(text)
        else:self.statusBar().clearMessage()

    def _crosshair_changed(self):
        self._save_side_alignment()
        self.workspace.set_crosshair_origins(
            self.cad_origin_x.value(),self.cad_origin_y.value(),
            self.gerber_origin_x.value(),self.gerber_origin_y.value())

    def _alignment_changed(self):
        self.dx=self.xoff.value(); self.dy=self.yoff.value(); self.da=self.aoff.value()
        self.alignment_confirmed=False
        self.alignment_status.setText("Alignment changed — confirmation required")
        self._save_side_alignment()
        self.workspace.set_alignment(self.dx,self.dy,self.da)
        if self.state.dimension_results:
            self.state.dimension_results={}; self.state.shape_models={}
            for r in range(self.table.rowCount()): self.table.setItem(r,10,QTableWidgetItem("RE-ANALYZE AFTER ALIGNMENT"))
        self._update_status()

    def _nudge(self,x,y,a):
        self.xoff.setValue(self.xoff.value()+x); self.yoff.setValue(self.yoff.value()+y); self.aoff.setValue(self.aoff.value()+a)

    def _populate(self):
        self.table.setRowCount(len(self.state.unique_parts))
        for r,p in enumerate(self.state.unique_parts):
            for col,val in enumerate([p.representative_ref,p.mpn,"","","","","","","","","WAITING",""]): self.table.setItem(r,col,QTableWidgetItem(val))
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
                # Columns 8/9 are paste detail and dimension source respectively.
                self.table.setItem(r,9,QTableWidgetItem(data.source or "MPN lookup"))
                if data.status!="EXACT MPN MATCH" and not self.state.dimension_results.get(p.mpn):
                    self.table.setItem(r,10,QTableWidgetItem(data.status))
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
        if not self.alignment_confirmed:
            QMessageBox.warning(self,"Alignment","Confirm CAD / Gerber alignment before PAD matching."); return
        if not (self.state.cad_records and self.state.unique_parts and self.state.gerber_documents):
            QMessageBox.warning(self,"Missing input","Import CAD, BOM and Gerber before analysis."); return
        analysis_docs=[d for d in self.state.gerber_documents if d.layer!="Other / Ignore"]
        gerber_results=derive_project_dimensions(self.state.unique_parts,self.state.cad_records,analysis_docs,alignment=(self.dx,self.dy,self.da))
        self.state.dimension_results=gerber_results
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        for r,p in enumerate(self.state.unique_parts):
            x=self.state.dimension_results.get(p.mpn)
            if not x:continue
            self.table.setItem(r,4,QTableWidgetItem(str(getattr(x,"length_mm","") or ""))); self.table.setItem(r,5,QTableWidgetItem(str(getattr(x,"width_mm","") or "")))
            self.table.setItem(r,6,QTableWidgetItem(str(getattr(x,"height_mm","") or "")))
            pl=getattr(x,'paste_length_mm',None); pw=getattr(x,'paste_width_mm',None)
            padl=getattr(x,'paste_pad_length_mm',None); padw=getattr(x,'paste_pad_width_mm',None)
            self.table.setItem(r,7,QTableWidgetItem(f"{pl or ''} × {pw or ''}" if pl and pw else ""))
            self.table.setItem(r,8,QTableWidgetItem(f"{padl or ''} × {padw or ''} / {getattr(x,'pad_count',None) or ''} / {getattr(x,'pitch_mm',None) or ''}" if getattr(x,'pad_count',None) else ""))
            shape=self.state.shape_models.get(p.mpn)
            if shape and shape.package_type:self.table.setItem(r,3,QTableWidgetItem(f"{shape.package_type} [{shape.package_family}]"))
            elif shape:self.table.setItem(r,3,QTableWidgetItem(shape.package_family))
            self.table.setItem(r,9,QTableWidgetItem(f"{getattr(x,'source','')} / {getattr(x,'confidence','') or 'NONE'}"))
            self.table.setItem(r,10,QTableWidgetItem(getattr(x,"status","MANUAL REVIEW")))
            self.table.setItem(r,11,QTableWidgetItem("Paste geometry only — not body size" if getattr(x,'paste_length_mm',None) else ""))
        self._update_status()

    def _apply_adjust(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if not x:return
        x.length_mm=round(self.manual_l.value(),4); x.width_mm=round(self.manual_w.value(),4); x.source="USER - Manual Body Adjustment"; x.confidence="USER CONFIRMED"; x.status="WAITING FOR USER ACCEPTANCE"; x.accepted=False
        # A manual edit is user-authored body evidence, not Gerber evidence.
        # Preserve that provenance through ShapeModel rebuild/export.
        x.manual_body_override=True
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        self.table.setItem(r,4,QTableWidgetItem(str(x.length_mm))); self.table.setItem(r,5,QTableWidgetItem(str(x.width_mm))); self.table.setItem(r,9,QTableWidgetItem(f"{x.source} / {x.confidence}")); self.table.setItem(r,10,QTableWidgetItem(x.status)); self._update_status()

    def _accept_dimension(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if x:
            x.accepted=True; x.status="USER ACCEPTED"
            if "User Confirmed" not in x.source:x.source=(x.source+" - User Confirmed").strip(" -")
            self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
            self.table.setItem(r,10,QTableWidgetItem(x.status)); self._update_status()

    def _reject_dimension(self):
        r=self.table.currentRow()
        if r<0 or r>=len(self.state.unique_parts):return
        x=self.state.dimension_results.get(self.state.unique_parts[r].mpn)
        if x:x.accepted=False; x.status="MANUAL REVIEW"
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        self.table.setItem(r,10,QTableWidgetItem("MANUAL REVIEW")); self._update_status()

    def _export(self):
        folder=QFileDialog.getExistingDirectory(self,"Export folder")
        if not folder:return
        self.state.shape_models=build_project_shapes(self.state.unique_parts,self.state.cad_records,self.state.dimension_results,self.state.mpn_lookup_results)
        cad={c.ref:c for c in self.state.cad_records}
        # Export all measurement evidence. Exporters independently gate
        # unaccepted body dimensions while retaining paste-only evidence.
        export_excel(Path(folder)/"Shape_Dimensions.xlsx",self.state.unique_parts,cad,self.state.dimension_results,self.state.shape_models)
        export_text(Path(folder)/"Shape_Dimensions.txt",self.state.unique_parts,self.state.dimension_results,self.state.shape_models)
        QMessageBox.information(self,"Export","Created Shape_Dimensions.xlsx and Shape_Dimensions.txt")

def run_app():
    app=QApplication.instance() or QApplication([]); w=MainWindow(); w.show(); app.exec()
