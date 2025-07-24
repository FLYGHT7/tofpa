# tofpa
Take-Off Flight Path Analysis Tool for Aviation (ICAO)

Note: This code is in development and provided as is, it may contain errors and you are solely resposible for using it. Any feedback is welcome.
The implementation is done in a projected coordinate system and currently there is no intention to use a purely geodesic calculation.

Currently it creates the default straight take-off flight path area (TOFPA) considering a 1.2% slope, analysis is done via a QGIS processing model which only handles DTM data.

<img width="1536" height="834" alt="image" src="https://github.com/user-attachments/assets/a289b0b2-466b-4665-b8b8-7bd77e22b3a5" />

## Roadmap
1. Implement survey obstacle analysis.
2. Convert processing model to UI pyqgis icon 'click-to-run'.
