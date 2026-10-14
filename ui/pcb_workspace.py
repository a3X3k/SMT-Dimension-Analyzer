import math
from PySide6.QtCore import Qt,QPointF,Signal
from PySide6.QtGui import QColor,QPen,QBrush,QPainter,QPainterPath
from PySide6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsSimpleTextItem,QGraphicsRectItem,QGraphicsItem

class PCBWorkspace(QGraphicsView):
    componentClicked=Signal(str)
    measurementChanged=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.scene=QGraphicsScene(self); self.setScene(self.scene)
        self.setRenderHints(self.renderHints()|QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QColor("#292929"))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.cad=[]; self.gerbers=[]; self.visible_layers=set(); self.show_refs=True; self.board_side='Top'
        self.dx=self.dy=self.angle=0.0; self.layer_offsets={}; self.selected_ref=""; self.review_bbox=None
        self.gerber_opacity=.85; self.measure_mode=False; self.measure_points=[]; self.origin_point=None; self.cad_origin=(0.0,0.0); self.gerber_origin=(0.0,0.0)

    def wheelEvent(self,e):
        self.scale(1.18 if e.angleDelta().y()>0 else 1/1.18,1.18 if e.angleDelta().y()>0 else 1/1.18)

    def set_data(self,cad=None,gerbers=None):
        if cad is not None:self.cad=cad
        if gerbers is not None:
            self.gerbers=gerbers; self.visible_layers={str(d.path) for d in gerbers}
            self.layer_offsets={key:value for key,value in self.layer_offsets.items() if key in self.visible_layers}
        self.redraw()

    def set_crosshair_origins(self,cad_x,cad_y,gerber_x,gerber_y):
        self.cad_origin=(float(cad_x),float(cad_y))
        self.gerber_origin=(float(gerber_x),float(gerber_y))
        self.redraw()

    def set_origin_point(self,x,y):
        self.origin_point=(float(x),float(y)) if x is not None and y is not None else None
        self.redraw()

    def set_board_side(self,side):
        if side not in ('Top','Bottom'):
            raise ValueError('Board side must be Top or Bottom')
        self.board_side=side
        self.measure_points=[]
        self.redraw()

    def _cad_on_side(self,c):
        value=(c.layer or '').strip().lower()
        if value in ('bottom','bot','b','back','bottom side','bottom layer'):
            return self.board_side=='Bottom'
        if value in ('top','t','front','top side','top layer'):
            return self.board_side=='Top'
        # Unknown side is not safe to show on both board faces.
        return self.board_side=='Top'

    def _gerber_on_side(self,d):
        return d.layer.startswith(self.board_side+' ') or (
            self.board_side=='Top' and d.layer in ('Other / Ignore','Unknown','Manual Mapping Required'))

    def set_alignment(self,dx,dy,angle):
        self.dx=float(dx); self.dy=float(dy); self.angle=float(angle); self.redraw()

    def set_layer_offset(self,path,dx,dy):
        self.layer_offsets[str(path)]=(float(dx),float(dy))
        self.redraw()

    def toggle_refs(self,on): self.show_refs=on; self.redraw()

    def set_layer_visible(self,path,on):
        key=str(path)
        if on:self.visible_layers.add(key)
        else:self.visible_layers.discard(key)
        self.redraw()

    def set_gerber_opacity(self,value):
        self.gerber_opacity=max(0.05,min(1.0,float(value))); self.redraw()

    def set_measure_mode(self,on):
        self.measure_mode=bool(on); self.measure_points=[]
        self.setDragMode(QGraphicsView.NoDrag if on else QGraphicsView.ScrollHandDrag)
        self.setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)
        self.measurementChanged.emit("Measure: click two points (mm)." if on else "")
        self.redraw()

    def fit_board(self):
        pts=[(c.x,-c.y) for c in self.cad if c.x is not None and c.y is not None and self._cad_on_side(c)]
        for d in self.gerbers:
            if str(d.path) not in self.visible_layers or not self._gerber_on_side(d): continue
            b=d.bounds()
            if b:
                for x,y in ((b[0],b[1]),(b[2],b[3])):
                    x,y=self._tx(x,y,str(d.path)); pts.append((x,-y))
        if pts:
            xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
            from PySide6.QtCore import QRectF
            r=QRectF(min(xs),min(ys),max(max(xs)-min(xs),1),max(max(ys)-min(ys),1))
            pad=max(r.width(),r.height())*.025
            self.fitInView(r.adjusted(-pad,-pad,pad,pad),Qt.KeepAspectRatio)

    def select_ref(self,ref): self.selected_ref=ref; self.redraw()
    def show_review_bbox(self,bbox): self.review_bbox=bbox; self.redraw()

    def zoom_to_ref(self,ref):
        self.selected_ref=ref; self.redraw()
        c=next((x for x in self.cad if x.ref==ref),None)
        if c and c.x is not None and c.y is not None and self._cad_on_side(c):
            self.resetTransform(); self.scale(18,18); self.centerOn(c.x,-c.y)

    def _tx(self,x,y,layer_path=None):
        a=math.radians(self.angle)
        ox,oy=self.layer_offsets.get(layer_path,(0.0,0.0))
        return x*math.cos(a)-y*math.sin(a)+self.dx+ox, x*math.sin(a)+y*math.cos(a)+self.dy+oy

    def _draw_origin_crosshair(self,x,y,color,label):
        from PySide6.QtCore import QRectF
        pen=QPen(QColor(color)); pen.setCosmetic(True); pen.setWidthF(1.5)
        extent=150.0
        self.scene.addLine(x-extent,-y,x+extent,-y,pen)
        self.scene.addLine(x,-y-extent,x,-y+extent,pen)
        text=self.scene.addSimpleText(label)
        text.setBrush(QBrush(QColor(color)))
        text.setPos(x+1,-y+1)
        text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)

    def redraw(self):
        self.scene.clear()
        # Batch Gerber geometry by layer: a single graphics item per layer
        # avoids thousands of QGraphicsItem allocations on every alignment nudge.
        gerber_pen=QPen(QColor("#FFB74D")); gerber_pen.setCosmetic(True); gerber_pen.setWidthF(.8)
        for d in self.gerbers:
            if str(d.path) not in self.visible_layers or not self._gerber_on_side(d): continue
            path=QPainterPath()
            for p in d.primitives:
                if p.kind=="line" and None not in (p.x,p.y,p.x2,p.y2):
                    x1,y1=self._tx(p.x,p.y,str(d.path)); x2,y2=self._tx(p.x2,p.y2,str(d.path))
                    path.moveTo(x1,-y1); path.lineTo(x2,-y2)
                elif p.kind=="flash" and p.x is not None and p.y is not None:
                    x,y=self._tx(p.x,p.y,str(d.path)); ap=d.apertures.get(p.aperture); sx=sy=.25
                    if ap and ap.params:
                        sx=ap.params[0]; sy=ap.params[1] if len(ap.params)>1 else sx
                        if d.units=="inch": sx*=25.4; sy*=25.4
                    path.addEllipse(x-sx/2,-y-sy/2,sx,sy)
            if not path.isEmpty():
                item=self.scene.addPath(path,gerber_pen)
                item.setOpacity(self.gerber_opacity)

        cad_pen=QPen(QColor("#E6E6E6")); cad_pen.setCosmetic(True); cad_pen.setWidthF(.8)
        sel_pen=QPen(QColor("#66FF33")); sel_pen.setCosmetic(True); sel_pen.setWidthF(2)
        for c in self.cad:
            if c.x is None or c.y is None or not self._cad_on_side(c): continue
            pen=sel_pen if c.ref==self.selected_ref else cad_pen
            r=QGraphicsRectItem(-.65,-.45,1.3,.9); r.setPos(c.x,-c.y); r.setRotation(-(c.rotation or 0))
            r.setPen(pen); r.setData(0,c.ref); self.scene.addItem(r)
            h=self.scene.addLine(c.x-.35,-c.y,c.x+.35,-c.y,pen); h.setData(0,c.ref)
            v=self.scene.addLine(c.x,-c.y-.35,c.x,-c.y+.35,pen); v.setData(0,c.ref)
            if self.show_refs:
                t=QGraphicsSimpleTextItem(c.ref); t.setBrush(QBrush(QColor("#D8D8D8")))
                t.setPos(c.x+.75,-c.y-.65); t.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations); t.setData(0,c.ref); self.scene.addItem(t)

        if self.review_bbox:
            b=self.review_bbox; pen=QPen(QColor("#66FF33")); pen.setCosmetic(True); pen.setWidthF(2.5)
            self.scene.addRect(b[0],-b[3],b[2]-b[0],b[3]-b[1],pen)

        # Draw both independently adjustable origin markers on the active board side.
        cx,cy=self.cad_origin
        gx,gy=self._tx(*self.gerber_origin)
        self._draw_origin_crosshair(cx,cy,"#00E5FF","CAD origin (0,0)")
        self._draw_origin_crosshair(gx,gy,"#FF80AB","Gerber origin (0,0)")

        if self.origin_point is not None:
            ox,oy=self.origin_point
            pen=QPen(QColor("#00E5FF")); pen.setCosmetic(True); pen.setWidthF(2)
            self.scene.addLine(ox-2,-oy,ox+2,-oy,pen)
            self.scene.addLine(ox,-oy-2,ox,-oy+2,pen)
            marker=QGraphicsSimpleTextItem("Origin (0, 0)")
            marker.setBrush(QBrush(QColor("#00E5FF")))
            marker.setPos(ox+1,-oy+1)
            marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            self.scene.addItem(marker)
        if len(self.measure_points)==2:
            a,b=self.measure_points; pen=QPen(QColor("#66FF33")); pen.setCosmetic(True); pen.setWidthF(2)
            self.scene.addLine(a.x(),a.y(),b.x(),b.y(),pen)
            dx=b.x()-a.x(); dy=-(b.y()-a.y()); dist=math.hypot(dx,dy)
            t=QGraphicsSimpleTextItem(f"{dist:.4f} mm"); t.setBrush(QBrush(QColor("#66FF33")))
            t.setPos((a.x()+b.x())/2,(a.y()+b.y())/2); t.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations); self.scene.addItem(t)

        if self.scene.items(): self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def mousePressEvent(self,e):
        if self.measure_mode and e.button()==Qt.LeftButton:
            p=self.mapToScene(e.position().toPoint())
            if len(self.measure_points)>=2:self.measure_points=[]
            self.measure_points.append(p)
            if len(self.measure_points)==2:
                a,b=self.measure_points; dx=b.x()-a.x(); dy=-(b.y()-a.y())
                self.measurementChanged.emit(f"Measure: ΔX {dx:.4f} mm | ΔY {dy:.4f} mm | Distance {math.hypot(dx,dy):.4f} mm")
            self.redraw(); return
        if e.button()==Qt.LeftButton:
            item=self.itemAt(e.position().toPoint())
            if item:
                ref=item.data(0)
                if ref:self.componentClicked.emit(str(ref)); return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self,e):
        item=self.itemAt(e.position().toPoint())
        if item:
            ref=item.data(0)
            if ref:self.componentClicked.emit(str(ref)); self.zoom_to_ref(str(ref)); return
        super().mouseDoubleClickEvent(e)
