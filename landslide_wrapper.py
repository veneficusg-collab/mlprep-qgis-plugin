#myplugin_dialog_wrapper
import os
import sys
import subprocess
import json
import platform
import shutil
import tempfile 

from qgis.core import (
    QgsVectorLayer, 
    QgsRasterLayer, 
    QgsProject,
    QgsMapSettings,
    QgsMapRendererParallelJob
)
from qgis.PyQt import QtWidgets, QtGui, QtCore
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QPixmap

# Import the UI class
from .MainWindow import Ui_MainWindow

class PluginDialog(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(PluginDialog, self).__init__(parent)
        self.setupUi(self)
        
        # --- CONFIGURATION ---
        self.venv_python = self.get_venv_python_path()
        self.current_result_path = None 
        
        # --- DEFINE ADMIN PATHS & COLUMNS ---
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        roi_dir = os.path.join(plugin_dir, "roi_data")
        
        self.admin_config = {
            "Region": {
                "path": os.path.join(roi_dir, "phl_admbnda_adm1_psa_namria_20231106.shp"),
                "col": "ADM1_EN"
            },
            "Province": {
                "path": os.path.join(roi_dir, "phl_admbnda_adm2_psa_namria_20231106.shp"),
                "col": "ADM2_EN"
            },
            "Municipality": {
                "path": os.path.join(roi_dir, "phl_admbnda_adm3_psa_namria_20231106.shp"),
                "col": "ADM3_EN"
            },
            "Barangay": {
                "path": os.path.join(roi_dir, "phl_admbnda_adm4_psa_namria_20231106.shp"),
                "col": "ADM4_EN"
            }
        }

        # Index for search bar
        self.location_index = {} 

        # =========================================================
        # 1. MODIFY EXISTING UI LABELS
        # =========================================================
        self.Label_ROI.setText("LULC Shapefile:")
        self.GroupBox_ROI.setTitle("LULC Preview") 
        
        # =========================================================
        # 2. REORDER FILE INPUTS & FIX SPACING (DEM First, LULC Second)
        # =========================================================
        
        # --- FIX: ADD SPACING TO THE GRID LAYOUT ---
        # This fixes the "squashed" look in your screenshot
        self.gridLayout_2.setVerticalSpacing(15)  # 15px gap between rows
        self.gridLayout_2.setContentsMargins(10, 15, 10, 15) # Padding around the edges

        # Re-add widgets in the correct order
        self.gridLayout_2.addWidget(self.Label_DEM, 0, 0, 1, 1)
        self.gridLayout_2.addWidget(self.Widget_DEM, 0, 1, 1, 1)
        self.gridLayout_2.addWidget(self.Label_ROI, 1, 0, 1, 1)
        self.gridLayout_2.addWidget(self.Widget_ROI, 1, 1, 1, 1)
        self.gridLayout_2.addWidget(self.Label_Sentinel_2_Pre_Event, 2, 0, 1, 1)
        self.gridLayout_2.addWidget(self.Widget_Sentinel_2_Pre_Event, 2, 1, 1, 1)
        self.gridLayout_2.addWidget(self.Label_Sentinel_2_Post_Event, 3, 0, 1, 1)
        self.gridLayout_2.addWidget(self.Widget_Sentinel_2_Post_Event, 3, 1, 1, 1)

        # =========================================================
        # 3. NEW UI: ROI Selection
        # =========================================================
        
        self.GroupBox_ROI_Selection = QtWidgets.QGroupBox(self.Widget_Inputs)
        self.GroupBox_ROI_Selection.setTitle("Region of Interest")
        self.GroupBox_ROI_Selection.setObjectName("GroupBox_ROI_Selection")
        
        self.layout_roi_select = QtWidgets.QGridLayout(self.GroupBox_ROI_Selection)
        self.layout_roi_select.setContentsMargins(10, 15, 10, 15) # Match padding
        self.layout_roi_select.setVerticalSpacing(15)             # Match spacing
        self.layout_roi_select.setHorizontalSpacing(10)
        self.layout_roi_select.setColumnStretch(1, 1)

        # Styles
        label_style = "color: black; font-weight: normal;"
        combo_style = """
            QComboBox {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 4px 10px;
                background: #D5D5D5;
                color: black;
                font-size: 11px;
                min-height: 25px; 
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left-width: 0px;
            }
        """
        search_style = """
            QLineEdit {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 4px 10px;
                background: #ffffff;
                color: black;
                font-size: 11px;
                min-height: 25px; 
            }
        """

        # --- ROW 0: SEARCH BAR ---
        self.Label_Search = QtWidgets.QLabel("Search Location:", self.GroupBox_ROI_Selection)
        self.Label_Search.setStyleSheet(label_style)
        
        self.LineEdit_Search = QtWidgets.QLineEdit(self.GroupBox_ROI_Selection)
        self.LineEdit_Search.setPlaceholderText("Type to search (e.g. Alamada)...")
        self.LineEdit_Search.setStyleSheet(search_style)
        
        # --- ROW 1: LEVEL ---
        self.Label_Level = QtWidgets.QLabel("Select Level:", self.GroupBox_ROI_Selection)
        self.Label_Level.setStyleSheet(label_style)
        self.ComboBox_ROI_Level = QtWidgets.QComboBox(self.GroupBox_ROI_Selection)
        self.ComboBox_ROI_Level.addItems(["Region", "Province", "Municipality", "Barangay"])
        self.ComboBox_ROI_Level.setCurrentText("Municipality") 
        self.ComboBox_ROI_Level.setStyleSheet(combo_style)
        
        # --- ROW 2: NAME ---
        self.Label_Name = QtWidgets.QLabel("Select Name:", self.GroupBox_ROI_Selection)
        self.Label_Name.setStyleSheet(label_style)
        self.ComboBox_ROI_Name = QtWidgets.QComboBox(self.GroupBox_ROI_Selection)
        self.ComboBox_ROI_Name.setStyleSheet(combo_style)
        self.ComboBox_ROI_Name.setEditable(False) # Strict Dropdown

        # Add to Layout
        self.layout_roi_select.addWidget(self.Label_Search, 0, 0)
        self.layout_roi_select.addWidget(self.LineEdit_Search, 0, 1)
        
        self.layout_roi_select.addWidget(self.Label_Level, 1, 0)
        self.layout_roi_select.addWidget(self.ComboBox_ROI_Level, 1, 1)
        
        self.layout_roi_select.addWidget(self.Label_Name, 2, 0)
        self.layout_roi_select.addWidget(self.ComboBox_ROI_Name, 2, 1)
        
        self.verticalLayout_4.insertWidget(2, self.GroupBox_ROI_Selection)

        # =========================================================

        # Connect buttons
        self.PushButton_ROI.clicked.connect(self.select_lulc_file) 
        self.PushButton_DEM.clicked.connect(self.select_dem_file)
        self.PushButton_Sentinel_2_Pre_Event.clicked.connect(self.select_pre_event_file)
        self.PushButton_Sentinel_2_Post_Event.clicked.connect(self.select_post_event_file)
        self.Button_Detect.clicked.connect(self.run_detection)
        self.Button_Save.clicked.connect(self.save_result_to_disk)

        # Dropdown Logic
        self.ComboBox_ROI_Level.currentTextChanged.connect(self.populate_location_names)
        self.populate_location_names()
        
        # Search Bar Logic
        QtCore.QTimer.singleShot(100, self.build_search_index)

    def get_venv_python_path(self):
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        venv_name = "ls_detect_env"
        if platform.system() == "Windows":
            return os.path.join(plugin_dir, venv_name, "Scripts", "python.exe")
        else:
            return os.path.join(plugin_dir, venv_name, "bin", "python")

    def build_search_index(self):
        """Reads all shapefiles to build a master search index."""
        self.location_index = {}
        all_names = []
        
        for level, config in self.admin_config.items():
            path = config["path"]
            col = config["col"]
            
            if os.path.exists(path):
                try:
                    layer = QgsVectorLayer(path, "temp", "ogr")
                    if layer.isValid():
                        idx = layer.fields().indexOf(col)
                        if idx != -1:
                            values = layer.uniqueValues(idx)
                            for val in values:
                                if val:
                                    name = str(val)
                                    if name not in self.location_index:
                                        self.location_index[name] = level
                                        all_names.append(name)
                except:
                    pass
        
        completer = QtWidgets.QCompleter(all_names, self.LineEdit_Search)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.LineEdit_Search.setCompleter(completer)
        
        completer.activated.connect(self.on_search_selected)

    def on_search_selected(self, text):
        level = self.location_index.get(text)
        if level:
            self.ComboBox_ROI_Level.setCurrentText(level)
            index = self.ComboBox_ROI_Name.findText(text)
            if index != -1:
                self.ComboBox_ROI_Name.setCurrentIndex(index)
            else:
                self.ComboBox_ROI_Name.setCurrentText(text)

    def populate_location_names(self):
        self.ComboBox_ROI_Name.clear()
        selected_level = self.ComboBox_ROI_Level.currentText()
        
        config = self.admin_config.get(selected_level)
        if not config: return

        shp_path = config["path"]
        col_name = config["col"]

        if not os.path.exists(shp_path):
            self.ComboBox_ROI_Name.addItem(f"Error: {selected_level} file missing")
            return

        layer = QgsVectorLayer(shp_path, "roi_temp", "ogr")
        if not layer.isValid():
            self.ComboBox_ROI_Name.addItem("Error: Invalid Shapefile")
            return

        fields = [f.name() for f in layer.fields()]
        if col_name not in fields:
            self.ComboBox_ROI_Name.addItem(f"Field '{col_name}' not found")
            return

        try:
            idx = layer.fields().indexOf(col_name)
            unique_values = layer.uniqueValues(idx)
            sorted_names = sorted([str(v) for v in unique_values if v])
            self.ComboBox_ROI_Name.addItems(sorted_names)
        except Exception as e:
            self.ComboBox_ROI_Name.addItem(f"Error reading data")
            print(e)

    # --- FILE SELECTION ---
    def select_lulc_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select LULC Shapefile", "", "Shapefiles (*.shp)")
        if filename: 
            self.PTE_ROI.setPlainText(filename)
            self.preview_layer(filename, self.GraphicsView_ROI, is_raster=False)

    def select_dem_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select DEM", "", "Tiff (*.tif)")
        if filename: 
            self.PTE_DEM.setPlainText(filename)
            self.preview_layer(filename, self.GraphicsView_DEM_2, is_raster=True)

    def select_pre_event_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Pre-Event", "", "Tiff (*.tif)")
        if filename: 
            self.PTE_Sentinel_2_Pre_Event.setPlainText(filename)
            self.preview_layer(filename, self.GraphicsView_Pre_Event, is_raster=True)

    def select_post_event_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Post-Event", "", "Tiff (*.tif)")
        if filename: 
            self.PTE_Sentinel_2_Post_Event.setPlainText(filename)
            self.preview_layer(filename, self.GraphicsView_Post_Event, is_raster=True)

    def preview_layer(self, file_path, graphics_view, is_raster=False):
        if is_raster:
            layer = QgsRasterLayer(file_path, "preview")
        else:
            layer = QgsVectorLayer(file_path, "preview", "ogr")
        
        if not layer.isValid(): return

        settings = QgsMapSettings()
        settings.setLayers([layer])
        settings.setBackgroundColor(QColor(255, 255, 255, 0))
        settings.setExtent(layer.extent())
        
        view_size = graphics_view.size()
        if view_size.width() <= 0: view_size = QtCore.QSize(200, 200)
        settings.setOutputSize(view_size)

        render_job = QgsMapRendererParallelJob(settings)
        render_job.start()
        render_job.waitForFinished()
        
        image = render_job.renderedImage()
        scene = QtWidgets.QGraphicsScene()
        item = scene.addPixmap(QPixmap.fromImage(image))
        graphics_view.setScene(scene)
        graphics_view.fitInView(item, Qt.KeepAspectRatio)

    # --- DETECTION LOGIC ---
    def run_detection(self):
        lulc = self.PTE_ROI.toPlainText() 
        dem = self.PTE_DEM.toPlainText()
        before = self.PTE_Sentinel_2_Pre_Event.toPlainText()
        after = self.PTE_Sentinel_2_Post_Event.toPlainText()
        
        selected_level = self.ComboBox_ROI_Level.currentText()
        selected_name = self.ComboBox_ROI_Name.currentText()
        
        config = self.admin_config.get(selected_level)
        if not config: return
        roi_file_path = config["path"]
        filter_col = config["col"]

        if not all([lulc, dem, before, after]):
            QtWidgets.QMessageBox.warning(self, "Missing Inputs", "Please select LULC, DEM, Before, and After files.")
            return

        temp_dir = tempfile.gettempdir()
        temp_output_path = os.path.join(temp_dir, "temp_landslide_result.tif")

        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        worker_script = os.path.join(plugin_dir, "landslide_worker.py")

        if not os.path.exists(self.venv_python):
             QtWidgets.QMessageBox.critical(self, "Config Error", f"Virtual Environment Python not found at:\n{self.venv_python}")
             return

        command = [
            self.venv_python, worker_script,
            "--dem", dem,
            "--before", before,
            "--after", after,
            "--lulc", lulc,
            "--output", temp_output_path,
            "--roi_path", roi_file_path,
            "--filter_col", filter_col,
            "--filter_val", selected_name 
        ]

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            process = subprocess.run(command, capture_output=True, text=True)
            
            if process.returncode == 0:
                lines = process.stdout.strip().split('\n')
                last_line = lines[-1] if lines else ""
                try:
                    result_json = json.loads(last_line)
                    if result_json.get("status") == "success":
                        QtWidgets.QMessageBox.information(self, "Success", "Detection Complete! You can now click SAVE.")
                        
                        mask_path = result_json.get("output_mask")
                        ndvi_path = result_json.get("output_ndvi")
                        self.current_result_path = mask_path 

                        if ndvi_path and os.path.exists(ndvi_path):
                             self.preview_layer(ndvi_path, self.GraphicsView_NDVI, is_raster=True)
                        if mask_path and os.path.exists(mask_path):
                             self.preview_layer(mask_path, self.GraphicsView_Result, is_raster=True)
                             rlayer = QgsRasterLayer(mask_path, "Landslide Result (Preview)")
                             if rlayer.isValid():
                                QgsProject.instance().addMapLayer(rlayer)
                    else:
                        QtWidgets.QMessageBox.critical(self, "Worker Error", f"Script failed: {result_json.get('message')}")
                except json.JSONDecodeError:
                     print("STDOUT:", process.stdout)
                     QtWidgets.QMessageBox.warning(self, "Error", "Could not parse script output.")
            else:
                QtWidgets.QMessageBox.critical(self, "Error", f"Process failed.\n{process.stderr}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "System Error", str(e))
        finally:
             QtWidgets.QApplication.restoreOverrideCursor()

    # --- SAVE BUTTON LOGIC ---
    def save_result_to_disk(self):
        if not self.current_result_path or not os.path.exists(self.current_result_path):
            QtWidgets.QMessageBox.warning(self, "Save", "No detection result exists yet.\nPlease run 'DETECT' first.")
            return

        roi_name = self.ComboBox_ROI_Name.currentText()
        if not roi_name:
            roi_name = "Landslide_Result"
        
        safe_name = roi_name.replace(" ", "_")
        default_filename = f"{safe_name}_Landslide.tif"

        documents_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
        default_path = os.path.join(documents_dir, default_filename)

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Landslide Mask", default_path, "Tiff Files (*.tif)"
        )

        if filename:
            try:
                shutil.copy2(self.current_result_path, filename)
                QtWidgets.QMessageBox.information(self, "Saved", f"File successfully saved to:\n{filename}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Save Error", f"Could not save file:\n{str(e)}")