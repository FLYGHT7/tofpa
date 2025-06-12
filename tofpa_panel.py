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
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.core import QgsMapLayerProxyModel, QgsProject


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tofpa_panel_base.ui'))


class TOFPAPanel(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(TOFPAPanel, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)
        self.iface = iface
        
        # Set window title
        self.setWindowTitle("TOFPA - Takeoff and Final Approach")
        
        # Connect UI elements
        self.init_ui()
        
    def init_ui(self):
        """Initialize UI elements and connect signals"""
        # Example: Set up layer comboboxes to only show vector layers
        # Adjust according to your actual UI elements
        if hasattr(self, 'runwayLayerCombo'):
            self.runwayLayerCombo.setFilters(QgsMapLayerProxyModel.LineLayer)
            
        if hasattr(self, 'thresholdLayerCombo'):
            self.thresholdLayerCombo.setFilters(QgsMapLayerProxyModel.PointLayer)
        
        # Connect buttons
        if hasattr(self, 'calculateButton'):
            self.calculateButton.clicked.connect(self.calculate)
        
        # Default values - adjust according to your UI
        if hasattr(self, 'initialWidthSpin'):
            self.initialWidthSpin.setValue(180.0)
        if hasattr(self, 'maxWidthSpin'):
            self.maxWidthSpin.setValue(1800.0)
        
    def calculate(self):
        """Calculate the TOFPA surface"""
        # Get values from UI elements
        # Implement your calculation logic here
        
        # Example of collecting values from UI:
        # runway_layer = self.runwayLayerCombo.currentLayer()
        # threshold_layer = self.thresholdLayerCombo.currentLayer()
        # initial_width = self.initialWidthSpin.value()
        # max_width = self.maxWidthSpin.value()
        
        # Implement your TOFPA calculation logic here
        pass
        
    def closeEvent(self, event):
        """Called when the panel is closed"""
        self.closingPlugin.emit()
        event.accept()
