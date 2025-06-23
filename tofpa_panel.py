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
    calculateClicked = pyqtSignal()
    closeClicked = pyqtSignal()

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
        self.calculateButton.clicked.connect(self.on_calculate_clicked)
        self.cancelButton.clicked.connect(self.on_close_clicked)
        
        # Set default values
        self.initialWidthSpin.setValue(180.0)
        self.maxWidthSpin.setValue(1800.0)
        
    def on_calculate_clicked(self):
        self.calculateClicked.emit()

    def on_close_clicked(self):
        self.closeClicked.emit()
        self.close()
        
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

        # Get threshold feature
        if use_selected and threshold_layer.selectedFeatureCount() > 0:
            threshold_features = threshold_layer.selectedFeatures()
        else:
            threshold_features = list(threshold_layer.getFeatures())
        if len(threshold_features) == 0:
            QMessageBox.warning(self, "TOFPA", "No threshold features available to process.")
            return None

        # Create output layer
        result_layer = QgsVectorLayer("PolygonZ?crs=" + runway_layer.crs().authid(), 
                                     "TOFPA Surface", "memory")
        provider = result_layer.dataProvider()
        provider.addAttributes([
            QgsField("runway_id", QVariant.Int),
            QgsField("initial_width", QVariant.Double),
            QgsField("max_width", QVariant.Double),
            QgsField("clearway", QVariant.Double),
            QgsField("init_elev", QVariant.Double),
            QgsField("end_elev", QVariant.Double)
        ])
        result_layer.updateFields()

        # Only process the first runway and threshold feature (as in original)
        runway = runway_features[0]
        threshold = threshold_features[0]

        # --- LOGICA ORIGINAL DE GEOMETRIA ---
        rwy_geom = runway.geometry()
        geom = rwy_geom.asPolyline()
        if len(geom) < 2:
            QMessageBox.warning(self, "TOFPA", "Runway geometry is too short.")
            return None

        # Parámetro s fijo en 1 (como en el original)
        s = 1
        s2 = 180 if s == -1 else 0

        start_point = QgsPoint(geom[-1-s])
        end_point = QgsPoint(geom[s])
        angle0 = start_point.azimuth(end_point)
        back_angle0 = angle0 + 180

        azimuth = angle0 + s2
        bazimuth = azimuth + 180

        # Threshold point
        new_geom = QgsPoint(threshold.geometry().asPoint())
        new_geom.addZValue(initial_elevation)

        # Distancia para inicio de superficie
        dd = clearway_length if clearway_length != 0 else 0

        # Calcular puntos de la superficie TOFPA
        pt_01d = new_geom.project(dd, bazimuth)
        pt_01d.setZ(end_elevation)
        pt_01dl = pt_01d.project(initial_width/2, bazimuth+90)
        pt_01dr = pt_01d.project(initial_width/2, bazimuth-90)

        pt_02d = pt_01d.project(((max_width/2-initial_width/2)/0.125), bazimuth)
        pt_02d.setZ(end_elevation+((max_width/2-initial_width/2)/0.125)*0.012)
        pt_02dl = pt_02d.project(max_width/2, bazimuth+90)
        pt_02dr = pt_02d.project(max_width/2, bazimuth-90)

        pt_03d = pt_01d.project(10000, bazimuth)
        pt_03d.setZ(end_elevation+10000*0.012)
        pt_03dl = pt_03d.project(max_width/2, bazimuth+90)
        pt_03dr = pt_03d.project(max_width/2, bazimuth-90)

        # Crear polígono con los puntos correctos
        surface_area = [pt_03dr, pt_03dl, pt_02dl, pt_01dl, pt_01dr, pt_02dr]
        polygon = QgsPolygon(QgsLineString(surface_area))
        feature = QgsFeature(result_layer.fields())
        feature.setGeometry(polygon)
        feature["runway_id"] = runway.id()
        feature["initial_width"] = initial_width
        feature["max_width"] = max_width
        feature["clearway"] = clearway_length
        feature["init_elev"] = initial_elevation
        feature["end_elev"] = end_elevation
        provider.addFeatures([feature])

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

    def get_parameters(self):
        """Return all parameters from the panel widgets in a dict (compatible with plugin logic)."""
        return {
            'width_tofpa': self.initialWidthSpin.value(),
            'max_width_tofpa': self.maxWidthSpin.value(),
            'cwy_length': self.clearwayLengthSpin.value(),
            'z0': self.initialElevationSpin.value(),
            'ze': self.endElevationSpin.value(),
            's': 1,  # Puedes cambiar esto si agregas control de dirección
            'runway_layer_id': self.runwayLayerCombo.currentLayer().id() if self.runwayLayerCombo.currentLayer() else None,
            'threshold_layer_id': self.thresholdLayerCombo.currentLayer().id() if self.thresholdLayerCombo.currentLayer() else None,
            'use_selected_feature': self.useSelectedFeatureCheckBox.isChecked(),
            'export_kmz': self.exportToKmzCheckBox.isChecked()
        }
