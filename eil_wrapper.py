import os
import csv
import subprocess
import shutil
import tempfile
import numpy as np

# QGIS Imports
from qgis.PyQt import QtCore, QtWidgets
from qgis.PyQt.QtWidgets import (
    QMainWindow, QMessageBox, QFileDialog, QGraphicsScene, 
    QTableWidgetItem, QProgressDialog
)
from qgis.PyQt.QtCore import (
    QEvent, Qt, QVariant, QSize, QThread, pyqtSignal
)
from qgis.PyQt.QtGui import QImage, QPixmap, QColor, QPen, QBrush

# Import core QGIS classes
from qgis.core import (
    QgsPointXY, 
    QgsGeometry, 
    QgsFeatureRequest, 
    QgsVectorLayer, 
    QgsField,
    QgsProject,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsSymbol,
    QgsStyle,
    QgsSingleSymbolRenderer,
    QgsMapSettings,
    QgsMapRendererSequentialJob,
    QgsCoordinateReferenceSystem
)

from .eil_mainwindow import Ui_MainWindow

# ==============================================================================
# WORKER THREAD (Runs in Background)
# ==============================================================================
class PredictionWorker(QThread):
    """
    Runs the 'headless_model.py' script and parses the CSV result 
    in a background thread to keep the UI responsive.
    """
    finished = pyqtSignal(dict, dict) # Emits (results_dict, id_map_data)
    error = pyqtSignal(str)

    def __init__(self, cmd, env, output_csv, output_gpkg):
        super().__init__()
        self.cmd = cmd
        self.env = env
        self.output_csv = output_csv
        self.output_gpkg = output_gpkg

    def run(self):
        try:
            # 1. Run Subprocess
            process = subprocess.run(
                self.cmd, 
                capture_output=True, 
                text=True, 
                env=self.env
            )
            
            if process.returncode != 0:
                self.error.emit(f"Process Failed:\n{process.stderr}")
                return

            if not os.path.exists(self.output_csv):
                self.error.emit("Worker finished but output CSV not found.")
                return

            # 2. Parse CSV
            csv_data = []
            with open(self.output_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    csv_data.append(row)
            
            self.finished.emit({"rows": csv_data}, {})

        except Exception as e:
            self.error.emit(str(e))


# ==============================================================================
# MAIN DIALOG
# ==============================================================================
class PluginDialog(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        self.MODEL_PATH = os.path.join(self._base_dir, "model", "my_model.keras") 
        
        # State tracking for map clicks
        self.map_view_data = {} # Maps view to its current extent and dimensions
        self.debug_marker = None
        self.worker = None
        
        # Connect Map Click Events for all 4 views
        self.GraphicsView_Input_GPKG.viewport().installEventFilter(self)
        self.GraphicsView_Hazard_Map.viewport().installEventFilter(self)
        self.GraphicsView_Cohesion_Map.viewport().installEventFilter(self)
        self.GraphicsView_Friction_Map.viewport().installEventFilter(self)

        # Connect Buttons
        self.PushButton_GPKG.clicked.connect(self._pick_gpkg)
        self.Button_Detect.clicked.connect(self.on_detect_clicked)
        self.Button_Save.clicked.connect(self._save_inputs)

    # ------------------------------------------------------------------
    # MAIN LOGIC (With Threading)
    # ------------------------------------------------------------------
    def on_detect_clicked(self):
        venv_python = os.path.join(self._base_dir, "venv", "bin", "python")
        script_path = os.path.join(self._base_dir, "headless_model.py")

        if not os.path.exists(self.MODEL_PATH):
             QMessageBox.critical(self, "Missing Model", f"Could not find model at:\n{self.MODEL_PATH}")
             return

        source_gpkg = self.PTE_GPKG.toPlainText().strip()
        if not os.path.exists(source_gpkg):
            QMessageBox.warning(self, "Error", "Invalid GPKG path.")
            return

        folder = os.path.dirname(source_gpkg)
        filename = os.path.basename(source_gpkg)
        name, ext = os.path.splitext(filename)
        output_gpkg = os.path.join(folder, f"{name}_output{ext}")
        self.current_output_gpkg = output_gpkg
        output_csv = os.path.join(tempfile.gettempdir(), "qgis_prediction_results.csv")

        try:
            shutil.copy2(source_gpkg, output_gpkg)
        except Exception as e:
            QMessageBox.critical(self, "Copy Error", f"Could not create output file:\n{e}")
            return

        # Prepare Command
        my_env = os.environ.copy()
        if 'PYTHONHOME' in my_env: del my_env['PYTHONHOME']
        if 'PYTHONPATH' in my_env: del my_env['PYTHONPATH']
        
        cmd = [
            # Remove "arch", "-arm64", if you are not on an Apple Silicon Mac
            venv_python, 
            script_path, 
            "--gpkg", output_gpkg,
            "--model", self.MODEL_PATH,
            "--output", output_csv
        ]

        # Setup Loading Bar
        self.progress_dialog = QProgressDialog("Running AI Model... This may take a minute.", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Processing")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setCancelButton(None) 
        
        # Start Worker
        self.worker = PredictionWorker(cmd, my_env, output_csv, output_gpkg)
        self.worker.finished.connect(self.on_prediction_complete)
        self.worker.error.connect(self.on_prediction_error)
        
        self.progress_dialog.show()
        self.worker.start()

    def on_prediction_error(self, err_msg):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Error", f"Prediction Failed:\n{err_msg}")

    def on_prediction_complete(self, data, _):
        self.progress_dialog.setLabelText("Updating Layer Attributes...")
        
        try:
            rows = data['rows']
            output_gpkg = self.current_output_gpkg
            
            vlayer = QgsVectorLayer(output_gpkg, "result_layer", "ogr")
            if not vlayer.isValid():
                raise Exception("Could not load the output GPKG for updating.")

            # Add Attributes
            pr = vlayer.dataProvider()
            needed = ["sus_pinn_landslide", "cohesion", "internal_friction"]
            existing = vlayer.fields().names()
            to_add = [QgsField(f, QVariant.Double) for f in needed if f not in existing]
            
            if to_add:
                vlayer.startEditing()
                pr.addAttributes(to_add)
                vlayer.updateFields()
                vlayer.commitChanges()

            # Build ID Map
            id_map = {} 
            fid_idx = vlayer.fields().indexFromName("fid") 
            
            if fid_idx != -1:
                for f in vlayer.getFeatures():
                    val = f.attributes()[fid_idx]
                    clean_val = self._safe_float(val)
                    if clean_val is not None:
                        try:
                            key_val = int(clean_val) 
                            id_map[key_val] = f.id()
                        except:
                            pass
            
            # Map CSV Rows to Layer IDs
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
                        target_id = id_map[csv_id]
                        results[target_id] = {
                            idx_sus: float(row['sus_pinn_landslide']),
                            idx_coh: float(row['cohesion']),
                            idx_fric: float(row['internal_friction'])
                        }
                except ValueError:
                    continue

            if not results:
                self.progress_dialog.close()
                QMessageBox.warning(self, "Warning", "No matching IDs found between CSV and GPKG.")
                return

            # Bulk Update
            vlayer.startEditing()
            pr.changeAttributeValues(results)
            vlayer.commitChanges()
            
            del vlayer
            
            self.progress_dialog.close()
            self.PTE_GPKG.setPlainText(output_gpkg)
            self.refresh_map_display()
            
            QMessageBox.information(self, "Success", f"Prediction Complete!\nFile: {output_gpkg}")

        except Exception as e:
            self.progress_dialog.close()
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Update Error", f"Failed to update layer:\n{e}")

    # ------------------------------------------------------------------
    # DISPLAY LOGIC
    # ------------------------------------------------------------------
    def refresh_map_display(self):
        gpkg_path = self.PTE_GPKG.toPlainText().strip()
        if not gpkg_path or not os.path.exists(gpkg_path):
            self.GraphicsView_Input_GPKG.setScene(QGraphicsScene())
            self.GraphicsView_Hazard_Map.setScene(QGraphicsScene())
            self.GraphicsView_Cohesion_Map.setScene(QGraphicsScene())
            self.GraphicsView_Friction_Map.setScene(QGraphicsScene())
            return

        try:
            # 1. Input Map
            layer_input = QgsVectorLayer(gpkg_path, "input_layer", "ogr")
            if layer_input.isValid():
                self.render_layer_to_scene(layer_input, self.GraphicsView_Input_GPKG)
            
            # 2. Hazard Map
            layer_hazard = QgsVectorLayer(gpkg_path, "hazard_layer", "ogr")
            if layer_hazard.isValid() and "sus_pinn_landslide" in layer_hazard.fields().names():
                self.update_stats_table(layer_hazard, "sus_pinn_landslide", self.Table_Hazard)
                self.apply_heatmap_style(layer_hazard, "sus_pinn_landslide")
                self.render_layer_to_scene(layer_hazard, self.GraphicsView_Hazard_Map)
            
            # 3. Cohesion Map
            layer_coh = QgsVectorLayer(gpkg_path, "cohesion_layer", "ogr")
            if layer_coh.isValid() and "cohesion" in layer_coh.fields().names():
                self.update_stats_table(layer_coh, "cohesion", self.Table_Cohesion)
                self.apply_heatmap_style(layer_coh, "cohesion")
                self.render_layer_to_scene(layer_coh, self.GraphicsView_Cohesion_Map)

            # 4. Friction Map
            layer_fric = QgsVectorLayer(gpkg_path, "friction_layer", "ogr")
            if layer_fric.isValid() and "internal_friction" in layer_fric.fields().names():
                self.update_stats_table(layer_fric, "internal_friction", self.Table_Friction)
                self.apply_heatmap_style(layer_fric, "internal_friction")
                self.render_layer_to_scene(layer_fric, self.GraphicsView_Friction_Map)

        except Exception as e:
            print(f"Render failed: {e}")

    def render_layer_to_scene(self, layer, target_view):
        """Renders the styled layer object directly to the target graphics view."""
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
            extent.scale(1.1) # Add slight margin
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
            
            # Store view dimensions for the identify tool
            self.map_view_data[target_view] = {
                'extent': extent,
                'width': rect.width(),
                'height': rect.height()
            }
            
        except Exception as e:
            print(f"Internal Render Error: {e}")

    def calculate_manual_breaks(self, layer, field_name):
        idx = layer.fields().indexFromName(field_name)
        if idx == -1: return None
        
        count = layer.featureCount()
        sample_size = 10000
        values = []
        
        iterator = layer.getFeatures()
        for i, f in enumerate(iterator):
            if count > sample_size and i % (count // sample_size) != 0: continue
            
            raw_val = f.attributes()[idx]
            clean_val = self._safe_float(raw_val)
            if clean_val is not None:
                values.append(clean_val)
        
        if not values: return None
        arr = np.array(values)
        min_val, max_val = np.min(arr), np.max(arr)
        
        if np.isclose(min_val, max_val, atol=1e-12):
            return [(min_val, max_val)]
            
        try:
            if field_name == "sus_pinn_landslide":
                breaks = np.unique(np.percentile(arr, [0, 33.33, 66.67, 100]))
            else:
                breaks = np.linspace(min_val, max_val, 4)

            if len(breaks) < 4:
                breaks = np.linspace(min_val, max_val, 4)
            
            ranges = []
            for i in range(len(breaks)-1):
                lower = breaks[i]
                upper = breaks[i+1]
                if upper <= lower: upper = lower + 1e-12
                ranges.append((lower, upper))
            
            unique_ranges = []
            for r in ranges:
                if not unique_ranges or r != unique_ranges[-1]:
                    unique_ranges.append(r)
            return unique_ranges
        except:
            return [(min_val, max_val)]

    def update_stats_table(self, layer, field_name, table_widget):
        table_widget.setHorizontalHeaderLabels(["Class", "Range", "Color"])
        table_widget.setRowCount(0)
        
        ranges = self.calculate_manual_breaks(layer, field_name)
        if not ranges: return 

        colors = [
            QColor(255, 255, 0),   # Yellow
            QColor(197, 0, 255),   # Purple/Orange
            QColor(255, 0, 0)      # Red
        ]

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

    def apply_heatmap_style(self, layer, field_name):
        ranges_data = self.calculate_manual_breaks(layer, field_name)
        if not ranges_data: return

        if len(ranges_data) == 1:
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(180, 180, 180)) 
            symbol.symbolLayer(0).setStrokeStyle(Qt.NoPen)
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            return

        colors = [
            QColor(255, 255, 0),   # Yellow
            QColor(197, 0, 255),   # Purple/Orange
            QColor(255, 0, 0)      # Red
        ]
        
        qgs_ranges = []
        for i, (lower, upper) in enumerate(ranges_data):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            col_idx = i if i < 3 else 2
            
            symbol.setColor(colors[col_idx])
            symbol.setOpacity(1.0)
            symbol.symbolLayer(0).setStrokeStyle(Qt.NoPen)
            
            lbl = ["Low", "Moderate", "High"][col_idx] if col_idx < 3 else "High"
            rng = QgsRendererRange(lower, upper, symbol, lbl)
            qgs_ranges.append(rng)

        renderer = QgsGraduatedSymbolRenderer(field_name, qgs_ranges)
        renderer.setMode(QgsGraduatedSymbolRenderer.Custom)
        layer.setRenderer(renderer)

    # ------------------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------------------
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
        # Identify which view was clicked
        views = {
            self.GraphicsView_Input_GPKG.viewport(): self.GraphicsView_Input_GPKG,
            self.GraphicsView_Hazard_Map.viewport(): self.GraphicsView_Hazard_Map,
            self.GraphicsView_Cohesion_Map.viewport(): self.GraphicsView_Cohesion_Map,
            self.GraphicsView_Friction_Map.viewport(): self.GraphicsView_Friction_Map
        }
        
        if source in views and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                target_view = views[source]
                self.identify_feature(event.pos(), target_view)
                return True
        return super().eventFilter(source, event)

    def identify_feature(self, screen_pos, target_view):
        view_data = self.map_view_data.get(target_view)
        if not view_data: return

        extent = view_data['extent']
        render_width = view_data['width']
        render_height = view_data['height']
        
        if render_width == 0 or render_height == 0: return

        # Optional: Add a visual marker on the clicked view
        scene = target_view.scene()
        if scene:
            if self.debug_marker and self.debug_marker in scene.items():
                scene.removeItem(self.debug_marker)
            scene_pos = target_view.mapToScene(screen_pos)
            self.debug_marker = scene.addEllipse(
                scene_pos.x() - 5, scene_pos.y() - 5, 10, 10,
                QPen(Qt.red, 2), QBrush(Qt.NoBrush)
            )

        # Convert screen coordinate to Map Extent coordinate
        scene_pos = target_view.mapToScene(screen_pos)
        ratio_x = scene_pos.x() / render_width
        ratio_y = scene_pos.y() / render_height
        
        map_x = extent.xMinimum() + (extent.width() * ratio_x)
        map_y = extent.yMaximum() - (extent.height() * ratio_y)
        
        search_radius = extent.width() * 0.05
        if search_radius == 0: search_radius = 100

        search_rect = QgsGeometry.fromPointXY(QgsPointXY(map_x, map_y)).buffer(search_radius, 5).boundingBox()
        request = QgsFeatureRequest().setFilterRect(search_rect)
        
        gpkg_path = self.PTE_GPKG.toPlainText().strip()
        if not os.path.exists(gpkg_path): return

        live_layer = QgsVectorLayer(gpkg_path, "query", "ogr")
        if not live_layer.isValid(): return

        features = list(live_layer.getFeatures(request))

        if features:
            click_point = QgsPointXY(map_x, map_y)
            closest_feat = None
            min_dist = float('inf')

            for f in features:
                dist = f.geometry().distance(QgsGeometry.fromPointXY(click_point))
                if dist < min_dist:
                    min_dist = dist
                    closest_feat = f
            
            feat = closest_feat
            attrs = feat.attributes()
            fields = live_layer.fields()
            
            info_str = f"<b>Feature Info (ID: {feat.id()}):</b><br><br>"
            for i, attr in enumerate(attrs):
                name = fields[i].name()
                val_display = "NULL"
                
                real_val = self._safe_float(attr)
                if real_val is not None:
                    val_display = f"{real_val:.4g}"
                else:
                    val_display = str(attr.value()) if isinstance(attr, QVariant) else str(attr)
                
                if name in ["sus_pinn_landslide", "cohesion", "internal_friction"]:
                        info_str += f"<b><font color='blue'>{name}: {val_display}</font></b><br>"
                else:
                        info_str += f"<b>{name}:</b> {val_display}<br>"
            
            QMessageBox.information(self, "Identify", info_str)

    def _pick_gpkg(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Choose GeoPackage", self._base_dir, "GeoPackage (*.gpkg);;Shapefiles (*.shp)"
        )
        if fn:
            self.PTE_GPKG.setPlainText(fn)
            self.refresh_map_display()

    def _save_inputs(self):
        current_gpkg = self.PTE_GPKG.toPlainText().strip()
        if not current_gpkg or not os.path.exists(current_gpkg):
            QMessageBox.warning(self, "Save Error", "No GeoPackage found to save.\nPlease run a prediction first.")
            return

        try:
            base_name = os.path.basename(current_gpkg)
            save_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Save Result GeoPackage", 
                os.path.join(os.path.dirname(current_gpkg), base_name), 
                "GeoPackage (*.gpkg)"
            )
            if not save_path: return
            if not save_path.lower().endswith('.gpkg'): save_path += '.gpkg'
            if os.path.abspath(current_gpkg) == os.path.abspath(save_path):
                QMessageBox.information(self, "Save", "Destination is the same as current file.")
                return

            shutil.copy2(current_gpkg, save_path)
            QMessageBox.information(self, "Success", f"File successfully saved to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")