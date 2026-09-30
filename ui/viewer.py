from PySide6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsTextItem
class PCBViewer(QGraphicsView):
    def __init__(self,parent=None):
        super().__init__(parent); s=QGraphicsScene(self); s.addItem(QGraphicsTextItem("PCB Viewer — geometry visualization.")); self.setScene(s)
