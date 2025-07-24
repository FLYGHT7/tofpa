"""
FLYGHT7
"""
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.core import QgsMapLayerProxyModel, QgsWkbTypes

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
        
        # Configure layer combo boxes with specific geometry filters
        # Runway Layer: Only LineString geometries (lines)
        self.runwayLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.runwayLayerCombo.setExceptedLayerList([])
        
        # Threshold Layer: Only Point geometries  
        self.thresholdLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.thresholdLayerCombo.setExceptedLayerList([])
        
        # Apply geometry-specific filters
        self._apply_geometry_filters()
        
        # Connect to layer changes to refresh filters
        try:
            from qgis.core import QgsProject
            QgsProject.instance().layersAdded.connect(self._on_layers_changed)
            QgsProject.instance().layersRemoved.connect(self._on_layers_changed)
        except Exception:
            pass  # Fallback if QGIS not available
        
        # Set default values from original script
        self.initialWidthSpin.setValue(180.0)
        self.maxWidthSpin.setValue(1800.0)
        self.clearwayLengthSpin.setValue(0.0)
        self.initialElevationSpin.setValue(0.0)
        self.endElevationSpin.setValue(0.0)
        self.exportToKmzCheckBox.setChecked(False)
        self.useSelectedFeatureCheckBox.setChecked(True)
        self.directionCombo.setCurrentIndex(0)  # Default to "Start to End (0)"
        
        # Connect signals
        self.calculateButton.clicked.connect(self.on_calculate_clicked)
        self.cancelButton.clicked.connect(self.on_close_clicked)

    def _apply_geometry_filters(self):
        """Apply geometry-specific filters to layer combo boxes"""
        from qgis.core import QgsProject
        
        # Get all vector layers
        all_layers = QgsProject.instance().mapLayers().values()
        vector_layers = [layer for layer in all_layers if hasattr(layer, 'geometryType')]
        
        # Lists to store layers that don't match geometry requirements
        non_line_layers = []
        non_point_layers = []
        
        for layer in vector_layers:
            try:
                geom_type = layer.geometryType()
                
                # For runway combo: exclude non-line layers
                if geom_type != QgsWkbTypes.LineGeometry:
                    non_line_layers.append(layer)
                
                # For threshold combo: exclude non-point layers  
                if geom_type != QgsWkbTypes.PointGeometry:
                    non_point_layers.append(layer)
                    
            except Exception as e:
                # If we can't determine geometry type, exclude from both
                non_line_layers.append(layer)
                non_point_layers.append(layer)
        
        # Apply filters
        self.runwayLayerCombo.setExceptedLayerList(non_line_layers)
        self.thresholdLayerCombo.setExceptedLayerList(non_point_layers)

    def _on_layers_changed(self):
        """Refresh geometry filters when layers are added or removed"""
        try:
            self._apply_geometry_filters()
        except Exception:
            pass  # Fallback if filtering fails

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
