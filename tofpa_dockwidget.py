import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.core import QgsMapLayerProxyModel

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tofpa_panel_base.ui'))


class TofpaDockWidget(QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()
    calculateClicked = pyqtSignal()
    closeClicked = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(TofpaDockWidget, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)
        
        # Configure layer combo boxes to only show vector layers
        self.runwayLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.thresholdLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        
        # Set default values from original script
        self.initialWidthSpin.setValue(180.0)
        self.maxWidthSpin.setValue(1800.0)
        self.clearwayLengthSpin.setValue(0.0)
        self.initialElevationSpin.setValue(0.0)
        self.endElevationSpin.setValue(0.0)
        self.exportToKmzCheckBox.setChecked(False)
        self.useSelectedFeatureCheckBox.setChecked(True)
        self.directionCombo.setCurrentIndex(1)  # Default to "End to Start (-1)"
        
        # Connect signals
        self.calculateButton.clicked.connect(self.on_calculate_clicked)
        self.cancelButton.clicked.connect(self.on_close_clicked)

    def on_calculate_clicked(self):
        """Emit signal when calculate button is clicked"""
        self.calculateClicked.emit()
    
    def on_close_clicked(self):
        """Emit signal when close button is clicked"""
        self.closeClicked.emit()

    def get_parameters(self):
        """Get all parameters from the UI"""
        # Get direction value: index 0 = 0 (start to end), index 1 = -1 (end to start)
        direction_value = 0 if self.directionCombo.currentIndex() == 0 else -1
        
        return {
            'width_tofpa': self.initialWidthSpin.value(),
            'max_width_tofpa': self.maxWidthSpin.value(),
            'cwy_length': self.clearwayLengthSpin.value(),
            'z0': self.initialElevationSpin.value(),
            'ze': self.endElevationSpin.value(),
            's': direction_value,
            'runway_layer_id': self.runwayLayerCombo.currentLayer().id() if self.runwayLayerCombo.currentLayer() else None,
            'threshold_layer_id': self.thresholdLayerCombo.currentLayer().id() if self.thresholdLayerCombo.currentLayer() else None,
            'use_selected_feature': self.useSelectedFeatureCheckBox.isChecked(),
            'export_kmz': self.exportToKmzCheckBox.isChecked()
        }

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
