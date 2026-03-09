# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'mlprep_plugin_Objective_2.ui'
# Manual corrections applied for 2x2 Map Grid and Removed Dropdown

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1200, 850) # Widened slightly to accommodate the 2x2 grid better
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        
        # ==========================================
        # LEFT COLUMN: 2x2 MAP AREA
        # ==========================================
        self.Widget_Map_Area = QtWidgets.QWidget(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(3) # Increased stretch so maps get more room
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.Widget_Map_Area.sizePolicy().hasHeightForWidth())
        self.Widget_Map_Area.setSizePolicy(sizePolicy)
        self.Widget_Map_Area.setMinimumSize(QtCore.QSize(0, 0))
        self.Widget_Map_Area.setStyleSheet("QWidget {\n"
"    background-color:#ffffff;\n"
"}\n"
"\n"
"QGroupBox {\n"
"    font: 600 12px \"Arial\";\n"
"    color: #E0E0E0;\n"
"    border: 2px solid #555;\n"
"    border-radius: 10px;\n"
"    margin-top: 16px;\n"
"    background-color: transparent;\n"
"    padding: 12px;\n"
"    font-weight: 10;\n"
"}\n"
"\n"
"QGroupBox::title {\n"
"    subcontrol-origin: margin;\n"
"    subcontrol-position: top center;\n"
"    padding: 0 8px;\n"
"    background-color: #ffffff;    /* same as box background */\n"
"    color: black;\n"
"\n"
"    position:absolute;\n"
"    margin-top:10px\n"
"}")
        self.Widget_Map_Area.setObjectName("Widget_Map_Area")
        
        # 2x2 Grid Layout for Maps
        self.gridLayout = QtWidgets.QGridLayout(self.Widget_Map_Area)
        self.gridLayout.setObjectName("gridLayout")
        
        # Top-Left: Input GPKG
        self.GroupBox_Input_GPKG = QtWidgets.QGroupBox(self.Widget_Map_Area)
        self.GroupBox_Input_GPKG.setObjectName("GroupBox_Input_GPKG")
        self.layout_input = QtWidgets.QHBoxLayout(self.GroupBox_Input_GPKG)
        self.layout_input.setObjectName("layout_input")
        self.GraphicsView_Input_GPKG = QtWidgets.QGraphicsView(self.GroupBox_Input_GPKG)
        self.GraphicsView_Input_GPKG.setObjectName("GraphicsView_Input_GPKG")
        self.layout_input.addWidget(self.GraphicsView_Input_GPKG)
        self.gridLayout.addWidget(self.GroupBox_Input_GPKG, 0, 0, 1, 1)

        # Top-Right: Hazard Map
        self.GroupBox_Hazard_Map = QtWidgets.QGroupBox(self.Widget_Map_Area)
        self.GroupBox_Hazard_Map.setObjectName("GroupBox_Hazard_Map")
        self.layout_haz = QtWidgets.QHBoxLayout(self.GroupBox_Hazard_Map)
        self.layout_haz.setObjectName("layout_haz")
        self.GraphicsView_Hazard_Map = QtWidgets.QGraphicsView(self.GroupBox_Hazard_Map)
        self.GraphicsView_Hazard_Map.setObjectName("GraphicsView_Hazard_Map")
        self.layout_haz.addWidget(self.GraphicsView_Hazard_Map)
        self.gridLayout.addWidget(self.GroupBox_Hazard_Map, 0, 1, 1, 1)

        # Bottom-Left: Cohesion Map
        self.GroupBox_Cohesion_Map = QtWidgets.QGroupBox(self.Widget_Map_Area)
        self.GroupBox_Cohesion_Map.setObjectName("GroupBox_Cohesion_Map")
        self.layout_coh = QtWidgets.QHBoxLayout(self.GroupBox_Cohesion_Map)
        self.layout_coh.setObjectName("layout_coh")
        self.GraphicsView_Cohesion_Map = QtWidgets.QGraphicsView(self.GroupBox_Cohesion_Map)
        self.GraphicsView_Cohesion_Map.setObjectName("GraphicsView_Cohesion_Map")
        self.layout_coh.addWidget(self.GraphicsView_Cohesion_Map)
        self.gridLayout.addWidget(self.GroupBox_Cohesion_Map, 1, 0, 1, 1)

        # Bottom-Right: Internal Friction Map
        self.GroupBox_Friction_Map = QtWidgets.QGroupBox(self.Widget_Map_Area)
        self.GroupBox_Friction_Map.setObjectName("GroupBox_Friction_Map")
        self.layout_fric = QtWidgets.QHBoxLayout(self.GroupBox_Friction_Map)
        self.layout_fric.setObjectName("layout_fric")
        self.GraphicsView_Friction_Map = QtWidgets.QGraphicsView(self.GroupBox_Friction_Map)
        self.GraphicsView_Friction_Map.setObjectName("GraphicsView_Friction_Map")
        self.layout_fric.addWidget(self.GraphicsView_Friction_Map)
        self.gridLayout.addWidget(self.GroupBox_Friction_Map, 1, 1, 1, 1)

        self.horizontalLayout.addWidget(self.Widget_Map_Area)

        # ==========================================
        # RIGHT COLUMN: INPUTS AREA
        # ==========================================
        self.GridLayout_Inputs_Area = QtWidgets.QGridLayout()
        self.GridLayout_Inputs_Area.setObjectName("GridLayout_Inputs_Area")
        self.scrollArea = QtWidgets.QScrollArea(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.scrollArea.sizePolicy().hasHeightForWidth())
        self.scrollArea.setSizePolicy(sizePolicy)
        self.scrollArea.setStyleSheet("background-color:#D7D5D2;")
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 350, 850))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.Widget_Inputs = QtWidgets.QWidget(self.scrollAreaWidgetContents)
        self.Widget_Inputs.setStyleSheet("QGroupBox {\n"
"    font: 600 12px \"Arial\";\n"
"    color: #E0E0E0;\n"
"    border: 2px solid #555;\n"
"    border-radius: 10px;\n"
"    margin-top: 16px;\n"
"    background-color: transparent;\n"
"    padding: 12px;\n"
"    font-weight: 10;\n"
"}\n"
"\n"
"QGroupBox::title {\n"
"    subcontrol-origin: margin;\n"
"    subcontrol-position: top center;\n"
"    padding: 0 8px;\n"
"    background-color: #D7D5D2;    /* same as box background */\n"
"    color: black;\n"
"\n"
"    position:absolute;\n"
"    margin-top:10px\n"
"}\n"
"\n"
"QLabel {\n"
"    color: black;\n"
"}\n"
"\n"
"QDateEdit {\n"
"    border: 1px solid #555;\n"
"    border-radius: 6px;\n"
"    background-color: #ffffff;\n"
"    color:black;\n"
"    height:25;\n"
"}")
        self.Widget_Inputs.setObjectName("Widget_Inputs")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.Widget_Inputs)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        
        # Title Label
        self.Lable_EIL_Hazard_Map = QtWidgets.QLabel(self.Widget_Inputs)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.Lable_EIL_Hazard_Map.sizePolicy().hasHeightForWidth())
        self.Lable_EIL_Hazard_Map.setSizePolicy(sizePolicy)
        self.Lable_EIL_Hazard_Map.setMinimumSize(QtCore.QSize(250, 35))
        self.Lable_EIL_Hazard_Map.setMaximumSize(QtCore.QSize(16777215, 35))
        self.Lable_EIL_Hazard_Map.setStyleSheet("QLabel {\n"
"    color: black;\n"
"    font: 700 16pt \"Arial\";\n"
"}")
        self.Lable_EIL_Hazard_Map.setScaledContents(False)
        self.Lable_EIL_Hazard_Map.setAlignment(QtCore.Qt.AlignCenter)
        self.Lable_EIL_Hazard_Map.setObjectName("Lable_EIL_Hazard_Map")
        self.verticalLayout_4.addWidget(self.Lable_EIL_Hazard_Map)
        
        # File Inputs
        self.GroupBox_File_Inputs = QtWidgets.QGroupBox(self.Widget_Inputs)
        self.GroupBox_File_Inputs.setStyleSheet("")
        self.GroupBox_File_Inputs.setObjectName("GroupBox_File_Inputs")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.GroupBox_File_Inputs)
        self.gridLayout_2.setVerticalSpacing(0)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.Widget_GPKG = QtWidgets.QWidget(self.GroupBox_File_Inputs)
        self.Widget_GPKG.setStyleSheet("/* ======= File row: Browse button (left pill) ======= */\n"
"QWidget {\n"
"    border: none;\n"
"}\n"
"\n"
"QPushButton#PushButton_GPKG {\n"
"    font:montserrat;\n"
"    border: 1px solid #3a3a3a;\n"
"    border-top-left-radius: 6px;\n"
"    border-bottom-left-radius: 6px;\n"
"    border-top-right-radius: 0px;\n"
"    border-bottom-right-radius: 0px;\n"
"    background: #ffffff;\n"
"    color:black;\n"
"    padding: 6px 14px;\n"
"    font-weight: 10;\n"
"    font-size: 10px;\n"
"    min-height: 10;\n"
"    min-width: 55;\n"
"}\n"
"\n"
"/* ======= File row: Path field (right pill) ======= */\n"
"\n"
"QPlainTextEdit#PTE_GPKG {\n"
"    border: 1px solid #3a3a3a;\n"
"    border-left: 0;                     /* fuse with the button */\n"
"    border-top-right-radius: 6px;\n"
"    border-bottom-right-radius: 6px;\n"
"    border-top-left-radius: 0;\n"
"    border-bottom-left-radius: 0;\n"
"    background: #D5D5D5;\n"
"    padding: 0px 0px;\n"
"    min-height: 10;\n"
"    font-size: 10px;\n"
"    font-weight:10;\n"
"    color:black;\n"
"}\n"
"\n"
"QPushButton#PushButton_GPKG:hover { background: #f4f4f4; }\n"
"QPushButton#PushButton_GPKG:pressed { background: #eaeaea; }\n"
"QPushButton#PushButton_GPKG:disabled { color: #9b9b9b; background: #f6f6f6; }\n"
"\n"
"/* Optional: make text white in dark UIs */\n"
"QLabel { color: #black; }\n"
"QGroupBox { color: #202020; }\n"
"")
        self.Widget_GPKG.setObjectName("Widget_GPKG")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout(self.Widget_GPKG)
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.PushButton_GPKG = QtWidgets.QPushButton(self.Widget_GPKG)
        self.PushButton_GPKG.setObjectName("PushButton_GPKG")
        self.horizontalLayout_4.addWidget(self.PushButton_GPKG)
        self.PTE_GPKG = QtWidgets.QPlainTextEdit(self.Widget_GPKG)
        self.PTE_GPKG.setMaximumSize(QtCore.QSize(16777215, 25))
        self.PTE_GPKG.setPlainText("")
        self.PTE_GPKG.setObjectName("PTE_GPKG")
        self.horizontalLayout_4.addWidget(self.PTE_GPKG)
        self.gridLayout_2.addWidget(self.Widget_GPKG, 0, 1, 1, 1)
        self.Label_GPKG = QtWidgets.QLabel(self.GroupBox_File_Inputs)
        self.Label_GPKG.setMaximumSize(QtCore.QSize(16777215, 30))
        self.Label_GPKG.setObjectName("Label_GPKG")
        self.gridLayout_2.addWidget(self.Label_GPKG, 0, 0, 1, 1)
        self.verticalLayout_4.addWidget(self.GroupBox_File_Inputs)
        
        # --- STATISTICS SECTION ---
        self.GroupBox_Legend = QtWidgets.QGroupBox(self.Widget_Inputs)
        self.GroupBox_Legend.setObjectName("GroupBox_Legend")
        self.verticalLayout_Stats = QtWidgets.QVBoxLayout(self.GroupBox_Legend)
        self.verticalLayout_Stats.setObjectName("verticalLayout_Stats")

        # 1. Hazard Map Stats
        self.GroupBox_Stats_Hazard = QtWidgets.QGroupBox(self.GroupBox_Legend)
        self.GroupBox_Stats_Hazard.setObjectName("GroupBox_Stats_Hazard")
        self.layout_haz_table = QtWidgets.QVBoxLayout(self.GroupBox_Stats_Hazard)
        self.Table_Hazard = QtWidgets.QTableWidget(self.GroupBox_Stats_Hazard)
        self.Table_Hazard.setColumnCount(3)
        self.Table_Hazard.setHorizontalHeaderLabels(["Class", "Range", "Color"])
        self.Table_Hazard.horizontalHeader().setStretchLastSection(True)
        self.Table_Hazard.verticalHeader().setVisible(False)
        self.Table_Hazard.setMinimumHeight(120)
        self.Table_Hazard.setStyleSheet("background-color: white; color: black;")
        self.layout_haz_table.addWidget(self.Table_Hazard)
        self.verticalLayout_Stats.addWidget(self.GroupBox_Stats_Hazard)

        # 2. Cohesion Stats
        self.GroupBox_Stats_Cohesion = QtWidgets.QGroupBox(self.GroupBox_Legend)
        self.GroupBox_Stats_Cohesion.setObjectName("GroupBox_Stats_Cohesion")
        self.layout_coh_table = QtWidgets.QVBoxLayout(self.GroupBox_Stats_Cohesion)
        self.Table_Cohesion = QtWidgets.QTableWidget(self.GroupBox_Stats_Cohesion)
        self.Table_Cohesion.setColumnCount(3)
        self.Table_Cohesion.setHorizontalHeaderLabels(["Class", "Range", "Color"])
        self.Table_Cohesion.horizontalHeader().setStretchLastSection(True)
        self.Table_Cohesion.verticalHeader().setVisible(False)
        self.Table_Cohesion.setMinimumHeight(120)
        self.Table_Cohesion.setStyleSheet("background-color: white; color: black;")
        self.layout_coh_table.addWidget(self.Table_Cohesion)
        self.verticalLayout_Stats.addWidget(self.GroupBox_Stats_Cohesion)

        # 3. Friction Stats
        self.GroupBox_Stats_Friction = QtWidgets.QGroupBox(self.GroupBox_Legend)
        self.GroupBox_Stats_Friction.setObjectName("GroupBox_Stats_Friction")
        self.layout_fric_table = QtWidgets.QVBoxLayout(self.GroupBox_Stats_Friction)
        self.Table_Friction = QtWidgets.QTableWidget(self.GroupBox_Stats_Friction)
        self.Table_Friction.setColumnCount(3)
        self.Table_Friction.setHorizontalHeaderLabels(["Class", "Range", "Color"])
        self.Table_Friction.horizontalHeader().setStretchLastSection(True)
        self.Table_Friction.verticalHeader().setVisible(False)
        self.Table_Friction.setMinimumHeight(120)
        self.Table_Friction.setStyleSheet("background-color: white; color: black;")
        self.layout_fric_table.addWidget(self.Table_Friction)
        self.verticalLayout_Stats.addWidget(self.GroupBox_Stats_Friction)

        self.verticalLayout_4.addWidget(self.GroupBox_Legend)

        # --- FOOTER BUTTONS ---
        self.Widget_Footer_Buttons = QtWidgets.QWidget(self.Widget_Inputs)
        self.Widget_Footer_Buttons.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.Widget_Footer_Buttons.setStyleSheet("QPushButton {\n"
"    font: montserrat;\n"
"    border: 1px solid #3a3a3a;\n"
"    border-top-left-radius: 6px;\n"
"    border-bottom-left-radius: 6px;\n"
"    border-top-right-radius: 6px;\n"
"    border-bottom-right-radius: 6px;\n"
"    background: #ffffff;\n"
"    color:black;\n"
"    padding: 6px 14px;\n"
"    font-weight: 10;\n"
"    font-size: 10px;\n"
"    min-height: 10;\n"
"    min-width: 55;\n"
"    \n"
"}\n"
"\n"
"QPushButton:hover { background: #f4f4f4; }\n"
"QPushButton:pressed { background: #eaeaea; }\n"
"QPushButton:disabled { color: #9b9b9b; background: #f6f6f6; }")
        self.Widget_Footer_Buttons.setObjectName("Widget_Footer_Buttons")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout(self.Widget_Footer_Buttons)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.Button_Save = QtWidgets.QPushButton(self.Widget_Footer_Buttons)
        self.Button_Save.setObjectName("Button_Save")
        self.horizontalLayout_3.addWidget(self.Button_Save)
        self.Button_Detect = QtWidgets.QPushButton(self.Widget_Footer_Buttons)
        self.Button_Detect.setObjectName("Button_Detect")
        self.horizontalLayout_3.addWidget(self.Button_Detect)
        self.verticalLayout_4.addWidget(self.Widget_Footer_Buttons)
        
        self.verticalLayout_5.addWidget(self.Widget_Inputs)
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.GridLayout_Inputs_Area.addWidget(self.scrollArea, 0, 0, 1, 1)
        self.horizontalLayout.addLayout(self.GridLayout_Inputs_Area)
        
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1200, 37))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuEdit = QtWidgets.QMenu(self.menubar)
        self.menuEdit.setObjectName("menuEdit")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionNew = QtWidgets.QAction(MainWindow)
        self.actionNew.setObjectName("actionNew")
        self.actionSave = QtWidgets.QAction(MainWindow)
        self.actionSave.setObjectName("actionSave")
        self.actionCopy = QtWidgets.QAction(MainWindow)
        self.actionCopy.setObjectName("actionCopy")
        self.actionPaste = QtWidgets.QAction(MainWindow)
        self.actionPaste.setObjectName("actionPaste")
        self.menuFile.addAction(self.actionNew)
        self.menuFile.addAction(self.actionSave)
        self.menuEdit.addAction(self.actionCopy)
        self.menuEdit.addAction(self.actionPaste)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        
        # Grid Titles
        self.GroupBox_Input_GPKG.setTitle(_translate("MainWindow", "INPUT GPKG"))
        self.GroupBox_Hazard_Map.setTitle(_translate("MainWindow", "HAZARD MAP"))
        self.GroupBox_Cohesion_Map.setTitle(_translate("MainWindow", "COHESION MAP"))
        self.GroupBox_Friction_Map.setTitle(_translate("MainWindow", "INTERNAL FRICTION MAP"))
        
        # Inputs Panel
        self.Lable_EIL_Hazard_Map.setText(_translate("MainWindow", "Earthquake-Induced Landslide Hazard Map"))
        self.GroupBox_File_Inputs.setTitle(_translate("MainWindow", "File Inputs"))
        self.PushButton_GPKG.setText(_translate("MainWindow", "Choose File"))
        self.Label_GPKG.setText(_translate("MainWindow", "GPKG:"))
        
        # Legend/Stats Panel
        self.GroupBox_Legend.setTitle(_translate("MainWindow", "Model Statistics (Natural Breaks)"))
        self.GroupBox_Stats_Hazard.setTitle(_translate("MainWindow", "Hazard Map Classification"))
        self.GroupBox_Stats_Cohesion.setTitle(_translate("MainWindow", "Cohesion Classification"))
        self.GroupBox_Stats_Friction.setTitle(_translate("MainWindow", "Internal Friction Classification"))
        
        # Footer
        self.Button_Save.setText(_translate("MainWindow", "SAVE"))
        self.Button_Detect.setText(_translate("MainWindow", "PREDICT"))
        
        # Menus
        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.menuEdit.setTitle(_translate("MainWindow", "Edit"))
        self.actionNew.setText(_translate("MainWindow", "New"))
        self.actionSave.setText(_translate("MainWindow", "Save"))
        self.actionCopy.setText(_translate("MainWindow", "Copy"))
        self.actionPaste.setText(_translate("MainWindow", "Paste"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())