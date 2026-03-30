"""
FLYGHT7
"""
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.core import QgsMapLayerProxyModel, QgsWkbTypes
from .utils.compat import (  # MIGA-01, MIGA-02
    FIELD_INT, FIELD_DOUBLE,
    WKB_LINE_GEOM, WKB_POINT_GEOM, WKB_POLYGON_GEOM,
    LAYER_FILTER_VECTOR,
)

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tofpa_panel_base.ui'))

logger = logging.getLogger('TOFPA.ui')


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
        self.runwayLayerCombo.setFilters(LAYER_FILTER_VECTOR)
        self.runwayLayerCombo.setExceptedLayerList([])
        
        # Threshold Layer: Only Point geometries  
        self.thresholdLayerCombo.setFilters(LAYER_FILTER_VECTOR)
        self.thresholdLayerCombo.setExceptedLayerList([])
        
        # Obstacles Layer: Point or Polygon geometries
        self.obstaclesLayerCombo.setFilters(LAYER_FILTER_VECTOR)
        self.obstaclesLayerCombo.setExceptedLayerList([])
        
        # Apply geometry-specific filters
        self._apply_geometry_filters()
        
        # Connect to layer changes to refresh filters and obstacle field combo
        try:
            from qgis.core import QgsProject
            QgsProject.instance().layersAdded.connect(self._on_layers_changed)
            QgsProject.instance().layersRemoved.connect(self._on_layers_changed)
        except Exception:
            logger.debug("QGIS layers signal connection failed - running outside QGIS", exc_info=True)
        
        # Connect obstacles layer change to update height field combo
        self.obstaclesLayerCombo.layerChanged.connect(self._update_obstacle_fields)
        
        # Connect checkbox to enable/disable obstacles group
        self.includeObstaclesCheckBox.toggled.connect(self._toggle_obstacles_group)
        
        # Set default values from original script
        self.initialWidthSpin.setValue(180.0)
        self.maxWidthSpin.setValue(1800.0)
        self.clearwayLengthSpin.setValue(0.0)
        self.initialElevationSpin.setValue(0.0)
        self.endElevationSpin.setValue(0.0)
        self.exportToKmzCheckBox.setChecked(False)
        self.exportToAixmCheckBox.setChecked(False)
        self.useSelectedFeatureCheckBox.setChecked(True)
        self.directionCombo.setCurrentIndex(0)  # Default to "Start to End (0)"
        
        # Set default values for obstacles
        self.includeObstaclesCheckBox.setChecked(False)
        self.obstacleBufferSpin.setValue(10.0)
        self.minObstacleHeightSpin.setValue(5.0)
        
        # Set default values for shadow analysis
        self.enableShadowAnalysisCheckBox.setChecked(False)
        self.shadowToleranceSpin.setValue(5.0)
        
        # Connect shadow analysis checkbox to enable/disable shadow tolerance control
        self.enableShadowAnalysisCheckBox.toggled.connect(self._toggle_shadow_controls)
        
        # Initialize obstacles group as disabled
        self._toggle_obstacles_group(False)
        self._toggle_shadow_controls(False)
        
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
        non_obstacle_layers = []  # For obstacles: points or polygons only
        
        for layer in vector_layers:
            try:
                geom_type = layer.geometryType()
                
                # For runway combo: exclude non-line layers
                if geom_type != WKB_LINE_GEOM:
                    non_line_layers.append(layer)
                
                # For threshold combo: exclude non-point layers  
                if geom_type != WKB_POINT_GEOM:
                    non_point_layers.append(layer)
                
                # For obstacles combo: exclude non-point and non-polygon layers
                if geom_type not in [WKB_POINT_GEOM, WKB_POLYGON_GEOM]:
                    non_obstacle_layers.append(layer)
                    
            except Exception:
                logger.debug("Could not determine geometry type for layer, excluding from all combos", exc_info=True)
                # If we can't determine geometry type, exclude from all
                non_line_layers.append(layer)
                non_point_layers.append(layer)
                non_obstacle_layers.append(layer)
        
        # Apply filters
        self.runwayLayerCombo.setExceptedLayerList(non_line_layers)
        self.thresholdLayerCombo.setExceptedLayerList(non_point_layers)
        self.obstaclesLayerCombo.setExceptedLayerList(non_obstacle_layers)

    def _on_layers_changed(self):
        """Refresh geometry filters when layers are added or removed"""
        try:
            self._apply_geometry_filters()
            # Also update obstacle fields if obstacles layer is selected
            self._update_obstacle_fields()
        except Exception:
            logger.debug("Geometry filter application failed", exc_info=True)

    def _update_obstacle_fields(self):
        """Update the obstacle height field combo box based on selected layer"""
        try:
            self.obstacleHeightFieldCombo.clear()
            
            layer = self.obstaclesLayerCombo.currentLayer()
            if layer:
                # Add numeric fields to the combo
                for field in layer.fields():
                    if field.type() in [FIELD_INT, FIELD_DOUBLE]:
                        self.obstacleHeightFieldCombo.addItem(field.name())
                        
                # Set default common field names if available
                field_names = [field.name().lower() for field in layer.fields()]
                for default_name in ['height', 'elevation', 'elev', 'z', 'alt', 'altitude']:
                    if default_name in field_names:
                        index = field_names.index(default_name)
                        self.obstacleHeightFieldCombo.setCurrentIndex(index)
                        break
        except Exception:
            logger.debug("Obstacle height field update failed", exc_info=True)

    def _toggle_obstacles_group(self, enabled):
        """Enable or disable the obstacles group based on checkbox state"""
        try:
            self.obstaclesGroup.setEnabled(enabled)
            if not enabled:
                # Clear obstacles layer selection when disabled
                self.obstaclesLayerCombo.setCurrentIndex(-1)
                # Also disable shadow analysis when obstacles are disabled
                self.enableShadowAnalysisCheckBox.setChecked(False)
            
            # Update shadow controls based on obstacles state
            self._toggle_shadow_controls(self.enableShadowAnalysisCheckBox.isChecked())
        except Exception:
            logger.debug("Toggle obstacles group failed", exc_info=True)

    def _toggle_shadow_controls(self, enabled):
        """Enable or disable shadow analysis controls based on checkbox state"""
        try:
            # Shadow analysis is only available when obstacles analysis is enabled
            obstacles_enabled = self.includeObstaclesCheckBox.isChecked()
            final_enabled = enabled and obstacles_enabled
            
            self.shadowToleranceLabel.setEnabled(final_enabled)
            self.shadowToleranceSpin.setEnabled(final_enabled)
            
            # If obstacles are not enabled, disable shadow analysis checkbox
            if not obstacles_enabled:
                self.enableShadowAnalysisCheckBox.setEnabled(False)
                self.enableShadowAnalysisCheckBox.setChecked(False)
            else:
                self.enableShadowAnalysisCheckBox.setEnabled(True)
        except Exception:
            logger.debug("Toggle shadow controls failed", exc_info=True)

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
            'export_kmz': self.exportToKmzCheckBox.isChecked(),
            'export_aixm': self.exportToAixmCheckBox.isChecked(),
            # New obstacles parameters
            'include_obstacles': self.includeObstaclesCheckBox.isChecked(),
            'obstacles_layer_id': self.obstaclesLayerCombo.currentLayer().id() if self.obstaclesLayerCombo.currentLayer() and self.includeObstaclesCheckBox.isChecked() else None,
            'obstacle_height_field': self.obstacleHeightFieldCombo.currentText() if self.includeObstaclesCheckBox.isChecked() else None,
            'obstacle_buffer': self.obstacleBufferSpin.value(),
            'min_obstacle_height': self.minObstacleHeightSpin.value(),
            # New shadow analysis parameters
            'enable_shadow_analysis': self.enableShadowAnalysisCheckBox.isChecked() and self.includeObstaclesCheckBox.isChecked(),
            'shadow_tolerance': self.shadowToleranceSpin.value()
        }

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
