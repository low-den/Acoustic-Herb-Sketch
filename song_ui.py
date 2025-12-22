from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
                             QPushButton, QLabel, QLineEdit, QComboBox, QFrame,
                             QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt

class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()

class SessionBoxWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.NoFrame) # Removed border
        self.setFixedWidth(130) # Increased width slightly (was 120, +5 margin on both sides ~ 130)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Instrument Button
        self.btn_inst = QPushButton("악기 선택")
        layout.addWidget(self.btn_inst)
        
        # Difficulty Row (Label + Combo)
        diff_layout = QHBoxLayout()
        self.lbl_difficulty = QLabel("난이도")
        self.combo_difficulty = NoScrollComboBox() 
        diff_layout.addWidget(self.lbl_difficulty)
        diff_layout.addWidget(self.combo_difficulty)
        layout.addLayout(diff_layout)
        
        # Remove Button (Bottom Center)
        layout.addStretch()
        self.btn_remove = QPushButton("X")
        self.btn_remove.setFixedSize(30, 20)
        
        # Center the remove button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

class SongBoxWidget(QFrame):
    def __init__(self):
        super().__init__()
        # self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Thicker border for better visibility
        self.setStyleSheet("""
            SongBoxWidget {
                border: 2px solid #8f8f91;
                border-radius: 5px;
                background-color: #ffffff;
                margin-bottom: 5px;
            }
        """)
        
        self.main_layout = QHBoxLayout(self)
        
        # Left Controls (Move Up/Down)
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        self.btn_up = QPushButton("▲")
        self.btn_up.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        
        self.btn_down = QPushButton("▼")
        self.btn_down.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        
        left_layout.addWidget(self.btn_up)
        left_layout.addWidget(self.btn_down)
        
        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_container.setFixedWidth(30)
        
        self.main_layout.addWidget(left_container)
        
        # Content
        content_layout = QVBoxLayout()
        
        # Header (Info)
        header_layout = QHBoxLayout()
        
        self.lbl_number = QLabel("No.1")
        self.lbl_number.setStyleSheet("color: blue; font-weight: bold;")
        header_layout.addWidget(self.lbl_number)
        
        self.edit_name = QLineEdit("새 곡")
        
        # Set bold and larger font for edit_name
        font = self.edit_name.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.edit_name.setFont(font)
        self.edit_name.setStyleSheet("background-color: #D6E4ED;")
        
        self.edit_nickname = QLineEdit() # Nickname field
        self.edit_nickname.setPlaceholderText("별명")
        self.edit_nickname.setFixedWidth(80)
        self.edit_bpm = QLineEdit("100")
        self.edit_bpm.setFixedWidth(50)
        self.combo_category = NoScrollComboBox()
        self.combo_category.addItems(["기악곡", "보컬곡"])
        self.edit_ref = QLineEdit()
        self.edit_ref.setPlaceholderText("URL")
        
        self.btn_delete = QPushButton("X")
        self.btn_delete.setFixedSize(30, 30)
        
        # Helper for bold labels
        def bold_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-weight: bold;")
            return lbl
        
        header_layout.addWidget(bold_label("곡 이름:"))
        header_layout.addWidget(self.edit_name)
        header_layout.addWidget(self.edit_nickname) # Add nickname widget
        header_layout.addWidget(bold_label("BPM(♩):"))
        header_layout.addWidget(self.edit_bpm)
        header_layout.addWidget(bold_label("분류:"))
        header_layout.addWidget(self.combo_category)
        header_layout.addWidget(bold_label("참고영상:"))
        header_layout.addWidget(self.edit_ref)
        header_layout.addWidget(self.btn_delete)
        
        content_layout.addLayout(header_layout)
        
        # Sessions Area
        self.sessions_scroll = QScrollArea()
        self.sessions_scroll.setWidgetResizable(True)
        self.sessions_scroll.setFixedHeight(100)
        self.sessions_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.sessions_container = QWidget()
        self.sessions_layout = QHBoxLayout(self.sessions_container)
        self.sessions_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.sessions_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_add_session = QPushButton("+")
        self.btn_add_session.setFixedSize(40, 70)
        self.sessions_layout.addWidget(self.btn_add_session)
        
        self.sessions_scroll.setWidget(self.sessions_container)
        content_layout.addWidget(self.sessions_scroll)
        
        self.main_layout.addLayout(content_layout)

class SongWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Top Add Button
        self.btn_add_song = QPushButton("곡 추가")
        self.btn_add_song.setFixedHeight(40)
        self.btn_add_song.setStyleSheet("""
            QPushButton {
                background-color: #C8FFC8; 
                color: black;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #7CCD7C;
            }
        """)
        layout.addWidget(self.btn_add_song)
        
        # Scroll Area for Songs
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.songs_container = QWidget()
        self.songs_layout = QVBoxLayout(self.songs_container)
        self.songs_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.songs_container)
        layout.addWidget(self.scroll_area)
        
        # Footer
        self.btn_reset = QPushButton("공연 초기화")
        self.btn_reset.setStyleSheet("background-color: #ffaaaa; color: white;")
        layout.addWidget(self.btn_reset)
