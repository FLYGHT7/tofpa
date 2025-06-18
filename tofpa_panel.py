# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TOFPAPanel
                                 A QGIS plugin
 Takeoff and Final Approach Analysis Tool - Panel
 ***************************************************************************/
"""

import os

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, Qt, QVariant
from qgis.core import (QgsMapLayerProxyModel, QgsProject, QgsVectorLayer, 
                      QgsFeature, QgsGeometry, QgsFeatureRequest, QgsField)
from qgis.PyQt.QtWidgets import QMessageBox


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tofpa_panel_base.ui'))


class TOFPAPanel(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(TOFPAPanel, self).__init__(parent)
        # Set up the user interface from Designer
        self.setupUi(self)
        self.iface = iface
        
        # Set window title
        self.setWindowTitle("TOFPA - Takeoff and Final Approach")
        
        # Connect UI elements
        self.init_ui()
        
    def init_ui(self):
        """Initialize UI elements and connect signals"""
        # Set up layer comboboxes to only show appropriate layers
        self.runwayLayerCombo.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.thresholdLayerCombo.setFilters(QgsMapLayerProxyModel.PointLayer)
        
        # Connect buttons
        self.calculateButton.clicked.connect(self.calculate)
        self.cancelButton.clicked.connect(self.close)
        
        # Set default values
        self.initialWidthSpin.setValue(180.0)
        self.maxWidthSpin.setValue(1800.0)
        
    def calculate(self):
        """Calculate the TOFPA surface"""
        # Show a "processing" message
        self.iface.messageBar().pushMessage("TOFPA", "Calculating takeoff and final approach surfaces...", level=1)
        
        try:
            # Get input values from UI
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            
            # Validate inputs
            if not runway_layer:
                QMessageBox.warning(self, "TOFPA", "Please select a runway layer.")
                return
                
            if not threshold_layer:
                QMessageBox.warning(self, "TOFPA", "Please select a threshold layer.")
                return
            
            # Get parameter values
            initial_width = self.initialWidthSpin.value()
            max_width = self.maxWidthSpin.value()
            clearway_length = self.clearwayLengthSpin.value()
            initial_elevation = self.initialElevationSpin.value()
            end_elevation = self.endElevationSpin.value()
            use_selected = self.useSelectedFeatureCheckBox.isChecked()
            
            # Process features and create TOFPA surface
            result_layer = self.generate_tofpa_surface(
                runway_layer, 
                threshold_layer, 
                initial_width, 
                max_width, 
                clearway_length, 
                initial_elevation,
                end_elevation,
                use_selected
            )
            
            # Add layer to map
            if result_layer:
                QgsProject.instance().addMapLayer(result_layer)
                
                # Export to KMZ if option checked
                if self.exportToKmzCheckBox.isChecked():
                    self.export_to_kmz(result_layer)
                
                # Show success message
                self.iface.messageBar().pushMessage("TOFPA", 
                    "Takeoff and Final Approach surfaces created successfully.", level=3)
            
        except Exception as e:
            # Show error message
            QMessageBox.critical(self, "TOFPA Calculation Error", 
                f"An error occurred during calculation: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def generate_tofpa_surface(self, runway_layer, threshold_layer, initial_width, 
                              max_width, clearway_length, initial_elevation,
                              end_elevation, use_selected):
        """
        Generate the TOFPA surface based on input parameters
        """
        # Get features to process
        if use_selected and runway_layer.selectedFeatureCount() > 0:
            runway_features = runway_layer.selectedFeatures()
        else:
            runway_features = list(runway_layer.getFeatures())
            
        if len(runway_features) == 0:
            QMessageBox.warning(self, "TOFPA", "No runway features available to process.")
            return None
            
        # Create output layer
        result_layer = QgsVectorLayer("Polygon?crs=" + runway_layer.crs().authid(), 
                                     "TOFPA Surface", "memory")
        provider = result_layer.dataProvider()
        
        # Add attributes
        provider.addAttributes([
            QgsField("runway_id", QVariant.Int),
            QgsField("initial_width", QVariant.Double),
            QgsField("max_width", QVariant.Double),
            QgsField("clearway", QVariant.Double),
            QgsField("init_elev", QVariant.Double),
            QgsField("end_elev", QVariant.Double)
        ])
        result_layer.updateFields()
        
        # Process each runway
        for runway in runway_features:
            # TODO: Implement your actual TOFPA surface generation algorithm here
            # This is a simplified example - replace with your actual calculation logic
            
            # Get runway geometry
            runway_geom = runway.geometry()
            
            # Find relevant threshold points (if needed)
            # threshold_points = self.find_threshold_points(threshold_layer, runway_geom)
            
            # Create takeoff and approach surfaces
            # Replace this with your actual surface generation code
            buffer_geom = runway_geom.buffer(max_width, 5)
            
            # Create feature
            new_feature = QgsFeature(result_layer.fields())
            new_feature.setGeometry(buffer_geom)
            new_feature["runway_id"] = runway.id()
            new_feature["initial_width"] = initial_width
            new_feature["max_width"] = max_width
            new_feature["clearway"] = clearway_length
            new_feature["init_elev"] = initial_elevation
            new_feature["end_elev"] = end_elevation
            
            provider.addFeatures([new_feature])
            
        # Update layer extent
        result_layer.updateExtents()
        
        return result_layer
        
    def export_to_kmz(self, layer):
        """Export the specified layer to KMZ format"""
        # TODO: Implement KMZ export logic
        try:
            # Get save file path from user
            from qgis.PyQt.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getSaveFileName(self, 
                "Save KMZ File", "", "KMZ files (*.kmz)")
            
            if file_path:
                if not file_path.endswith('.kmz'):
                    file_path += '.kmz'
                    
                # Use QGIS processing to export to KMZ
                # This is just a placeholder - implement your KMZ export logic
                self.iface.messageBar().pushMessage("TOFPA", 
                    f"KMZ export to {file_path} not yet implemented.", level=1)
        except Exception as e:
            QMessageBox.critical(self, "KMZ Export Error", 
                f"Failed to export to KMZ: {str(e)}")
        
    def closeEvent(self, event):
        """Called when the panel is closed"""
        self.closingPlugin.emit()
        event.accept()
