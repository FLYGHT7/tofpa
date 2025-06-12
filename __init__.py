# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TOFPA
                                 A QGIS plugin
 Takeoff and Final Approach Analysis Tool
 ***************************************************************************/
"""

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load TOFPA class from file TOFPA.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .tofpa import tofpa  # Changed from TOFPA to tofpa based on the error message
    return tofpa(iface)