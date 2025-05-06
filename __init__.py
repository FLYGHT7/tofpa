# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TOFPA
                                 A QGIS plugin
 Takeoff and Final Approach Analysis Tool
                             -------------------
        begin                : 2025-5-5
        copyright            : (C) 2025
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

def classFactory(iface):
    """Load TOFPA class from file tofpa.py
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .tofpa import TOFPA
    return TOFPA(iface)