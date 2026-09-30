import math
from PySide6.QtCore import Qt,QPointF,Signal
from PySide6.QtGui import QColor,QPen,QBrush,QPainterPath,QTransform,QPainter
from PySide6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsSimpleTextItem,QGraphicsEllipseItem,QGraphicsPathItem,QGraphicsRectItem

class PCBWorkspace(QGraphicsView):
    componentClicked=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self.scene=QGraphicsScene(self); self.setScene(self.scene)
        self.setRenderHints(self.renderHints()|QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag); self.setBackgroundBrush(QColor("#10151b"))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.cad=[]; self.gerbers=[]; self.visible_layers=set(); self.show_refs=True; self.dx=0.; self.dy=0.; self.angle=0.; self.selected_ref=""; self.review_bbox=None
    def wheelEvent(self,e):
        f=1.18 if e.angleDelta().y()>0 else 1/1.18; self.scale(f,f)
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
    def fit_board(self):
        r=self.scene.itemsBoundingRect()
        if not r.isNull(): self.fitInView(r.adjusted(-5,-5,5,5),Qt.KeepAspectRatio)
    def select_ref(self,ref): self.selected_ref=ref; self.redraw()
    def show_review_bbox(self,bbox): self.review_bbox=bbox; self.redraw()
    def zoom_to_ref(self,ref):
        self.selected_ref=ref; self.redraw()
        c=next((x for x in self.cad if x.ref==ref),None)
        if c and c.x is not None and c.y is not None:
            self.centerOn(c.x,-c.y); self.resetTransform(); self.scale(18,18)
    def _tx(self,x,y):
        a=math.radians(self.angle); return (x*math.cos(a)-y*math.sin(a)+self.dx, x*math.sin(a)+y*math.cos(a)+self.dy)
    def redraw(self):
        self.scene.clear()
        gerber_pen=QPen(QColor("#46d37b")); gerber_pen.setCosmetic(True); gerber_pen.setWidthF(0.8)
        for d in self.gerbers:
            for p in d.primitives:
                if p.kind=="line" and None not in (p.x,p.y,p.x2,p.y2):
                    x1,y1=self._tx(p.x,p.y); x2,y2=self._tx(p.x2,p.y2); self.scene.addLine(x1,-y1,x2,-y2,gerber_pen)
                elif p.kind=="flash" and p.x is not None and p.y is not None:
                    x,y=self._tx(p.x,p.y); ap=d.apertures.get(p.aperture); sx=sy=.25
                    if ap and ap.params:
                        sx=ap.params[0]; sy=ap.params[1] if len(ap.params)>1 else sx
                        if d.units=="inch": sx*=25.4; sy*=25.4
                    self.scene.addEllipse(x-sx/2,-y-sy/2,sx,sy,gerber_pen)
        cad_pen=QPen(QColor("#4aa3ff")); cad_pen.setCosmetic(True)
        sel_pen=QPen(QColor("#ffcc4d")); sel_pen.setCosmetic(True); sel_pen.setWidthF(2)
        for c in self.cad:
            if c.x is None or c.y is None: continue
            pen=sel_pen if c.ref==self.selected_ref else cad_pen
            r=QGraphicsRectItem(c.x-0.65,-c.y-0.45,1.3,.9); r.setPen(pen); r.setRotation(-(c.rotation or 0)); r.setData(0,c.ref); self.scene.addItem(r)
            self.scene.addLine(c.x-.9,-c.y,c.x+.9,-c.y,pen); self.scene.addLine(c.x,-c.y-.9,c.x,-c.y+.9,pen)
            if self.show_refs:
                t=QGraphicsSimpleTextItem(c.ref); t.setBrush(QBrush(QColor("#e9eef5"))); t.setPos(c.x+.8,-c.y-.8); t.setFlag(t.ItemIgnoresTransformations); self.scene.addItem(t)
        if self.review_bbox:
            b=self.review_bbox; pen=QPen(QColor("#ff4d6d")); pen.setCosmetic(True); pen.setWidthF(2.5)
            self.scene.addRect(b[0],-b[3],b[2]-b[0],b[3]-b[1],pen)
        if self.scene.items(): self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-10,-10,10,10))
    def mouseDoubleClickEvent(self,e):
        item=self.itemAt(e.position().toPoint())
        while item:
            ref=item.data(0)
            if ref: self.componentClicked.emit(str(ref)); break
            item=item.parentItem()
        super().mouseDoubleClickEvent(e)
