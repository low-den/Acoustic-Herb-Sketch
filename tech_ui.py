from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
                             QCheckBox, QGroupBox, QScrollArea, QRadioButton, QButtonGroup,
                             QTextEdit, QTreeWidget, QTreeWidgetItem, QFrame, QSplitter, QListWidget, QAbstractItemView)
from PyQt6.QtCore import Qt

class SoundDesignRow(QWidget):
    def __init__(self, label_text, options, exclusive=True):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel(label_text))
        
        self.group = QButtonGroup(self)
        self.group.setExclusive(exclusive)
        
        for i, opt_text in enumerate(options):
            if exclusive:
                btn = QRadioButton(opt_text)
            else:
                btn = QCheckBox(opt_text)
            self.group.addButton(btn, i)
            layout.addWidget(btn)
            
        layout.addStretch()

class TechWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # Splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Panel: Sound Design & Cue Sheet ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        
        # 1. Sound Design Section
        design_group = QGroupBox("음향 설계")
        design_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        design_inner = QVBoxLayout()
        
        # Hardcoded rows as per PDF
        # 일렉기타 1 TS 케이블 [ ] 3개 [ ] 2개 [ ] 1개
        self.eg1_row = SoundDesignRow("일렉기타 1 TS 케이블", ["3개", "2개", "1개"])
        design_inner.addWidget(self.eg1_row)
        
        # 일렉기타 2 TS 케이블 [ ] 3개 [ ] 2개 [ ] 1개
        self.eg2_row = SoundDesignRow("일렉기타 2 TS 케이블", ["3개", "2개", "1개"])
        design_inner.addWidget(self.eg2_row)
        
        # 피아노/신디 1 [ ] 패시브 DI [ ] 액티브 DI
        self.piano1_row = SoundDesignRow("피아노/신디 1", ["패시브 DI", "액티브 DI"])
        design_inner.addWidget(self.piano1_row)
        
        # 피아노/신디 2 [ ] 패시브 DI [ ] 액티브 DI
        self.piano2_row = SoundDesignRow("피아노/신디 2", ["패시브 DI", "액티브 DI"])
        design_inner.addWidget(self.piano2_row)
        
        design_group.setLayout(design_inner)
        left_layout.addWidget(design_group)
        
        # --- Right Panel (Moved to Left Bottom): Equipment List ---
        # Moving Equipment List here (below Sound Design)
        
        # Equipment List Group
        # To match the structure of "groupbox" style for sound design, let's wrap it in a groupbox or just add the widgets.
        # Original right panel had: Label "## 장비 계산", Table, Buttons.
        # Let's wrap in a GroupBox for consistency or just add them.
        # The prompt says: "right_layout(장비계산 위젯)를 design_group 아래로 보내고"
        
        # Let's reuse the widgets created for equipment list
        self.lbl_eq = QLabel("장비 계산")
        self.lbl_eq.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(self.lbl_eq)
        
        # Add guidance label
        self.lbl_guidance = QLabel("* 마이크 스탠드는\n허큘레스, 반도, K&M, GRAVITY 브랜드만 계수해 주세요.")
        left_layout.addWidget(self.lbl_guidance)
        
        self.eq_table = QTableWidget()
        self.eq_table.setColumnCount(3)
        self.eq_table.setHorizontalHeaderLabels(["장비명", "보유", "필요"])
        self.eq_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.eq_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.eq_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.eq_table.setColumnWidth(1, 60)
        self.eq_table.setColumnWidth(2, 60)
        
        # Set selection behavior to SelectRows for easier deletion
        self.eq_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.eq_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        left_layout.addWidget(self.eq_table)
        
        btn_eq_layout = QHBoxLayout()
        self.btn_eq_add = QPushButton("추가")
        self.btn_eq_del = QPushButton("삭제")
        self.btn_eq_auto = QPushButton("자동계산")
        
        btn_eq_layout.addWidget(self.btn_eq_add)
        btn_eq_layout.addWidget(self.btn_eq_del)
        btn_eq_layout.addWidget(self.btn_eq_auto)
        left_layout.addLayout(btn_eq_layout)
        
        splitter.addWidget(left_container)
        
        # --- Right Panel (New Home for Cue Sheet) ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        
        # 2. Cue Sheet Section (Moved from Left)
        cue_group = QGroupBox("큐시트")
        cue_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        cue_inner = QVBoxLayout()
        
        # Song List
        lbl_song = QLabel("곡 목록")
        lbl_song.setStyleSheet("font-weight: bold;")
        cue_inner.addWidget(lbl_song)
        self.song_list = QListWidget() # Added song list
        cue_inner.addWidget(self.song_list, 1)
        
        # Section List (Table Structure)
        self.cue_table = QTableWidget()
        self.cue_table.setColumnCount(4)
        self.cue_table.setHorizontalHeaderLabels(["섹션", "세션", "이펙트", "메모"])
        
        # Column resizing
        header = self.cue_table.horizontalHeader()
        
        # Set initial widths to approximate 2:1:2:5 ratio
        self.cue_table.setColumnWidth(0, 100) # 2
        self.cue_table.setColumnWidth(1, 150)  # 1
        self.cue_table.setColumnWidth(2, 150) # 2
        
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive) # Section name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive) # Instrument
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive) # Effect
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)     # Memo (5, Fills remaining)
        
        self.cue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cue_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.cue_table.setWordWrap(True) # Enable word wrap for memo
        self.cue_table.verticalHeader().setVisible(False)
        
        cue_inner.addWidget(self.cue_table, 2)
        
        # Control Buttons
        cue_btn_layout = QHBoxLayout()
        self.btn_cue_up = QPushButton("▲")
        self.btn_cue_down = QPushButton("▼")
        self.btn_cue_add = QPushButton("추가")
        self.btn_cue_edit = QPushButton("편집")
        self.btn_cue_del = QPushButton("삭제")
        
        cue_btn_layout.addWidget(self.btn_cue_up)
        cue_btn_layout.addWidget(self.btn_cue_down)
        cue_btn_layout.addWidget(self.btn_cue_add)
        cue_btn_layout.addWidget(self.btn_cue_edit)
        cue_btn_layout.addWidget(self.btn_cue_del)
        cue_inner.addLayout(cue_btn_layout)
        
        # Memo
        lbl_memo = QLabel("공연 전반 메모")
        lbl_memo.setStyleSheet("font-weight: bold;")
        cue_inner.addWidget(lbl_memo)
        # Memo and Export Layout
        memo_export_layout = QHBoxLayout()
        
        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText("통기타 모니터링 잘 들리게 해주세요\n신디사이저 모니터링 잘 들리게 해주세요")
        self.memo_edit.setMaximumHeight(100)
        memo_export_layout.addWidget(self.memo_edit)
        
        # Export Button
        self.btn_export_cue = QPushButton("내보내기")
        self.btn_export_cue.setFixedWidth(80)
        self.btn_export_cue.setFixedHeight(100) # Match memo height
        self.btn_export_cue.setStyleSheet("""
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
        memo_export_layout.addWidget(self.btn_export_cue)
        
        cue_inner.addLayout(memo_export_layout)
        
        cue_group.setLayout(cue_inner)
        right_layout.addWidget(cue_group)
        
        splitter.addWidget(right_container)
        
        # Set Splitter Ratios
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
