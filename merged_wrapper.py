import os
import sys
import subprocess
import json
import platform
import shutil
import tempfile
import csv
import numpy as np

# QGIS / PyQt Imports
from qgis.PyQt import QtWidgets, QtCore, QtGui
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QVariant, QSize, QEvent
from qgis.PyQt.QtWidgets import (
    QMainWindow, QTabWidget, QStackedWidget, QMessageBox, 
    QProgressDialog, QFileDialog, QGraphicsScene, QTableWidgetItem
)
from qgis.PyQt.QtGui import QColor, QPixmap, QPen, QBrush, QImage

from qgis.core import (
    QgsVectorLayer, QgsRasterLayer, QgsProject, QgsMapSettings,
    QgsMapRendererParallelJob, QgsMapRendererSequentialJob, QgsCoordinateReferenceSystem,
    QgsFeatureRequest, QgsGeometry, QgsPointXY, QgsField,
    QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol, QgsSingleSymbolRenderer
)

# Import BOTH UI files
from .landslide_mainwindow import Ui_MainWindow as Ui_Landslide
from .eil_mainwindow import Ui_MainWindow as Ui_EIL

# ==============================================================================
# EIL WORKER THREAD
# ==============================================================================
class PredictionWorker(QThread):
    finished = pyqtSignal(dict, dict)
    error = pyqtSignal(str)

    def __init__(self, cmd, env, output_csv, output_gpkg):
        super().__init__()
        self.cmd = cmd
        self.env = env
        self.output_csv = output_csv
        self.output_gpkg = output_gpkg

    def run(self):
        try:
            process = subprocess.run(self.cmd, capture_output=True, text=True, env=self.env)
            if process.returncode != 0:
                self.error.emit(f"Process Failed:\n{process.stderr}")
                return
            if not os.path.exists(self.output_csv):
                self.error.emit("Worker finished but output CSV not found.")
                return

            csv_data = []
            with open(self.output_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    csv_data.append(row)
            
            self.finished.emit({"rows": csv_data}, {})
        except Exception as e:
            self.error.emit(str(e))

# ==============================================================================
# AUTO-SETUP THREAD (First-time installation)
# ==============================================================================
class SetupWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, base_dir, ls_python, eil_python):
        super().__init__()
        self.base_dir = base_dir
        self.ls_python = ls_python
        self.eil_python = eil_python

    def run(self):
        # We must use QGIS's internal Python executable to spawn the venvs
        if sys.platform == 'win32':
            base_python = os.path.join(sys.prefix, 'python.exe')
        else:
            base_python = sys.executable

        try:
            # 1. Setup Landslide Environment
            ls_venv_dir = os.path.join(self.base_dir, "ls_detect_env")
            if not os.path.exists(ls_venv_dir):
                self.progress.emit("Creating Landslide Environment...")
                subprocess.run([base_python, "-m", "venv", ls_venv_dir], check=True)
                
                self.progress.emit("Installing Landslide Dependencies (This may take a few minutes)...")
                req_ls = os.path.join(self.base_dir, "requirements_ls.txt")
                subprocess.run([self.ls_python, "-m", "pip", "install", "-r", req_ls], check=True)

            # 2. Setup EIL Environment
            eil_venv_dir = os.path.join(self.base_dir, "venv")
            if not os.path.exists(eil_venv_dir):
                self.progress.emit("Creating EIL Environment...")
                subprocess.run([base_python, "-m", "venv", eil_venv_dir], check=True)
                
                self.progress.emit("Installing EIL Dependencies (This may take a few minutes)...")
                req_eil = os.path.join(self.base_dir, "requirements_eil.txt")
                subprocess.run([self.eil_python, "-m", "pip", "install", "-r", req_eil], check=True)

            self.finished.emit(True, "Setup Complete!")
        except Exception as e:
            self.finished.emit(False, str(e))

# ==============================================================================
# MAIN UNIFIED DIALOG
# ==============================================================================
class UnifiedPluginDialog(QMainWindow):
    def __init__(self, parent=None):
        super(UnifiedPluginDialog, self).__init__(parent)
        self.setWindowTitle("MLPREP Detection Suite")
        
        # 1. SETUP MAIN UNIFIED LAYOUT
        self.centralwidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.centralwidget)
        self.main_layout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 2. STACKED WIDGET FOR MAPS (LEFT COLUMN)
        self.map_stack = QStackedWidget(self.centralwidget)
        self.main_layout.addWidget(self.map_stack, stretch=3)

        # 3. TAB WIDGET FOR INPUTS (RIGHT COLUMN)
        self.input_tabs = QTabWidget(self.centralwidget)
        self.main_layout.addWidget(self.input_tabs, stretch=1)

        # 4. INSTANTIATE AND EXTRACT FROM YOUR UI FILES
        self.ui_ls = Ui_Landslide()
        self.ui_eil = Ui_EIL()

        self.dummy_ls = QMainWindow()
        self.ui_ls.setupUi(self.dummy_ls)
        
        self.dummy_eil = QMainWindow()
        self.ui_eil.setupUi(self.dummy_eil)

        # 5. STITCH MAPS INTO LEFT STACK
        self.map_stack.addWidget(self.ui_ls.Widget_Map_Area)  # Index 0: Landslide Maps
        self.map_stack.addWidget(self.ui_eil.Widget_Map_Area) # Index 1: EIL Maps

        # 6. STITCH INPUTS INTO RIGHT TABS
        self.input_tabs.addTab(self.ui_ls.scrollArea, "Landslide Detection") # Index 0
        self.input_tabs.addTab(self.ui_eil.scrollArea, "EIL Detection")      # Index 1

        # 7. CONNECT TABS TO MAPS
        self.input_tabs.currentChanged.connect(self.map_stack.setCurrentIndex)

        # =========================================================
        # RESTORE ORIGINAL MASTER CSS
        # =========================================================
        self.apply_master_stylesheet()

        # =========================================================
        # INITIALIZE PLUGIN STATES & VARIABLES
        # =========================================================
        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Landslide specific variables
        self.ls_venv_python = self.get_venv_python_path("ls_detect_env")
        self.current_result_path_ls = None
        self.location_index = {}
        roi_dir = os.path.join(self._base_dir, "roi_data")
        self.admin_config = {
            "Region":       {"path": os.path.join(roi_dir, "phl_admbnda_adm1_psa_namria_20231106.shp"), "col": "ADM1_EN"},
            "Province":     {"path": os.path.join(roi_dir, "phl_admbnda_adm2_psa_namria_20231106.shp"), "col": "ADM2_EN"},
            "Municipality": {"path": os.path.join(roi_dir, "phl_admbnda_adm3_psa_namria_20231106.shp"), "col": "ADM3_EN"},
            "Barangay":     {"path": os.path.join(roi_dir, "phl_admbnda_adm4_psa_namria_20231106.shp"), "col": "ADM4_EN"}
        }

        # EIL specific variables
        self.eil_venv_python = self.get_venv_python_path("venv")
        self.MODEL_PATH = os.path.join(self._base_dir, "model", "my_model.keras")
        self.map_view_data = {}
        self.debug_marker = None
        self.worker = None

        # =========================================================
        # CONNECT SIGNALS & SLOTS
        # =========================================================
        self.build_dynamic_landslide_ui()
        self.connect_landslide_signals()
        self.connect_eil_signals()

        # RUN THE FIRST-TIME SETUP CHECK
        QtCore.QTimer.singleShot(500, self.check_and_setup_environments)

    # ------------------------------------------------------------------
    # FIRST-TIME AUTO SETUP LOGIC
    # ------------------------------------------------------------------
    def check_and_setup_environments(self):
        ls_venv_dir = os.path.join(self._base_dir, "ls_detect_env")
        eil_venv_dir = os.path.join(self._base_dir, "venv")
        
        # If both exist, we do nothing and proceed as normal
        if os.path.exists(ls_venv_dir) and os.path.exists(eil_venv_dir):
            return

        # Prompt the user
        reply = QMessageBox.question(
            self, 
            "First Time Setup Required", 
            "The MLPREP Detection Suite requires Python dependencies to run (TensorFlow, GeoPandas, etc.).\n\nWould you like to install them now? (This may take 3-5 minutes depending on internet speed).",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.setup_dialog = QProgressDialog("Initializing Setup...", None, 0, 0, self)
            self.setup_dialog.setWindowTitle("Installing Dependencies")
            self.setup_dialog.setWindowModality(Qt.WindowModal)
            self.setup_dialog.setCancelButton(None)
            self.setup_dialog.show()

            # Start the Setup Worker
            self.setup_worker = SetupWorker(self._base_dir, self.ls_venv_python, self.eil_venv_python)
            self.setup_worker.progress.connect(self.setup_dialog.setLabelText)
            self.setup_worker.finished.connect(self.on_setup_finished)
            self.setup_worker.start()
        else:
            QMessageBox.warning(self, "Setup Skipped", "The plugin will not function correctly until dependencies are installed.")

    def on_setup_finished(self, success, message):
        self.setup_dialog.close()
        if success:
            QMessageBox.information(self, "Setup Complete", "All dependencies installed successfully! You can now use the plugin.")
        else:
            QMessageBox.critical(self, "Setup Failed", f"An error occurred during installation:\n{message}\n\nPlease check your internet connection and try again.")

    # ------------------------------------------------------------------
    # RESTORE ORIGINAL STYLING (THE FIX)
    # ------------------------------------------------------------------
    def apply_master_stylesheet(self):
        """Forces the original CSS globally so moving widgets doesn't break their styles."""
        original_css = """
            /* --- Window & Tab Styles --- */
            QWidget { background-color: #2b2b2b; } /* Matches dark mode behind tabs */
            QStackedWidget { background-color: #ffffff; }
            QTabWidget::pane { border: none; background-color: #D7D5D2; }
            QTabBar::tab { background-color: #b0b0b0; color: black; padding: 10px 20px; font-weight: bold; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
            QTabBar::tab:selected { background-color: #D7D5D2; }

            /* --- Base Areas --- */
            QWidget#Widget_Map_Area { background-color: #ffffff; }
            QScrollArea, QWidget#Widget_Inputs { background-color: #D7D5D2; border: none; }

            /* --- GroupBox Borders & Titles --- */
            /* Map Area GroupBoxes (White Titles) */
            QWidget#Widget_Map_Area QGroupBox { font: 600 12px "Arial"; color: #E0E0E0; border: 2px solid #555; border-radius: 10px; margin-top: 16px; background-color: transparent; padding: 12px; }
            QWidget#Widget_Map_Area QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 8px; background-color: #ffffff; color: black; position: absolute; margin-top: 10px; }
            
            /* Input Area GroupBoxes (Gray Titles) */
            QWidget#Widget_Inputs QGroupBox { font: 600 12px "Arial"; color: #E0E0E0; border: 2px solid #555; border-radius: 10px; margin-top: 16px; background-color: transparent; padding: 12px; }
            QWidget#Widget_Inputs QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 8px; background-color: #D7D5D2; color: black; position: absolute; margin-top: 10px; }

            /* --- General Text --- */
            QLabel { color: black; }
            QLabel#Lable_EIL_Hazard_Map, QLabel#Lable_Landslide { color: black; font: 700 16pt "Arial"; }

            /* --- The "Pill" Styled File Browsers --- */
            /* Browse Button (Left side) */
            QPushButton#PushButton_GPKG, QPushButton#PushButton_ROI, QPushButton#PushButton_DEM, 
            QPushButton#PushButton_Sentinel_2_Pre_Event, QPushButton#PushButton_Sentinel_2_Post_Event {
                font-family: montserrat; border: 1px solid #3a3a3a; border-top-left-radius: 6px; border-bottom-left-radius: 6px; border-top-right-radius: 0px; border-bottom-right-radius: 0px; background-color: #ffffff; color: black; padding: 6px 14px; font-weight: 10; font-size: 10px; min-height: 10px; min-width: 55px;
            }
            /* Text Area (Right side) */
            QPlainTextEdit#PTE_GPKG, QPlainTextEdit#PTE_ROI, QPlainTextEdit#PTE_DEM, 
            QPlainTextEdit#PTE_Sentinel_2_Pre_Event, QPlainTextEdit#PTE_Sentinel_2_Post_Event {
                border: 1px solid #3a3a3a; border-left: 0px; border-top-right-radius: 6px; border-bottom-right-radius: 6px; border-top-left-radius: 0px; border-bottom-left-radius: 0px; background-color: #D5D5D5; padding: 0px 0px; min-height: 10px; font-size: 10px; font-weight: 10; color: black;
            }

            /* --- Standard Buttons (Footer) --- */
            QPushButton { font-family: montserrat; border: 1px solid #3a3a3a; border-radius: 6px; background-color: #ffffff; color: black; padding: 6px 14px; font-weight: bold; font-size: 10px; min-height: 10px; min-width: 55px; }
            QPushButton:hover { background-color: #f4f4f4; }
            QPushButton:pressed { background-color: #eaeaea; }
            
            /* --- Dropdowns & Inputs --- */
            QComboBox { border: 1px solid #3a3a3a; border-radius: 6px; padding: 4px 10px; background-color: #D5D5D5; color: black; font-size: 11px; min-height: 25px; }
            QLineEdit { border: 1px solid #3a3a3a; border-radius: 6px; padding: 4px 10px; background-color: #ffffff; color: black; font-size: 11px; min-height: 25px; }
        """
        self.centralwidget.setStyleSheet(original_css)

    # ------------------------------------------------------------------
    # COMMON UTILS
    # ------------------------------------------------------------------
    def get_venv_python_path(self, venv_name):
        """Returns the correct Python executable path based on the Operating System."""
        import platform
        if platform.system() == "Windows":
            return os.path.join(self._base_dir, venv_name, "Scripts", "python.exe")
        else:
            return os.path.join(self._base_dir, venv_name, "bin", "python")

    def _safe_float(self, val):
        if val is None: return None
        if isinstance(val, QVariant):
            if val.isNull(): return None
            val = val.value()
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def eventFilter(self, source, event):
        eil_views = {
            self.ui_eil.GraphicsView_Input_GPKG.viewport(): self.ui_eil.GraphicsView_Input_GPKG,
            self.ui_eil.GraphicsView_Hazard_Map.viewport(): self.ui_eil.GraphicsView_Hazard_Map,
            self.ui_eil.GraphicsView_Cohesion_Map.viewport(): self.ui_eil.GraphicsView_Cohesion_Map,
            self.ui_eil.GraphicsView_Friction_Map.viewport(): self.ui_eil.GraphicsView_Friction_Map
        }
        
        if source in eil_views and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                target_view = eil_views[source]
                self.identify_feature_eil(event.pos(), target_view)
                return True
                
        return super().eventFilter(source, event)

    # ==================================================================
    # LANDSLIDE LOGIC
    # ==================================================================
    def build_dynamic_landslide_ui(self):
        self.ui_ls.Label_ROI.setText("LULC Shapefile:")
        self.ui_ls.GroupBox_ROI.setTitle("LULC Preview") 
        
        self.ui_ls.GroupBox_ROI_Selection = QtWidgets.QGroupBox(self.ui_ls.Widget_Inputs)
        self.ui_ls.GroupBox_ROI_Selection.setTitle("Region of Interest")
        self.ui_ls.GroupBox_ROI_Selection.setObjectName("GroupBox_ROI_Selection")
        
        self.ui_ls.layout_roi_select = QtWidgets.QGridLayout(self.ui_ls.GroupBox_ROI_Selection)
        self.ui_ls.layout_roi_select.setContentsMargins(10, 15, 10, 15)
        self.ui_ls.layout_roi_select.setVerticalSpacing(15)
        self.ui_ls.layout_roi_select.setHorizontalSpacing(10)
        self.ui_ls.layout_roi_select.setColumnStretch(1, 1)

        self.ui_ls.Label_Search = QtWidgets.QLabel("Search Location:", self.ui_ls.GroupBox_ROI_Selection)
        self.ui_ls.LineEdit_Search = QtWidgets.QLineEdit(self.ui_ls.GroupBox_ROI_Selection)
        self.ui_ls.LineEdit_Search.setPlaceholderText("Type to search (e.g. Alamada)...")
        
        self.ui_ls.Label_Level = QtWidgets.QLabel("Select Level:", self.ui_ls.GroupBox_ROI_Selection)
        self.ui_ls.ComboBox_ROI_Level = QtWidgets.QComboBox(self.ui_ls.GroupBox_ROI_Selection)
        self.ui_ls.ComboBox_ROI_Level.addItems(["Region", "Province", "Municipality", "Barangay"])
        self.ui_ls.ComboBox_ROI_Level.setCurrentText("Municipality") 
        
        self.ui_ls.Label_Name = QtWidgets.QLabel("Select Name:", self.ui_ls.GroupBox_ROI_Selection)
        self.ui_ls.ComboBox_ROI_Name = QtWidgets.QComboBox(self.ui_ls.GroupBox_ROI_Selection)
        self.ui_ls.ComboBox_ROI_Name.setEditable(False)

        self.ui_ls.layout_roi_select.addWidget(self.ui_ls.Label_Search, 0, 0)
        self.ui_ls.layout_roi_select.addWidget(self.ui_ls.LineEdit_Search, 0, 1)
        self.ui_ls.layout_roi_select.addWidget(self.ui_ls.Label_Level, 1, 0)
        self.ui_ls.layout_roi_select.addWidget(self.ui_ls.ComboBox_ROI_Level, 1, 1)
        self.ui_ls.layout_roi_select.addWidget(self.ui_ls.Label_Name, 2, 0)
        self.ui_ls.layout_roi_select.addWidget(self.ui_ls.ComboBox_ROI_Name, 2, 1)
        
        self.ui_ls.verticalLayout_4.insertWidget(2, self.ui_ls.GroupBox_ROI_Selection)

    def connect_landslide_signals(self):
        self.ui_ls.PushButton_ROI.clicked.connect(self.select_lulc_file_ls) 
        self.ui_ls.PushButton_DEM.clicked.connect(self.select_dem_file_ls)
        self.ui_ls.PushButton_Sentinel_2_Pre_Event.clicked.connect(self.select_pre_event_file_ls)
        self.ui_ls.PushButton_Sentinel_2_Post_Event.clicked.connect(self.select_post_event_file_ls)
        self.ui_ls.Button_Detect.clicked.connect(self.run_landslide_detection)
        self.ui_ls.Button_Save.clicked.connect(self.save_landslide_result)

        self.ui_ls.ComboBox_ROI_Level.currentTextChanged.connect(self.populate_location_names_ls)
        self.populate_location_names_ls()
        QtCore.QTimer.singleShot(100, self.build_search_index_ls)

    def build_search_index_ls(self):
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
                except: pass
        completer = QtWidgets.QCompleter(all_names, self.ui_ls.LineEdit_Search)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.ui_ls.LineEdit_Search.setCompleter(completer)
        completer.activated.connect(self.on_search_selected_ls)

    def on_search_selected_ls(self, text):
        level = self.location_index.get(text)
        if level:
            self.ui_ls.ComboBox_ROI_Level.setCurrentText(level)
            index = self.ui_ls.ComboBox_ROI_Name.findText(text)
            if index != -1:
                self.ui_ls.ComboBox_ROI_Name.setCurrentIndex(index)
            else:
                self.ui_ls.ComboBox_ROI_Name.setCurrentText(text)

    def populate_location_names_ls(self):
        self.ui_ls.ComboBox_ROI_Name.clear()
        selected_level = self.ui_ls.ComboBox_ROI_Level.currentText()
        config = self.admin_config.get(selected_level)
        if not config: return

        shp_path = config["path"]
        col_name = config["col"]
        if not os.path.exists(shp_path):
            self.ui_ls.ComboBox_ROI_Name.addItem(f"Error: missing file")
            return

        layer = QgsVectorLayer(shp_path, "roi_temp", "ogr")
        if not layer.isValid(): return

        try:
            idx = layer.fields().indexOf(col_name)
            unique_values = layer.uniqueValues(idx)
            sorted_names = sorted([str(v) for v in unique_values if v])
            self.ui_ls.ComboBox_ROI_Name.addItems(sorted_names)
        except: pass

    def select_lulc_file_ls(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select LULC Shapefile", "", "Shapefiles (*.shp)")
        if filename: 
            self.ui_ls.PTE_ROI.setPlainText(filename)
            self.preview_layer_ls(filename, self.ui_ls.GraphicsView_ROI, is_raster=False)

    def select_dem_file_ls(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select DEM", "", "Tiff (*.tif)")
        if filename: 
            self.ui_ls.PTE_DEM.setPlainText(filename)
            self.preview_layer_ls(filename, self.ui_ls.GraphicsView_DEM_2, is_raster=True)

    def select_pre_event_file_ls(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Pre-Event", "", "Tiff (*.tif)")
        if filename: 
            self.ui_ls.PTE_Sentinel_2_Pre_Event.setPlainText(filename)
            self.preview_layer_ls(filename, self.ui_ls.GraphicsView_Pre_Event, is_raster=True)

    def select_post_event_file_ls(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Post-Event", "", "Tiff (*.tif)")
        if filename: 
            self.ui_ls.PTE_Sentinel_2_Post_Event.setPlainText(filename)
            self.preview_layer_ls(filename, self.ui_ls.GraphicsView_Post_Event, is_raster=True)

    def preview_layer_ls(self, file_path, graphics_view, is_raster=False):
        if is_raster: layer = QgsRasterLayer(file_path, "preview")
        else: layer = QgsVectorLayer(file_path, "preview", "ogr")
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
        scene = QGraphicsScene()
        item = scene.addPixmap(QPixmap.fromImage(image))
        graphics_view.setScene(scene)
        graphics_view.fitInView(item, Qt.KeepAspectRatio)

    def run_landslide_detection(self):
        lulc = self.ui_ls.PTE_ROI.toPlainText() 
        dem = self.ui_ls.PTE_DEM.toPlainText()
        before = self.ui_ls.PTE_Sentinel_2_Pre_Event.toPlainText()
        after = self.ui_ls.PTE_Sentinel_2_Post_Event.toPlainText()
        
        selected_level = self.ui_ls.ComboBox_ROI_Level.currentText()
        selected_name = self.ui_ls.ComboBox_ROI_Name.currentText()
        config = self.admin_config.get(selected_level)
        if not config: return
        
        roi_file_path = config["path"]
        filter_col = config["col"]

        if not all([lulc, dem, before, after]):
            QMessageBox.warning(self, "Missing Inputs", "Please select LULC, DEM, Before, and After files.")
            return

        temp_output_path = os.path.join(tempfile.gettempdir(), "temp_landslide_result.tif")
        worker_script = os.path.join(self._base_dir, "landslide_worker.py")

        if not os.path.exists(self.ls_venv_python):
             QMessageBox.critical(self, "Config Error", f"Virtual Environment Python not found at:\n{self.ls_venv_python}")
             return

        command = [
            self.ls_venv_python, worker_script,
            "--dem", dem, "--before", before, "--after", after, "--lulc", lulc,
            "--output", temp_output_path, "--roi_path", roi_file_path,
            "--filter_col", filter_col, "--filter_val", selected_name 
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
                        QMessageBox.information(self, "Success", "Detection Complete! You can now click SAVE.")
                        mask_path = result_json.get("output_mask")
                        ndvi_path = result_json.get("output_ndvi")
                        self.current_result_path_ls = mask_path 

                        if ndvi_path and os.path.exists(ndvi_path):
                             self.preview_layer_ls(ndvi_path, self.ui_ls.GraphicsView_NDVI, is_raster=True)
                        if mask_path and os.path.exists(mask_path):
                             self.preview_layer_ls(mask_path, self.ui_ls.GraphicsView_Result, is_raster=True)
                             rlayer = QgsRasterLayer(mask_path, "Landslide Result (Preview)")
                             if rlayer.isValid(): QgsProject.instance().addMapLayer(rlayer)
                    else:
                        QMessageBox.critical(self, "Worker Error", f"Script failed: {result_json.get('message')}")
                except json.JSONDecodeError:
                     QMessageBox.warning(self, "Error", "Could not parse script output.")
            else:
                QMessageBox.critical(self, "Error", f"Process failed.\n{process.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "System Error", str(e))
        finally:
             QtWidgets.QApplication.restoreOverrideCursor()

    def save_landslide_result(self):
        if not self.current_result_path_ls or not os.path.exists(self.current_result_path_ls):
            QMessageBox.warning(self, "Save", "No detection result exists yet.\nPlease run 'DETECT' first.")
            return

        roi_name = self.ui_ls.ComboBox_ROI_Name.currentText()
        safe_name = (roi_name or "Landslide_Result").replace(" ", "_")
        default_path = os.path.join(QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation), f"{safe_name}_Landslide.tif")

        filename, _ = QFileDialog.getSaveFileName(self, "Save Landslide Mask", default_path, "Tiff Files (*.tif)")
        if filename:
            try:
                shutil.copy2(self.current_result_path_ls, filename)
                QMessageBox.information(self, "Saved", f"File successfully saved to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save file:\n{str(e)}")


    # ==================================================================
    # EIL LOGIC
    # ==================================================================
    def connect_eil_signals(self):
        self.ui_eil.PushButton_GPKG.clicked.connect(self.select_gpkg_file_eil)
        self.ui_eil.Button_Detect.clicked.connect(self.run_eil_detection)
        self.ui_eil.Button_Save.clicked.connect(self.save_eil_result)

    def select_gpkg_file_eil(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Choose GeoPackage", self._base_dir, "GeoPackage (*.gpkg);;Shapefiles (*.shp)")
        if fn:
            self.ui_eil.PTE_GPKG.setPlainText(fn)
            self.refresh_map_display_eil()

    def run_eil_detection(self):
        script_path = os.path.join(self._base_dir, "headless_model.py")

        if not os.path.exists(self.MODEL_PATH):
             QMessageBox.critical(self, "Missing Model", f"Could not find model at:\n{self.MODEL_PATH}")
             return

        source_gpkg = self.ui_eil.PTE_GPKG.toPlainText().strip()
        if not os.path.exists(source_gpkg):
            QMessageBox.warning(self, "Error", "Invalid GPKG path.")
            return

        folder = os.path.dirname(source_gpkg)
        filename = os.path.basename(source_gpkg)
        name, ext = os.path.splitext(filename)
        output_gpkg = os.path.join(folder, f"{name}_output{ext}")
        self.current_output_gpkg_eil = output_gpkg
        output_csv = os.path.join(tempfile.gettempdir(), "qgis_prediction_results.csv")

        try: shutil.copy2(source_gpkg, output_gpkg)
        except Exception as e:
            QMessageBox.critical(self, "Copy Error", f"Could not create output file:\n{e}")
            return

        my_env = os.environ.copy()
        if 'PYTHONHOME' in my_env: del my_env['PYTHONHOME']
        if 'PYTHONPATH' in my_env: del my_env['PYTHONPATH']
        
        cmd = [
            self.eil_venv_python, script_path, 
            "--gpkg", output_gpkg, "--model", self.MODEL_PATH, "--output", output_csv
        ]

        self.progress_dialog = QProgressDialog("Running AI Model... This may take a minute.", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Processing")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None) 
        
        self.worker = PredictionWorker(cmd, my_env, output_csv, output_gpkg)
        self.worker.finished.connect(self.on_eil_prediction_complete)
        self.worker.error.connect(self.on_eil_prediction_error)
        
        self.progress_dialog.show()
        self.worker.start()

    def on_eil_prediction_error(self, err_msg):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Error", f"Prediction Failed:\n{err_msg}")

    def on_eil_prediction_complete(self, data, _):
        self.progress_dialog.setLabelText("Updating Layer Attributes...")
        try:
            rows = data['rows']
            output_gpkg = self.current_output_gpkg_eil
            
            vlayer = QgsVectorLayer(output_gpkg, "result_layer", "ogr")
            if not vlayer.isValid(): raise Exception("Could not load output GPKG.")

            pr = vlayer.dataProvider()
            needed = ["sus_pinn_landslide", "cohesion", "internal_friction"]
            existing = vlayer.fields().names()
            to_add = [QgsField(f, QVariant.Double) for f in needed if f not in existing]
            
            if to_add:
                vlayer.startEditing()
                pr.addAttributes(to_add)
                vlayer.updateFields()
                vlayer.commitChanges()

            id_map = {} 
            fid_idx = vlayer.fields().indexFromName("fid") 
            if fid_idx != -1:
                for f in vlayer.getFeatures():
                    val = self._safe_float(f.attributes()[fid_idx])
                    if val is not None:
                        try: id_map[int(val)] = f.id()
                        except: pass
            
            results = {}
            idx_sus = vlayer.fields().indexFromName("sus_pinn_landslide")
            idx_coh = vlayer.fields().indexFromName("cohesion")
            idx_fric = vlayer.fields().indexFromName("internal_friction")
            
            for row in rows:
                csv_id_raw = row.get('fid')
                if not csv_id_raw: continue
                try:
                    csv_id = int(float(csv_id_raw))
                    if csv_id in id_map:
                        results[id_map[csv_id]] = {
                            idx_sus: float(row['sus_pinn_landslide']),
                            idx_coh: float(row['cohesion']),
                            idx_fric: float(row['internal_friction'])
                        }
                except ValueError: continue

            if not results:
                self.progress_dialog.close()
                QMessageBox.warning(self, "Warning", "No matching IDs found between CSV and GPKG.")
                return

            vlayer.startEditing()
            pr.changeAttributeValues(results)
            vlayer.commitChanges()
            del vlayer
            
            self.progress_dialog.close()
            self.ui_eil.PTE_GPKG.setPlainText(output_gpkg)
            self.refresh_map_display_eil()
            QMessageBox.information(self, "Success", f"Prediction Complete!\nFile: {output_gpkg}")
        except Exception as e:
            self.progress_dialog.close()
            QMessageBox.critical(self, "Update Error", f"Failed to update layer:\n{e}")

    def refresh_map_display_eil(self):
        gpkg_path = self.ui_eil.PTE_GPKG.toPlainText().strip()
        if not gpkg_path or not os.path.exists(gpkg_path):
            self.ui_eil.GraphicsView_Input_GPKG.setScene(QGraphicsScene())
            self.ui_eil.GraphicsView_Hazard_Map.setScene(QGraphicsScene())
            self.ui_eil.GraphicsView_Cohesion_Map.setScene(QGraphicsScene())
            self.ui_eil.GraphicsView_Friction_Map.setScene(QGraphicsScene())
            return

        try:
            # 1. Input Map
            layer_input = QgsVectorLayer(gpkg_path, "input_layer", "ogr")
            if layer_input.isValid():
                self.render_layer_to_scene_eil(layer_input, self.ui_eil.GraphicsView_Input_GPKG)
            
            # 2. Hazard Map
            layer_hazard = QgsVectorLayer(gpkg_path, "hazard_layer", "ogr")
            if layer_hazard.isValid() and "sus_pinn_landslide" in layer_hazard.fields().names():
                self.update_stats_table_eil(layer_hazard, "sus_pinn_landslide", self.ui_eil.Table_Hazard)
                self.apply_heatmap_style_eil(layer_hazard, "sus_pinn_landslide")
                self.render_layer_to_scene_eil(layer_hazard, self.ui_eil.GraphicsView_Hazard_Map)
            
            # 3. Cohesion Map
            layer_coh = QgsVectorLayer(gpkg_path, "cohesion_layer", "ogr")
            if layer_coh.isValid() and "cohesion" in layer_coh.fields().names():
                self.update_stats_table_eil(layer_coh, "cohesion", self.ui_eil.Table_Cohesion)
                self.apply_heatmap_style_eil(layer_coh, "cohesion")
                self.render_layer_to_scene_eil(layer_coh, self.ui_eil.GraphicsView_Cohesion_Map)

            # 4. Friction Map
            layer_fric = QgsVectorLayer(gpkg_path, "friction_layer", "ogr")
            if layer_fric.isValid() and "internal_friction" in layer_fric.fields().names():
                self.update_stats_table_eil(layer_fric, "internal_friction", self.ui_eil.Table_Friction)
                self.apply_heatmap_style_eil(layer_fric, "internal_friction")
                self.render_layer_to_scene_eil(layer_fric, self.ui_eil.GraphicsView_Friction_Map)
        except Exception as e:
            print(f"Render failed: {e}")

    def render_layer_to_scene_eil(self, layer, target_view):
        try:
            rect = target_view.viewport().rect()
            settings = QgsMapSettings()
            settings.setLayers([layer])
            settings.setBackgroundColor(QColor(255, 255, 255))
            settings.setOutputSize(QSize(rect.width(), rect.height()))
            
            crs = layer.crs()
            if not crs.isValid(): crs = QgsCoordinateReferenceSystem("EPSG:4326")
            settings.setDestinationCrs(crs)
            
            extent = layer.extent()
            extent.scale(1.1)
            settings.setExtent(extent)
            
            render_job = QgsMapRendererSequentialJob(settings)
            render_job.start()
            render_job.waitForFinished()
            img = render_job.renderedImage()
            
            pixmap = QPixmap.fromImage(img)
            scene = QGraphicsScene()
            scene.addPixmap(pixmap)
            target_view.setScene(scene)
            target_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            
            self.map_view_data[target_view] = {
                'extent': extent,
                'width': rect.width(),
                'height': rect.height()
            }
        except Exception as e:
            print(f"Internal Render Error: {e}")

    def calculate_manual_breaks_eil(self, layer, field_name):
        idx = layer.fields().indexFromName(field_name)
        if idx == -1: return None
        count = layer.featureCount()
        sample_size = 10000
        values = []
        
        iterator = layer.getFeatures()
        for i, f in enumerate(iterator):
            if count > sample_size and i % (count // sample_size) != 0: continue
            clean_val = self._safe_float(f.attributes()[idx])
            if clean_val is not None: values.append(clean_val)
        
        if not values: return None
        arr = np.array(values)
        min_val, max_val = np.min(arr), np.max(arr)
        if np.isclose(min_val, max_val, atol=1e-12): return [(min_val, max_val)]
            
        try:
            if field_name == "sus_pinn_landslide":
                breaks = np.unique(np.percentile(arr, [0, 33.33, 66.67, 100]))
            else:
                breaks = np.linspace(min_val, max_val, 4)

            if len(breaks) < 4: breaks = np.linspace(min_val, max_val, 4)
            
            ranges = []
            for i in range(len(breaks)-1):
                upper = breaks[i+1] if breaks[i+1] > breaks[i] else breaks[i] + 1e-12
                ranges.append((breaks[i], upper))
            
            unique_ranges = []
            for r in ranges:
                if not unique_ranges or r != unique_ranges[-1]: unique_ranges.append(r)
            return unique_ranges
        except: return [(min_val, max_val)]

    def update_stats_table_eil(self, layer, field_name, table_widget):
        table_widget.setHorizontalHeaderLabels(["Class", "Range", "Color"])
        table_widget.setRowCount(0)
        ranges = self.calculate_manual_breaks_eil(layer, field_name)
        if not ranges: return 

        colors = [QColor(255, 255, 0), QColor(197, 0, 255), QColor(255, 0, 0)]
        if len(ranges) == 1:
            table_widget.insertRow(0)
            table_widget.setItem(0, 0, QTableWidgetItem("Uniform"))
            table_widget.setItem(0, 1, QTableWidgetItem(f"{ranges[0][0]:.4g}"))
            col_item = QTableWidgetItem()
            col_item.setBackground(QBrush(QColor(180, 180, 180)))
            table_widget.setItem(0, 2, col_item)
            return

        labels = ["Low", "Moderate", "High"]
        for i, (lower, upper) in enumerate(ranges):
            row_idx = table_widget.rowCount()
            table_widget.insertRow(row_idx)
            lbl = labels[i] if i < 3 else f"Class {i+1}"
            table_widget.setItem(row_idx, 0, QTableWidgetItem(lbl))
            table_widget.setItem(row_idx, 1, QTableWidgetItem(f"{lower:.4g} - {upper:.4g}"))
            col_idx = i if i < 3 else 2
            col_item = QTableWidgetItem()
            col_item.setBackground(QBrush(colors[col_idx]))
            table_widget.setItem(row_idx, 2, col_item)

    def apply_heatmap_style_eil(self, layer, field_name):
        ranges_data = self.calculate_manual_breaks_eil(layer, field_name)
        if not ranges_data: return

        if len(ranges_data) == 1:
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(180, 180, 180)) 
            symbol.symbolLayer(0).setStrokeStyle(Qt.NoPen)
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            return

        colors = [QColor(255, 255, 0), QColor(197, 0, 255), QColor(255, 0, 0)]
        qgs_ranges = []
        for i, (lower, upper) in enumerate(ranges_data):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            col_idx = i if i < 3 else 2
            symbol.setColor(colors[col_idx])
            symbol.setOpacity(1.0)
            symbol.symbolLayer(0).setStrokeStyle(Qt.NoPen)
            lbl = ["Low", "Moderate", "High"][col_idx] if col_idx < 3 else "High"
            qgs_ranges.append(QgsRendererRange(lower, upper, symbol, lbl))

        renderer = QgsGraduatedSymbolRenderer(field_name, qgs_ranges)
        renderer.setMode(QgsGraduatedSymbolRenderer.Custom)
        layer.setRenderer(renderer)

    def identify_feature_eil(self, screen_pos, target_view):
        view_data = self.map_view_data.get(target_view)
        if not view_data or view_data['width'] == 0: return

        extent, render_width, render_height = view_data['extent'], view_data['width'], view_data['height']
        
        scene = target_view.scene()
        if scene:
            if self.debug_marker and self.debug_marker in scene.items():
                scene.removeItem(self.debug_marker)
            scene_pos = target_view.mapToScene(screen_pos)
            self.debug_marker = scene.addEllipse(scene_pos.x() - 5, scene_pos.y() - 5, 10, 10, QPen(Qt.red, 2), QBrush(Qt.NoBrush))

        scene_pos = target_view.mapToScene(screen_pos)
        ratio_x = scene_pos.x() / render_width
        ratio_y = scene_pos.y() / render_height
        map_x = extent.xMinimum() + (extent.width() * ratio_x)
        map_y = extent.yMaximum() - (extent.height() * ratio_y)
        
        search_radius = extent.width() * 0.05
        if search_radius == 0: search_radius = 100

        search_rect = QgsGeometry.fromPointXY(QgsPointXY(map_x, map_y)).buffer(search_radius, 5).boundingBox()
        request = QgsFeatureRequest().setFilterRect(search_rect)
        
        gpkg_path = self.ui_eil.PTE_GPKG.toPlainText().strip()
        if not os.path.exists(gpkg_path): return

        live_layer = QgsVectorLayer(gpkg_path, "query", "ogr")
        if not live_layer.isValid(): return

        features = list(live_layer.getFeatures(request))
        if features:
            click_point = QgsPointXY(map_x, map_y)
            closest_feat = min(features, key=lambda f: f.geometry().distance(QgsGeometry.fromPointXY(click_point)))
            
            info_str = f"<b>Feature Info (ID: {closest_feat.id()}):</b><br><br>"
            fields = live_layer.fields()
            for i, attr in enumerate(closest_feat.attributes()):
                name = fields[i].name()
                real_val = self._safe_float(attr)
                val_display = f"{real_val:.4g}" if real_val is not None else str(attr.value() if isinstance(attr, QVariant) else attr)
                
                if name in ["sus_pinn_landslide", "cohesion", "internal_friction"]:
                    info_str += f"<b><font color='blue'>{name}: {val_display}</font></b><br>"
                else:
                    info_str += f"<b>{name}:</b> {val_display}<br>"
            
            QMessageBox.information(self, "Identify", info_str)

    def save_eil_result(self):
        current_gpkg = self.ui_eil.PTE_GPKG.toPlainText().strip()
        if not current_gpkg or not os.path.exists(current_gpkg):
            QMessageBox.warning(self, "Save Error", "No GeoPackage found to save.\nPlease run a prediction first.")
            return

        try:
            base_name = os.path.basename(current_gpkg)
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Result GeoPackage", os.path.join(os.path.dirname(current_gpkg), base_name), "GeoPackage (*.gpkg)")
            if not save_path: return
            if not save_path.lower().endswith('.gpkg'): save_path += '.gpkg'
            if os.path.abspath(current_gpkg) == os.path.abspath(save_path):
                QMessageBox.information(self, "Save", "Destination is the same as current file.")
                return

            shutil.copy2(current_gpkg, save_path)
            QMessageBox.information(self, "Success", f"File successfully saved to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")