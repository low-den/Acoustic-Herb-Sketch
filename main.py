import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QTabWidget, QToolBar, QSizePolicy, QLabel, QMessageBox,
                             QFileDialog, QMenu, QGraphicsOpacityEffect, QStackedWidget)
from PyQt6.QtGui import QUndoStack, QAction, QPixmap, QIcon
from PyQt6.QtCore import Qt

from data_handler import DataHandler
from profile_ui import ProfileWidget
from profile_service import ProfileService
from profile_controller import ProfileController
from song_ui import SongWidget
from song_service import SongService
from song_controller import SongController
from session_ui import SessionWidget
from session_service import SessionService
from session_controller import SessionController
from tech_ui import TechWidget
from tech_service import TechService
from tech_controller import TechController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Acoustic Herb Sketch")
        self.resize(1280, 720)
        
        # Set App Icon
        icon_path = self.get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Core Components
        self.data_handler = DataHandler()
        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self.update_window_title)
        
        # Services
        self.profile_service = ProfileService(self.data_handler, self.undo_stack)
        self.song_service = SongService(self.data_handler, self.undo_stack)
        self.session_service = SessionService(self.data_handler, self.undo_stack)
        self.tech_service = TechService(self.data_handler, self.undo_stack)
        
        # UI Setup
        self.init_ui()
        
        # Controllers
        self.profile_controller = ProfileController(self.profile_tab, self.profile_service)
        self.song_controller = SongController(self.song_tab, self.song_service)
        self.session_controller = SessionController(self.session_tab, self.session_service)
        self.tech_controller = TechController(self.tech_tab, self.tech_service, self.song_service)
        
        # Connect Signals for Cross-Module Updates
        self.profile_service.data_changed.connect(self.session_controller.refresh_data)
        self.song_service.data_changed.connect(self.session_controller.refresh_data)
        
        # Initial State
        self.set_project_loaded(False)
        
    def get_resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.dirname(os.path.abspath(__file__))

        return os.path.join(base_path, relative_path)
        
    def init_ui(self):
        # Toolbar (Top Menu)
        self.create_toolbar()
        
        # Central Widget & Tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # 1. Welcome Widget
        self.welcome_widget = self.create_welcome_widget()
        self.stack.addWidget(self.welcome_widget)
        
        # 2. Tabs
        self.tabs = QTabWidget()
        self.stack.addWidget(self.tabs)
        
        # Add Tabs
        self.profile_tab = ProfileWidget()
        self.song_tab = SongWidget()
        self.session_tab = SessionWidget()
        self.tech_tab = TechWidget()
        
        self.tabs.addTab(self.profile_tab, "부원 프로필")
        self.tabs.addTab(self.song_tab, "공연 곡 편집")
        self.tabs.addTab(self.session_tab, "세션 배분")
        self.tabs.addTab(self.tech_tab, "테크라이더")
        
        # Apply bold font to tab bar
        self.tabs.setStyleSheet("QTabBar::tab { font-weight: bold; }")

    def create_welcome_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo
        logo_path = self.get_resource_path("logo.png")
        
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(pixmap)
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                opacity_effect = QGraphicsOpacityEffect()
                opacity_effect.setOpacity(0.3)
                logo_label.setGraphicsEffect(opacity_effect)
                
                layout.addWidget(logo_label)
        
        text_label = QLabel("새 프로젝트 또는 열기를 선택해주세요")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet("font-size: 24px; color: gray; margin-top: 20px;")
        layout.addWidget(text_label)
        
        return widget
        
    def create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Left Actions
        # New Project
        new_act = toolbar.addAction("새 프로젝트")
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.new_file)
        
        # Open Recent (with Menu)
        self.recent_act = toolbar.addAction("최근 파일 열기")
        self.recent_act.setShortcut("Ctrl+Shift+O")
        self.recent_menu = QMenu(self)
        self.recent_act.setMenu(self.recent_menu)
        # Need to set popup mode if we want the button itself to open menu immediately?
        # QToolButton usually handles this if action has menu.
        # However, for QAction in Toolbar, it creates a toolbutton.
        # We need to configure the widget to show menu instantly or use setPopupMode.
        # But standard way is addAction. 
        # Let's update the menu content dynamically before showing.
        self.recent_menu.aboutToShow.connect(self.update_recent_menu)
        
        # Open
        open_act = toolbar.addAction("열기")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_file)
        
        # Save
        self.save_act = toolbar.addAction("저장")
        self.save_act.setShortcut("Ctrl+S")
        self.save_act.triggered.connect(self.save_file)
        
        # Save As
        save_as_act = toolbar.addAction("다른 이름 저장")
        save_as_act.setShortcut("Ctrl+Shift+S")
        save_as_act.triggered.connect(self.save_file_as)
        
        # Spacer
        empty = QWidget()
        empty.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(empty)
        
        # Right Actions (Undo/Redo)
        self.undo_action = QAction("되돌리기", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_stack.undo)
        self.undo_action.setEnabled(False)
        self.undo_stack.canUndoChanged.connect(self.undo_action.setEnabled)

        self.redo_action = QAction("다시 실행", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.undo_stack.redo)
        self.redo_action.setEnabled(False)
        self.undo_stack.canRedoChanged.connect(self.redo_action.setEnabled)
        
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)

        # Configure Recent Button to show menu
        widget = toolbar.widgetForAction(self.recent_act)
        if widget:
            widget.setPopupMode(widget.ToolButtonPopupMode.InstantPopup)

    def update_recent_menu(self):
        self.recent_menu.clear()
        files = self.data_handler.recent_files
        if not files:
            action = self.recent_menu.addAction("최근 파일 없음")
            action.setEnabled(False)
        else:
            for f in files:
                name = os.path.basename(f)
                action = self.recent_menu.addAction(name)
                action.triggered.connect(lambda checked, path=f: self.load_recent_file(path))

    def update_window_title(self, is_clean):
        if not self.data_handler.filepath:
            self.setWindowTitle("Acoustic Herb Sketch")
            return
            
        title = f"Acoustic Herb Sketch - {self.data_handler.filepath}"
        if not is_clean:
            title += "*"
        self.setWindowTitle(title)

    def set_project_loaded(self, loaded: bool):
        self.save_act.setEnabled(loaded)
        # self.undo_action.setEnabled(loaded) # Managed by undo_stack
        # self.redo_action.setEnabled(loaded) # Managed by undo_stack
        
        if loaded:
            self.stack.setCurrentWidget(self.tabs)
        else:
            self.stack.setCurrentWidget(self.welcome_widget)
                
        # Update Window Title
        if loaded and self.data_handler.filepath:
            self.update_window_title(self.undo_stack.isClean())
        else:
            self.setWindowTitle("Acoustic Herb Sketch")

    def new_file(self):
        if not self.check_unsaved_changes(): return

        filename, _ = QFileDialog.getSaveFileName(self, "새 프로젝트 저장", "", "Acoustic Files (*.acou)")
        if filename:
            try:
                self.data_handler.create_new_project(filename)
                self.reload_all_controllers()
                self.set_project_loaded(True)
                self.undo_stack.clear()
                self.undo_stack.setClean()
            except Exception as e:
                QMessageBox.critical(self, "오류", f"프로젝트 생성 실패: {str(e)}")

    def open_file(self):
        if not self.check_unsaved_changes(): return
        
        filename, _ = QFileDialog.getOpenFileName(self, "프로젝트 열기", "", "Acoustic Files (*.acou)")
        if filename:
            self.load_project(filename)

    def load_recent_file(self, filepath):
        if not self.check_unsaved_changes(): return
        
        if os.path.exists(filepath):
            self.load_project(filepath)
        else:
            QMessageBox.warning(self, "오류", "파일을 찾을 수 없습니다.")
            # Optionally remove from recent list?
            if filepath in self.data_handler.recent_files:
                self.data_handler.recent_files.remove(filepath)
                self.data_handler.save_recent_files_list()

    def load_project(self, filepath):
        try:
            self.data_handler.load_data(filepath)
            self.reload_all_controllers()
            self.set_project_loaded(True)
            self.undo_stack.clear()
            self.undo_stack.setClean()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 불러오기 실패: {str(e)}")

    def save_file(self):
        if not self.data_handler.filepath:
            self.save_file_as()
            return
            
        try:
            self.data_handler.save_data()
            self.undo_stack.setClean()
            self.update_window_title(True)
            QMessageBox.information(self, "저장", "저장되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {str(e)}")

    def save_file_as(self):
        filename, _ = QFileDialog.getSaveFileName(self, "다른 이름으로 저장", "", "Acoustic Files (*.acou)")
        if filename:
            try:
                self.data_handler.save_data(filename)
                self.undo_stack.setClean()
                self.set_project_loaded(True) # Update title
                QMessageBox.information(self, "저장", f"저장되었습니다: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 실패: {str(e)}")

    def closeEvent(self, event):
        if self.check_unsaved_changes():
            event.accept()
        else:
            event.ignore()

    def check_unsaved_changes(self):
        if not self.undo_stack.isClean():
            reply = QMessageBox.question(self, "저장되지 않은 변경사항", 
                                         "변경사항이 저장되지 않았습니다.\n저장하시겠습니까?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            
            if reply == QMessageBox.StandardButton.Save:
                self.save_file()
                return self.undo_stack.isClean()
            elif reply == QMessageBox.StandardButton.Discard:
                return True
            else: # Cancel
                return False
        return True

    def reload_all_controllers(self):
        # Refresh UI for all tabs based on loaded data
        self.profile_controller.refresh_ui()
        self.song_controller.refresh_ui()
        self.session_controller.refresh_data()
        self.tech_controller.refresh_ui()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
