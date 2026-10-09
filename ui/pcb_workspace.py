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
        self.cad=[]; self.gerbers=[]; self.visible_layers=set(); self.show_refs=True
        self.dx=self.dy=self.angle=0.0; self.selected_ref=""; self.review_bbox=None
        self.gerber_opacity=.85; self.measure_mode=False; self.measure_points=[]

    def wheelEvent(self,e):
        self.scale(1.18 if e.angleDelta().y()>0 else 1/1.18,1.18 if e.angleDelta().y()>0 else 1/1.18)

    def set_data(self,cad=None,gerbers=None):
        if cad is not None:self.cad=cad
        if gerbers is not None:
            self.gerbers=gerbers; self.visible_layers={str(d.path) for d in gerbers}
        self.redraw()

    def set_alignment(self,dx,dy,angle):
        self.dx=float(dx); self.dy=float(dy); self.angle=float(angle); self.redraw()

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
        pts=[(c.x,-c.y) for c in self.cad if c.x is not None and c.y is not None]
        for d in self.gerbers:
            if str(d.path) not in self.visible_layers: continue
            b=d.bounds()
            if b:
                for x,y in ((b[0],b[1]),(b[2],b[3])):
                    x,y=self._tx(x,y); pts.append((x,-y))
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
        if c and c.x is not None and c.y is not None:
            self.resetTransform(); self.scale(18,18); self.centerOn(c.x,-c.y)

    def _tx(self,x,y):
        a=math.radians(self.angle)
        return x*math.cos(a)-y*math.sin(a)+self.dx, x*math.sin(a)+y*math.cos(a)+self.dy

    def redraw(self):
        self.scene.clear()
        gerber_pen=QPen(QColor("#FFB74D")); gerber_pen.setCosmetic(True); gerber_pen.setWidthF(.8)
        gerber_brush=QBrush(QColor("#FFB74D"))
        for d in self.gerbers:
            if str(d.path) not in self.visible_layers: continue
            for p in d.primitives:
                item=None
                if p.kind=="line" and None not in (p.x,p.y,p.x2,p.y2):
                    x1,y1=self._tx(p.x,p.y); x2,y2=self._tx(p.x2,p.y2)
                    item=self.scene.addLine(x1,-y1,x2,-y2,gerber_pen)
                elif p.kind=="flash" and p.x is not None and p.y is not None:
                    x,y=self._tx(p.x,p.y); ap=d.apertures.get(p.aperture); sx=sy=.25
                    if ap and ap.params:
                        sx=ap.params[0]; sy=ap.params[1] if len(ap.params)>1 else sx
                        if d.units=="inch": sx*=25.4; sy*=25.4
                    item=self.scene.addEllipse(x-sx/2,-y-sy/2,sx,sy,gerber_pen)
                if item:item.setOpacity(self.gerber_opacity)

        cad_pen=QPen(QColor("#E6E6E6")); cad_pen.setCosmetic(True); cad_pen.setWidthF(.8)
        sel_pen=QPen(QColor("#66FF33")); sel_pen.setCosmetic(True); sel_pen.setWidthF(2)
        for c in self.cad:
            if c.x is None or c.y is None: continue
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
