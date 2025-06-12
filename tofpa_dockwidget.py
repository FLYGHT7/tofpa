import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import QDockWidget

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tofpa_dockwidget_base.ui'))


class TofpaDockWidget(QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(TofpaDockWidget, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)
        
        # Initialize any UI components or connections here
        # This would be similar to what you had in your dialog/popup

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
