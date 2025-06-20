# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TOFPA
                                 A QGIS panel
 Takeoff and Final Approach Analysis Tool
                              -------------------
        begin                : 2024-04-14
        copyright            : (C) 2024
        email                : your.email@example.com
 ***************************************************************************/

 /***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QCoreApplication, QVariant, Qt
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QFileDialog, QAction
from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
                      QgsPoint, QgsField, QgsPolygon, QgsLineString, Qgis, 
                      QgsFillSymbol, QgsVectorFileWriter, QgsCoordinateTransform,
                      QgsCoordinateReferenceSystem)

import os.path
from math import *

# Import the dialog
from .tofpa_dialog import TOFPADialog
from .tofpa_panel import TOFPAPanel  # Debes tener un archivo tofpa_panel.py que define el QDockWidget

class TOFPA:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr(u'&TOFPA')
        self.first_start = True
        self.panel = None

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('TOFPA', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'TOFPA'),
            callback=self.show_panel,
            parent=self.iface.mainWindow())
        self.first_start = True

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&TOFPA'), action)
            self.iface.removeToolBarIcon(action)
        # Remove the panel if it's open
        if self.panel:
            self.iface.removeDockWidget(self.panel)
            self.panel = None

    def show_panel(self):
        if not self.panel:
            self.panel = TOFPAPanel(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel)
            self.panel.calculateClicked.connect(self.on_calculate)
            self.panel.closeClicked.connect(self.on_close_panel)
        self.panel.show()
        self.panel.raise_()

    def on_close_panel(self):
        if self.panel:
            self.panel.hide()

    def on_calculate(self):
        params = self.panel.get_parameters()
        success = self.create_tofpa_surface(
            params['width_tofpa'],
            params['max_width_tofpa'],
            params['cwy_length'],
            params['z0'],
            params['ze'],
            params['s'],
            params['runway_layer_id'],
            params['threshold_layer_id'],
            params['use_selected_feature'],
            params['export_kmz']
        )
        if success:
            self.iface.messageBar().pushMessage("TOFPA:", "TakeOff Climb Surface Calculation Finished", level=Qgis.Success)

    def get_single_feature(self, layer, use_selected_feature, feature_type="feature"):
        """
        Get a single feature from the layer following the original selection logic.
        Returns the feature if successful, None if error (with error message displayed).
        """
        if use_selected_feature:
            selected_features = layer.selectedFeatures()
            if len(selected_features) == 1:
                return selected_features[0]
            elif len(selected_features) > 1:
                self.iface.messageBar().pushMessage(
                    "Error", 
                    f"Please select only one {feature_type} in layer '{layer.name()}'.", 
                    level=Qgis.Critical
                )
                return None
            else:
                self.iface.messageBar().pushMessage(
                    "Error", 
                    f"No {feature_type} selected in layer '{layer.name()}'. Please select one.", 
                    level=Qgis.Critical
                )
                return None
        else:
            all_features = list(layer.getFeatures())
            if len(all_features) == 1:
                return all_features[0]
            elif len(all_features) > 1:
                self.iface.messageBar().pushMessage(
                    "Error", 
                    f"Layer '{layer.name()}' has more than one {feature_type}. Please select one and check 'Use selected features only'.", 
                    level=Qgis.Critical
                )
                return None
            elif len(all_features) == 0:
                self.iface.messageBar().pushMessage(
                    "Error", 
                    f"No {feature_type}s found in layer '{layer.name()}'.", 
                    level=Qgis.Critical
                )
                return None
        return None

    def create_tofpa_surface(self, width_tofpa, max_width_tofpa, cwy_length, z0, ze, s, 
                            runway_layer_id, threshold_layer_id, use_selected_feature, export_kmz):
        """
        Create the TOFPA surface based on the given parameters.

        :param width_tofpa: Width of the TOFPA surface at the runway threshold
        :param max_width_tofpa: Maximum width of the TOFPA surface
        :param cwy_length: Length of the clearway
        :param z0: Initial height above the runway threshold
        :param ze: Height at the end of the TOFPA surface
        :param s: Slope of the TOFPA surface
        :param runway_layer_id: ID of the runway layer
        :param threshold_layer_id: ID of the threshold layer
        :param use_selected_feature: Flag indicating whether to use the selected feature
        :param export_kmz: Flag indicating whether to export the result as KMZ
        :return: True if the surface was created successfully, False otherwise
        :rtype: bool
        """
        # Get runway layer by ID
        runway_layer = QgsProject.instance().mapLayer(runway_layer_id)
        if not runway_layer:
            self.iface.messageBar().pushMessage("Error", "Selected runway layer not found!", level=Qgis.Critical)
            return False

        # Use robust feature selection logic
        runway_feature = self.get_single_feature(runway_layer, use_selected_feature, "runway feature")
        if not runway_feature:
            return False

        # Get runway geometry
        rwy_geom = runway_feature.geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (z0-ze)/rwy_length if rwy_length > 0 else 0
        print(f"Runway length: {rwy_length}")

        # Get the azimuth of the line
        geom = runway_feature.geometry().asPolyline()
        if len(geom) <= abs(s):
            self.iface.messageBar().pushMessage("Error", "Runway geometry is too short for the selected direction!", level=Qgis.Critical)
            return False

        start_point = QgsPoint(geom[-1-s])
        end_point = QgsPoint(geom[s])
        angle0 = start_point.azimuth(end_point)
        back_angle0 = angle0+180

        # Define s2 before using it
        s2 = 180 if s == -1 else 0

        # Initial true azimuth data
        azimuth = angle0+s2
        bazimuth = azimuth+180

        # Get the threshold point from selected layer
        threshold_layer = QgsProject.instance().mapLayer(threshold_layer_id)
        if not threshold_layer:
            self.iface.messageBar().pushMessage("Error", "Selected threshold layer not found!", level=Qgis.Critical)
            return False

        threshold_feature = self.get_single_feature(threshold_layer, use_selected_feature, "threshold feature")
        if not threshold_feature:
            return False

        # Get threshold point
        new_geom = QgsPoint(threshold_feature.geometry().asPoint())
        new_geom.addZValue(z0)

        # Prepare the output layer
        output_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "TOFPA_Surface", "memory")
        output_provider = output_layer.dataProvider()

        # Add fields to the output layer
        output_provider.addAttributes([
            QgsField("id", QVariant.Int),
            QgsField("width", QVariant.Double),
            QgsField("length", QVariant.Double),
            QgsField("slope", QVariant.Double),
            QgsField("z0", QVariant.Double),
            QgsField("ze", QVariant.Double)
        ])
        output_layer.updateFields()

        # Create the TOFPA surface geometry
        tofpa_geometries = []

        # Calculate the TOFPA surface geometry
        tofpa_geometry = self.calculate_tofpa_geometry(rwy_geom, width_tofpa, max_width_tofpa, cwy_length, z0, ze, s, new_geom, angle0, back_angle0)

        if tofpa_geometry is not None:
            tofpa_geometries.append(tofpa_geometry)

        # Add the TOFPA surface features to the output layer
        for i, geom in enumerate(tofpa_geometries):
            feature = QgsFeature()
            feature.setGeometry(geom)
            feature.setAttributes([i + 1, width_tofpa, cwy_length, s, z0, ze])
            output_provider.addFeature(feature)

        # Update the output layer extent
        output_layer.updateExtents()

        # Add the output layer to the project
        QgsProject.instance().addMapLayer(output_layer)

        # Export to KMZ if needed
        if export_kmz:
            kmz_file, _ = QFileDialog.getSaveFileName(None, "Export to KMZ", "", "KMZ Files (*.kmz);;All Files (*)")
            if kmz_file:
                self.export_to_kmz(output_layer, kmz_file)

        return True

    def calculate_tofpa_geometry(self, runway_geometry, width_tofpa, max_width_tofpa, cwy_length, z0, ze, s, threshold_point, angle0, back_angle0):
        """
        Calculate the geometry of the TOFPA surface based on the runway geometry and parameters.

        :param runway_geometry: The geometry of the runway
        :param width_tofpa: Width of the TOFPA surface at the runway threshold
        :param max_width_tofpa: Maximum width of the TOFPA surface
        :param cwy_length: Length of the clearway
        :param z0: Initial height above the runway threshold
        :param ze: Height at the end of the TOFPA surface
        :param s: Slope of the TOFPA surface
        :param threshold_point: The threshold point geometry
        :param angle0: The initial angle for the TOFPA surface
        :param back_angle0: The back angle for the TOFPA surface
        :return: The geometry of the TOFPA surface, or None if the calculation fails
        :rtype: QgsGeometry
        """
        # Try to get points as polyline (LineString) or asMultiPolyline (MultiLineString)
        if runway_geometry.isMultipart():
            lines = runway_geometry.asMultiPolyline()
            if not lines or len(lines[0]) < 2:
                return None
            points = lines[0]
        else:
            points = runway_geometry.asPolyline()
            if len(points) < 2:
                return None

        # Calculate the slope length
        slope_length = cwy_length / cos(atan(s))

        # Calculate the end points of the slope
        p1 = points[0]
        p2 = points[1]

        # Calculate the width at the end of the slope
        width_end = width_tofpa + slope_length * s

        # Create the polygon points
        poly_points = [
            p1,
            QgsPoint(p1.x() + width_tofpa, p1.y()),
            QgsPoint(p2.x() + width_end, p2.y()),
            p2,
            QgsPoint(p2.x() - width_end, p2.y()),
            QgsPoint(p1.x() - width_tofpa, p1.y()),
            p1
        ]

        # Create the polygon geometry
        polygon = QgsPolygon(QgsLineString(poly_points))

        return QgsGeometry(polygon)

    def export_to_kmz(self, layer, kmz_file):
        """
        Export the given layer to a KMZ file.

        :param layer: The layer to export
        :param kmz_file: The output KMZ file path
        """
        # Create a temporary KML file
        kml_file = kmz_file[:-4] + ".kml"
        QgsVectorFileWriter.writeAsVectorFormat(layer, kml_file, "UTF-8", driverName="KML")

        # Create the KMZ file by compressing the KML file
        import zipfile
        with zipfile.ZipFile(kmz_file, 'w') as kmz:
            kmz.write(kml_file, os.path.basename(kml_file))

        # Remove the temporary KML file
        os.remove(kml_file)