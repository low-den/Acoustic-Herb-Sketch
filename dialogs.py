from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QListWidget, QListWidgetItem,
                             QMessageBox, QScrollArea, QWidget, QTreeWidget, QTreeWidgetItem, QFrame, QRadioButton, QButtonGroup, QAbstractItemView, QCheckBox, QTextEdit, QGroupBox, QStackedWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from models import Member, Grade, MemberInstrument, Instrument, SkillLevel, InstrumentCategory, Song, SongSession, CueSection, DEFAULT_SECTION_NAMES
import uuid


# 악기 편집 다이얼로그
class InstrumentEditDialog(QDialog):
    # Signal emitted when instruments are changed
    instruments_changed = pyqtSignal()

    def __init__(self, data_handler, parent=None):
        super().__init__(parent)
        self.setWindowTitle("악기 편집")
        self.data_handler = data_handler
        self.resize(300, 500)
        
        self.init_ui()
        self.load_instruments()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # --- Left Panel: Instrument Tree ---
        left_layout = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        # Categories as top level items
        self.categories = {}
        for cat in InstrumentCategory:
            item = QTreeWidgetItem([cat.value])
            self.tree.addTopLevelItem(item)
            self.categories[cat.value] = item
            
        left_layout.addWidget(self.tree)
        
        # Add Button at bottom of tree
        self.btn_add_mode = QPushButton("악기추가")
        self.btn_add_mode.clicked.connect(self.toggle_add_panel)
        left_layout.addWidget(self.btn_add_mode)
        
        main_layout.addLayout(left_layout, stretch=1)
        
        # --- Right Panel: Add/Edit Instrument (Hidden by default or shown on add) ---
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        
        right_layout.addWidget(QLabel("이름"))
        self.edit_name = QLineEdit()
        right_layout.addWidget(self.edit_name)
        
        right_layout.addWidget(QLabel("분류"))
        self.combo_cat = QComboBox()
        for cat in InstrumentCategory:
            self.combo_cat.addItem(cat.value)
        right_layout.addWidget(self.combo_cat)

        
        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("추가") 
        self.btn_cancel = QPushButton("취소")
        self.btn_delete = QPushButton("제거") 
        
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_cancel)
        
        right_layout.addLayout(btn_row)
        right_layout.addStretch()
        
        main_layout.addWidget(self.right_panel, stretch=1)
        
        # Initial State: Hidden
        self.right_panel.hide()
        
        # Connect signals
        self.btn_add.clicked.connect(self.add_instrument)
        self.btn_cancel.clicked.connect(self.hide_right_panel)
        self.btn_delete.clicked.connect(self.delete_instrument)
        self.tree.itemClicked.connect(self.on_item_clicked)
        
        self.current_edit_id = None

    def show_right_panel(self):
        if self.right_panel.isHidden():
            self.right_panel.show()
            self.resize(600, self.height())

    def hide_right_panel(self):
        if not self.right_panel.isHidden():
            self.right_panel.hide()
            self.resize(300, self.height())
        self.current_edit_id = None
        self.tree.clearSelection() 

    def toggle_add_panel(self):
        self.current_edit_id = None
        self.edit_name.clear()
        self.combo_cat.setCurrentIndex(0)
        
        # Enable inputs
        self.edit_name.setEnabled(True)
        self.combo_cat.setEnabled(True)
        
        self.btn_add.setText("추가")
        self.btn_add.setEnabled(True)
        self.btn_delete.hide()
        self.show_right_panel()

    def on_item_clicked(self, item, column):
        if item.parent() is None:
            self.hide_right_panel()
            return
            
        inst_id = item.data(0, Qt.ItemDataRole.UserRole)
        inst = next((i for i in self.data_handler.instruments if i.id == inst_id), None)
        if not inst: return
        
        self.current_edit_id = inst.id
        self.edit_name.setText(inst.name)
        self.combo_cat.setCurrentText(inst.category)
            
        # Check default
        is_default = getattr(inst, 'is_default', False)
        
        self.edit_name.setEnabled(not is_default)
        self.combo_cat.setEnabled(not is_default)
            
        if is_default:
            self.btn_add.setText("수정 불가")
            self.btn_add.setEnabled(False)
            self.btn_delete.hide()
        else:
            self.btn_add.setText("적용")
            self.btn_add.setEnabled(True)
            self.btn_delete.show()
            
        self.show_right_panel()

    def load_instruments(self):
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            parent.takeChildren()
            
        for inst in self.data_handler.instruments:
            parent = self.categories.get(inst.category)
            if parent:
                item = QTreeWidgetItem([inst.name])
                item.setData(0, Qt.ItemDataRole.UserRole, inst.id)
                parent.addChild(item)
                
        self.tree.expandAll()

    def add_instrument(self):
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "경고", "이름을 입력해주세요.")
            return
            
        cat = self.combo_cat.currentText()
        
        if self.current_edit_id:
            inst = next((i for i in self.data_handler.instruments if i.id == self.current_edit_id), None)
            if inst:
                inst.name = name
                inst.category = cat
        else:
            new_inst = Instrument(name=name, category=cat)
            self.data_handler.instruments.append(new_inst)
            
        self.load_instruments()
        self.instruments_changed.emit()
        self.hide_right_panel()

    def delete_instrument(self):
        if not self.current_edit_id: return
        
        inst = next((i for i in self.data_handler.instruments if i.id == self.current_edit_id), None)
        if not inst: return

        if getattr(inst, 'is_default', False):
            QMessageBox.warning(self, "경고", "기본(디폴트) 악기는 삭제할 수 없습니다.")
            return

        reply = QMessageBox.question(self, '삭제', '정말 삭제하시겠습니까? (사용 중인 곡에서도 영향이 있습니다)', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.data_handler.instruments.remove(inst)
            self.load_instruments()
            self.instruments_changed.emit()
            self.hide_right_panel()

# 악기 선택 다이얼로그
class InstrumentSelectDialog(QDialog):
    def __init__(self, instruments, parent=None):
        super().__init__(parent)
        self.setWindowTitle("악기 선택")
        self.instruments = instruments
        self.selected_inst = None
        self.resize(300, 500)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        
        categories = {}
        for cat in InstrumentCategory:
            item = QTreeWidgetItem([cat.value])
            item.setData(0, Qt.ItemDataRole.UserRole, "CATEGORY") 
            self.tree.addTopLevelItem(item)
            categories[cat.value] = item
            
        for inst in self.instruments:
            parent = categories.get(inst.category)
            if parent:
                item = QTreeWidgetItem([inst.name])
                item.setData(0, Qt.ItemDataRole.UserRole, inst)
                parent.addChild(item)
                
        self.tree.expandAll()
        layout.addWidget(self.tree)
        
        btn_layout = QHBoxLayout()
        btn_select = QPushButton("선택")
        btn_cancel = QPushButton("취소")
        
        btn_select.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_select)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.tree.itemDoubleClicked.connect(self.accept)

    def accept(self):
        item = self.tree.currentItem()
        if not item: return
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data == "CATEGORY" or data is None:
            return
            
        self.selected_inst = data
        super().accept()

# 프로필 편집 - 악기 Row(행) 위젯
class InstrumentRowWidget(QWidget):
    VOCAL_RANGE = ["E5", "F5", "F#5", "G5", "G#5", "A5", "A#5", "B5", 
                   "C6", "C#6", "D6", "D#6", "E6", "F6", "F#6", "G6", "G#6", "A6", "A#6", "B6", 
                   "C7"]

    def __init__(self, pool, data: MemberInstrument = None, parent_dialog=None):
        super().__init__()
        self.pool = pool
        self.parent_dialog = parent_dialog
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.btn_inst_select = QPushButton("악기 선택")
        self.btn_skill_select = QComboBox()
        self.btn_delete = QPushButton("삭제")
        
        self.inst_id = None
        
        # Initialize UI state
        if data:
            self.inst_id = data.instrument_id
            inst_name = self.get_inst_name(data.instrument_id)
            self.btn_inst_select.setText(inst_name)
            self.update_skill_options(inst_name)
            self.btn_skill_select.setCurrentText(data.skill)
        else:
            self.btn_inst_select.setText("악기 선택")
            self.update_skill_options(None) # Default state
            
        self.layout.addWidget(self.btn_inst_select, stretch=3)
        self.layout.addWidget(self.btn_skill_select, stretch=2)
        self.layout.addWidget(self.btn_delete, stretch=1)
        
        self.btn_inst_select.clicked.connect(self.open_inst_select)
        
    def get_inst_name(self, inst_id):
        for i in self.pool:
            if i.id == inst_id:
                return i.name
        return "Unknown"

    def update_skill_options(self, inst_name):
        self.btn_skill_select.clear()
        
        if inst_name == "보컬/랩":
            self.btn_skill_select.addItem("최고음")
            self.btn_skill_select.addItems(self.VOCAL_RANGE)
        else:
            self.btn_skill_select.addItem("실력 선택")
            for s in SkillLevel:
                self.btn_skill_select.addItem(s.value)

    def open_inst_select(self):
        dlg = InstrumentSelectDialog(self.pool, self.parent_dialog)
        if dlg.exec():
            selected = dlg.selected_inst
            if selected:
                self.inst_id = selected.id
                self.btn_inst_select.setText(selected.name)
                self.update_skill_options(selected.name)

    def get_data(self):
        if not self.inst_id:
            return None
        skill_text = self.btn_skill_select.currentText()
        if skill_text in ["실력 선택", "최고음"]:
            return None
        return MemberInstrument(instrument_id=self.inst_id, skill=skill_text)

# 프로필 추가/편집 다이얼로그
class ProfileAddEditDialog(QDialog):
    def __init__(self, parent=None, member: Member = None, instruments_pool: list[Instrument] = None):
        super().__init__(parent)
        self.instruments_pool = instruments_pool or []
        self.member = member
        self.setWindowTitle("프로필 편집" if member else "프로필 추가")
        self.resize(400, 300)
        self.inst_rows = []
        
        self.init_ui()
        
        if member:
            self.load_member(member)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Name and Grade
        top_layout = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.grade_combo = QComboBox()
        for g in Grade:
            self.grade_combo.addItem(g.value)
            
        top_layout.addWidget(QLabel("이름:"))
        top_layout.addWidget(self.name_edit)
        top_layout.addWidget(QLabel("학년:"))
        top_layout.addWidget(self.grade_combo)
        layout.addLayout(top_layout)
        
        # Instruments Section
        layout.addWidget(QLabel("가능 악기"))
        
        self.inst_list_layout = QVBoxLayout()
        self.inst_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        inst_container = QWidget()
        inst_container.setLayout(self.inst_list_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inst_container)
        layout.addWidget(scroll)
        
        self.btn_add_inst = QPushButton("악기 추가")
        self.btn_add_inst.clicked.connect(lambda: self.add_instrument_row())
        layout.addWidget(self.btn_add_inst)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("적용")
        self.btn_cancel = QPushButton("취소")
        self.btn_apply.clicked.connect(self.validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def validate_and_accept(self):
        # Validate Name
        if not self.name_edit.text().strip():
             QMessageBox.warning(self, "경고", "이름을 입력해주세요.")
             return

        # Validate Instruments
        valid_instruments = []       
        for row in self.inst_rows:
            data = row.get_data()
            if data is None:
                QMessageBox.warning(self, "경고", "악기 혹은 실력을 선택해주세요.")
                return
            valid_instruments.append(data)
            
        if not valid_instruments:
           QMessageBox.warning(self, "경고", "최소 하나의 악기를 추가해주세요.")
           return

        self.accept()

    def add_instrument_row(self, instrument_data: MemberInstrument = None):
        row = InstrumentRowWidget(self.instruments_pool, instrument_data, self)
        self.inst_list_layout.addWidget(row)
        self.inst_rows.append(row)
        row.btn_delete.clicked.connect(lambda: self.remove_instrument_row(row))

    def remove_instrument_row(self, row):
        reply = QMessageBox.question(self, '삭제', '정말 삭제하시겠습니까?', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.inst_list_layout.removeWidget(row)
            row.deleteLater()
            self.inst_rows.remove(row)

    def load_member(self, member: Member):
        self.name_edit.setText(member.name)
        index = self.grade_combo.findText(member.grade)
        if index >= 0:
            self.grade_combo.setCurrentIndex(index)
        
        for inst in member.instruments:
            self.add_instrument_row(inst)

    def get_data(self) -> Member:
        # Construct Member object
        m = Member()
        if self.member:
            m.id = self.member.id # Keep ID if editing
            
        m.name = self.name_edit.text()
        m.grade = self.grade_combo.currentText()
        
        instruments = []
        for row in self.inst_rows:
            data = row.get_data()
            if data:
                instruments.append(data)
        m.instruments = instruments
        return m

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.validate_and_accept()
        else:
            super().keyPressEvent(event)

# 세션 편집 다이얼로그
class SessionEditDialog(QDialog):
    def __init__(self, parent, member: Member, song: Song, current_assignments: list, instruments_pool: list[Instrument], service):
        super().__init__(parent)
        self.member = member
        self.song = song
        self.current_assignments = current_assignments # List of session IDs assigned to this member in this song
        self.instruments_pool = instruments_pool
        self.service = service # To check warnings logic
        
        self.setWindowTitle("세션 편집 다이얼로그")
        self.resize(500, 500)
        
        self.checkboxes = {} # session_id -> QCheckBox
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Info Header
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"이름: {self.member.name}"))
        info_layout.addWidget(QLabel(f"학년: {self.member.grade}"))
        layout.addLayout(info_layout)
        
        layout.addWidget(QLabel("악기 선택"))
        
        # Scroll Area for Sessions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        
        self.warning_labels = []
        
        # Use ButtonGroup for exclusive selection (Modified to allow unchecking)
        self.session_group = QButtonGroup(self)
        self.session_group.setExclusive(False)
        self.session_group.buttonToggled.connect(self.on_checkbox_toggled)

        # 1. Count instances of each instrument ID in this song to determine if numbering is needed
        inst_counts = {}
        for session in self.song.sessions:
            inst_counts[session.instrument_id] = inst_counts.get(session.instrument_id, 0) + 1
            
        inst_indices = {} # To track current index: instrument_id -> current_count

        for session in self.song.sessions:
            # Row for each session
            row_widget = QWidget()
            row_layout = QVBoxLayout(row_widget)
            
            # Checkbox (Acting as Radio due to logic) and Instrument Name
            h_layout = QHBoxLayout()
            cb = QCheckBox() 
            self.checkboxes[session.id] = cb
            self.session_group.addButton(cb)
            
            inst = next((i for i in self.instruments_pool if i.id == session.instrument_id), None)
            
            # Determine display name with numbering if needed
            display_name = "Unknown"
            if inst:
                if inst_counts.get(inst.id, 0) > 1:
                    idx = inst_indices.get(inst.id, 0) + 1
                    inst_indices[inst.id] = idx
                    display_name = f"{inst.name} {idx}"
                else:
                    display_name = inst.name
            
            cb.setText(display_name)
            if session.id in self.current_assignments:
                cb.setChecked(True)
                
            h_layout.addWidget(cb)
            
            # Show Member's skill if they have this instrument
            member_inst = next((i for i in self.member.instruments if i.instrument_id == session.instrument_id), None)
            skill_text = member_inst.skill if member_inst else "연주 불가"
            
            h_layout.addStretch()
            if member_inst:
                h_layout.addWidget(QLabel(f"실력: {skill_text}"))
            
            row_layout.addLayout(h_layout)
            
            # Check for Warning
            warnings = self.service.validate_assignment(self.member, self.song, session)
            if warnings:
                for w in warnings:
                    lbl = QLabel(w)
                    if "배정되지 않았습니다" in w or "너무 적습니다" in w:
                        lbl.setStyleSheet("color: #FF8C00; font-size: 11px;")
                    elif "너무 많습니다" in w:
                        lbl.setStyleSheet("color: #FF4800; font-size: 11px;")
                    elif "할 수 없습니다" in w:
                        lbl.setStyleSheet("color: black; font-size: 11px;")
                    elif "너무 높습니다" in w:
                        lbl.setStyleSheet("color: blue; font-size: 11px;")
                    else:
                        lbl.setStyleSheet("color: red; font-size: 11px;")
                    row_layout.addWidget(lbl)
                    self.warning_labels.append(lbl)
            elif member_inst:
                # No warnings and capable -> Suitable
                # Use raw inst name for message usually, or display name?
                # "member의 일렉기타 2 실력이..." -> weird if skill is generic.
                # "member의 일렉기타 실력이..." -> better.
                msg = f"{self.member.name}의 {inst.name if inst else 'Unknown'} 실력이 곡에 적합합니다."
                lbl = QLabel(msg)
                lbl.setStyleSheet("color: green; font-size: 11px;")
                row_layout.addWidget(lbl)
                self.warning_labels.append(lbl)
                    
            self.list_layout.addWidget(row_widget)
            
            # Separator
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            self.list_layout.addWidget(line)
            
        layout.addWidget(scroll)
        
        # Ignore Warning Checkbox
        self.cb_ignore_warning = QCheckBox("경고 무시")
        
        # Load existing ignore state
        existing_ignore = False
        if self.current_assignments:
             sid = self.current_assignments[0]
             # assignment = self.service.get_assignment_object(self.song.id, sid) # Method added to service
             # But dialog calls service methods, so let's rely on service interface or access data_handler via service
             # Since get_assignment_object was added to SessionService, we can use it.
             assignment = self.service.get_assignment_object(self.song.id, sid)
             if assignment and assignment.member_id == self.member.id:
                 existing_ignore = assignment.ignore_warnings
        
        self.cb_ignore_warning.setChecked(existing_ignore)
        
        # Connect to toggle visibility of warnings
        self.cb_ignore_warning.toggled.connect(self.toggle_warnings)
        layout.addWidget(self.cb_ignore_warning)
        
        # Initialize warning visibility
        self.toggle_warnings(existing_ignore)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("적용")
        btn_cancel = QPushButton("취소")
        
        btn_apply.clicked.connect(self.validate_and_accept)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def on_checkbox_toggled(self, button, checked):
        if checked:
            # Uncheck all other buttons
            for btn in self.session_group.buttons():
                if btn != button:
                    # Prevent recursive signal loop if needed, but setChecked(False) on unchecked is fine
                    if btn.isChecked():
                        btn.setChecked(False)

    def toggle_warnings(self, checked):
        for lbl in self.warning_labels:
            lbl.setVisible(not checked)

    def validate_and_accept(self):
        # Allow even without warnings check if user insists? 
        # "경고 무시를 체크하지 않아도 아무런 확인창 없이 등록할 수 있도록 해줘."
        self.accept()
    
    def get_selected_sessions(self):
        return [sess_id for sess_id, cb in self.checkboxes.items() if cb.isChecked()]

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.validate_and_accept()
        else:
            super().keyPressEvent(event)

# 큐시트 항목 추가/편집 다이얼로그
class CueSheetEditDialog(QDialog):
    def __init__(self, parent, song: Song, section_data: CueSection = None, service=None):
        super().__init__(parent)
        self.song = song
        self.section_data = section_data
        self.service = service
        self.setWindowTitle("큐시트 항목 추가/편집" if not section_data else "큐시트 항목 편집")
        self.resize(600, 400)
        
        self.inst_widgets = {} # instrument_id -> { 'note': QLineEdit, 'effect_cb': QCheckBox, 'effect_name': QLineEdit, 'effect_level': QButtonGroup }
        self.init_ui()
        
    def init_ui(self):
        # Override init_ui to re-structure
        dialog_layout = QVBoxLayout(self)
        
        content_layout = QHBoxLayout()
        
        # --- Left Panel: Section Selector ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("섹션 선택"))
        
        self.section_list = QListWidget()
        
        # Initialize list with DEFAULT + Existing Custom Sections
        existing_names = [s.name for s in self.song.cue_sections]
        
        # Add Defaults first
        for name in DEFAULT_SECTION_NAMES:
            self.section_list.addItem(name)
            
        # Add existing custom sections if not in default
        for name in existing_names:
            if name not in DEFAULT_SECTION_NAMES:
                # Check if already added (to avoid duplicates if defaults are in song)
                # DEFAULT_SECTION_NAMES are unique.
                # Just add.
                # Check if it's already in the list widget to be safe?
                # QListWidget doesn't enforce uniqueness.
                # Let's check visually.
                # existing_names might contain defaults.
                # If name is NOT in DEFAULT_SECTION_NAMES, we add it.
                self.section_list.addItem(name)
        
        self.section_list.itemClicked.connect(self.on_section_selected)
        left_layout.addWidget(self.section_list)
        
        # Section List Buttons
        list_btn_layout = QHBoxLayout()
        self.btn_add_section = QPushButton("추가")
        self.btn_del_section = QPushButton("삭제")
        self.btn_add_section.clicked.connect(self.add_new_section_to_list)
        self.btn_del_section.clicked.connect(self.delete_section_from_list)
        
        list_btn_layout.addWidget(self.btn_add_section)
        list_btn_layout.addWidget(self.btn_del_section)
        left_layout.addLayout(list_btn_layout)
        
        content_layout.addWidget(left_widget, stretch=1)
        
        # --- Right Panel: Inputs ---
        self.right_panel = QWidget()
        self.right_panel.setEnabled(False)
        right_layout = QVBoxLayout(self.right_panel)
        
        # Instrument Name
        right_layout.addWidget(QLabel("악기"))
        self.input_inst_name = QLineEdit()
        self.input_inst_name.setPlaceholderText("예: 보컬")
        right_layout.addWidget(self.input_inst_name)
        
        # Effect Group
        eff_group = QGroupBox("이펙트")
        eff_layout = QVBoxLayout(eff_group)
        
        self.cb_effect = QCheckBox("이펙트 사용 요청")
        self.input_effect_name = QLineEdit()
        self.input_effect_name.setPlaceholderText("예: 리버브")
        self.input_effect_name.setEnabled(False)
        self.cb_effect.toggled.connect(self.input_effect_name.setEnabled)
        
        eff_layout.addWidget(self.cb_effect)
        eff_layout.addWidget(self.input_effect_name)
        
        # Effect Level
        level_layout = QHBoxLayout()
        self.group_level = QButtonGroup(self.right_panel)
        labels = ["Dry", "", "", "", "Wet"]
        for i, label in enumerate(labels, 1):
            rb = QRadioButton(label)
            self.group_level.addButton(rb, i)
            level_layout.addWidget(rb)
        # Default to 3 (Natural)
        self.group_level.button(3).setChecked(True)
        
        eff_layout.addLayout(level_layout)
        right_layout.addWidget(eff_group)
        
        # Memo
        right_layout.addWidget(QLabel("메모"))
        self.edit_memo = QTextEdit()
        self.edit_memo.setPlaceholderText("20자 이내로 적어주세요\n(예: 따뜻하고 두터운 톤\n일렉기타 솔로할 때 볼륨 살짝 낮춰주세요)")
        right_layout.addWidget(self.edit_memo, 1)
        
        content_layout.addWidget(self.right_panel, stretch=2)
        
        dialog_layout.addLayout(content_layout)
        
        # --- Bottom Buttons ---
        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("적용")
        self.btn_cancel = QPushButton("취소")
        
        self.btn_apply.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)
        dialog_layout.addLayout(btn_layout)
        
        # Select target section if provided
        if self.section_data:
            items = self.section_list.findItems(self.section_data.name, Qt.MatchFlag.MatchExactly)
            if items:
                self.section_list.setCurrentItem(items[0])
                self.on_section_selected(items[0])
        elif self.section_list.count() > 0:
             self.section_list.setCurrentRow(0)
             self.on_section_selected(self.section_list.item(0))

    def add_new_section_to_list(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "섹션 추가", "새 섹션 이름을 입력하세요:")
        if ok and name.strip():
            # Check for duplicates in list
            if self.section_list.findItems(name.strip(), Qt.MatchFlag.MatchExactly):
                QMessageBox.warning(self, "중복", "이미 존재하는 섹션 이름입니다.")
                return
            self.section_list.addItem(name.strip())

    def delete_section_from_list(self):
        item = self.section_list.currentItem()
        if not item:
            QMessageBox.warning(self, "선택", "삭제할 섹션을 선택해주세요.")
            return
            
        name = item.text()
        if name in DEFAULT_SECTION_NAMES:
            QMessageBox.warning(self, "경고", "기본(디폴트) 섹션은 삭제할 수 없습니다.")
            return
            
        # Remove from list
        self.section_list.takeItem(self.section_list.row(item))
        self.right_panel.setEnabled(False) # Disable right panel as selection is gone

    def on_section_selected(self, item):
        self.right_panel.setEnabled(True)
        # We don't clear inputs here to allow quick switching if needed, or maybe we should?
        # User might want to "Add note to Intro", then realize "Oh wait, Verse 1".
        # Keeping inputs is safer.

    def get_data(self):
        if not self.section_list.currentItem(): return None
        
        sec_name = self.section_list.currentItem().text()
        
        import json
        # Construct data dict
        entry_data = {
            "instrument_name": self.input_inst_name.text().strip(),
            "use_effect": self.cb_effect.isChecked(),
            "effect_name": self.input_effect_name.text().strip(),
            "effect_level": self.group_level.checkedId(),
            "memo": self.edit_memo.toPlainText()
        }
        
        return sec_name, entry_data

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.edit_memo.hasFocus():
                super().keyPressEvent(event)
            else:
                self.accept()
        else:
            super().keyPressEvent(event)

# 음향 설계 다이얼로그
class SoundDesignDialog(QDialog):
    def __init__(self, data_handler, parent=None):
        super().__init__(parent)
        self.data_handler = data_handler
        self.settings = dict(data_handler.sound_design_settings) # Deep copy? flat dict is fine
        self.setWindowTitle("음향 설계 상세 설정")
        self.resize(600, 400)
        
        self.init_ui()
        self.populate_list()
        
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # Left Panel: List
        left_layout = QVBoxLayout()
        self.inst_list = QListWidget()
        self.inst_list.itemClicked.connect(self.on_item_selected)
        left_layout.addWidget(self.inst_list)
        main_layout.addLayout(left_layout, 1)
        
        # Right Panel: Settings (Stacked Widget)
        self.right_panel = QStackedWidget()
        main_layout.addWidget(self.right_panel, 2)
        
        # Page 0: Empty
        self.right_panel.addWidget(QLabel("좌측 목록에서 악기를 선택해주세요."))
        
        # Page 1: Config Widget
        self.config_page = QWidget()
        config_layout = QVBoxLayout(self.config_page)
        
        self.lbl_selected_inst = QLabel("-")
        self.lbl_selected_inst.setStyleSheet("font-weight: bold; font-size: 14px;")
        config_layout.addWidget(self.lbl_selected_inst)
        
        config_layout.addSpacing(20)
        
        # Controls Container
        self.controls_container = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_container)
        config_layout.addWidget(self.controls_container)
        
        config_layout.addStretch()
        
        # Apply Button (for Dialog)
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_cancel = QPushButton("취소")
        
        btn_save.clicked.connect(self.save_and_accept)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        config_layout.addLayout(btn_layout)
        
        self.right_panel.addWidget(self.config_page)
        
        # Current Selection State
        self.current_key = None

    def populate_list(self):
        # Scan all songs to find max concurrent usage of each instrument
        max_usage = {} # inst_id -> max_count
        
        for song in self.data_handler.songs:
            current_counts = {}
            for session in song.sessions:
                inst_id = session.instrument_id
                current_counts[inst_id] = current_counts.get(inst_id, 0) + 1
            
            for iid, count in current_counts.items():
                max_usage[iid] = max(max_usage.get(iid, 0), count)
                
        # Populate List
        self.inst_list.clear()
        
        # Sort instruments by category then name for display
        sorted_instruments = sorted(self.data_handler.instruments, key=lambda x: (x.category, x.name))
        
        for inst in sorted_instruments:
            count = max_usage.get(inst.id, 0)
            
            # If count is 0, skip
            if count == 0:
                continue
                
            # If count > 1, enumerate. If count == 1, just name.
            if count == 1:
                item_text = inst.name
                item = QListWidgetItem(item_text)
                # Store (inst_object, index) -> index is 0 (0-based)
                item.setData(Qt.ItemDataRole.UserRole, (inst, 0))
                self.inst_list.addItem(item)
            else:
                for i in range(count):
                    item_text = f"{inst.name} {i+1}"
                    item = QListWidgetItem(item_text)
                    # Store (inst_object, index)
                    item.setData(Qt.ItemDataRole.UserRole, (inst, i))
                    self.inst_list.addItem(item)

    def on_item_selected(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data: return
        
        inst, index = data
        self.current_key = self.get_settings_key(inst, index)
        
        # Update Label
        self.lbl_selected_inst.setText(item.text())
        
        # Clear previous controls
        self.clear_layout(self.controls_layout)
        
        current_val = self.settings.get(self.current_key, -1)
        
        options = self._get_connection_options(inst)
        
        if not options:
            self.controls_layout.addWidget(QLabel("별도의 음향 설계 설정이 필요하지 않습니다."))
        else:
            lbl = QLabel("연결 방식")
            lbl.setStyleSheet("font-weight: bold;")
            self.controls_layout.addWidget(lbl)
            
            bg = QButtonGroup(self)
            
            for idx, (option_text, description) in enumerate(options):
                rb = QRadioButton(option_text)
                bg.addButton(rb, idx)
                self.controls_layout.addWidget(rb)
                
                # Description label showing required equipment
                desc_lbl = QLabel(f"  → {description}")
                desc_lbl.setStyleSheet("color: gray; font-size: 11px; margin-left: 20px;")
                self.controls_layout.addWidget(desc_lbl)
            
            if current_val != -1 and 0 <= current_val < len(options):
                bg.button(current_val).setChecked(True)
            else:
                bg.button(0).setChecked(True)  # Default: first option
                
            bg.idClicked.connect(self.update_setting)
            
        self.right_panel.setCurrentWidget(self.config_page)

    def _get_connection_options(self, inst):
        """Returns list of (display_text, equipment_description) for the instrument's connection options.
        
        Returns empty list for instruments that have only a single fixed connection 
        method (드럼, 퍼커션) and don't need user configuration.
        """
        # Build guitar family set (기타계열 excluding 일렉기타, 베이스)
        guitar_family_names = set()
        for i in self.data_handler.instruments:
            if i.category == InstrumentCategory.GUITAR.value and i.name not in ["일렉기타", "베이스"]:
                guitar_family_names.add(i.name)
        
        if inst.name == "보컬/랩":
            return [
                ("믹서 직결", "XLR 5m 1개, 롱 마이크 스탠드 1개"),
                ("보컬 이펙터", "XLR 5m 2개, 롱 마이크 스탠드 1개"),
            ]
        elif inst.name in guitar_family_names:
            return [
                ("통기타 이펙터", "TS 3m 1개, XLR 5m 1개"),
                ("믹서 직결", "TS 5m 1개"),
                ("마이킹", "XLR 5m 1개"),
                ("패시브 DI", "패시브 DI 모노 1개, TS 3m 1개, XLR 5m 1개"),
            ]
        elif inst.name == "일렉기타":
            return [
                ("기타-이펙터-앰프 (Fx Loop 사용)", "TS 3m 3개, XLR 5m 1개, SM57 1개,\n숏 마이크 스탠드 1개, 일렉 앰프 1개"),
                ("기타-이펙터-앰프 (Fx Loop 미사용)", "TS 3m 2개, XLR 5m 1개, SM57 1개,\n숏 마이크 스탠드 1개, 일렉 앰프 1개"),
                ("기타-앰프", "TS 3m 1개, XLR 5m 1개, SM57 1개,\n숏 마이크 스탠드 1개, 일렉 앰프 1개"),
            ]
        elif inst.name == "베이스":
            return [
                ("기타-이펙터-앰프/믹서", "TS 3m 2개, XLR 5m 1개, 베이스 앰프 1개"),
                ("기타-이펙터-앰프 마이킹", "TS 3m 1개, XLR 5m 1개, SM57 1개,\n숏 마이크 스탠드 1개, 베이스 앰프 1개"),
            ]
        elif inst.name in ["디지털 피아노", "신디사이저"]:
            return [
                ("패시브 DI", "패시브 DI 스테레오 1개, TS 3m 2개, XLR 5m 2개"),
                ("액티브 DI", "액티브 DI 스테레오 1개, TS 3m 2개, XLR 5m 2개"),
            ]
        elif inst.name == "카혼":
            return [
                ("마이킹", "SM57 2개, XLR 5m 2개, 숏 마이크 스탠드 1개,\n롱 마이크 스탠드 1개"),
                ("픽업-믹서직결", "TS 5m 1개"),
                ("픽업-DI", "액티브 DI 모노 1개, TS 3m 1개, XLR 5m 1개"),
            ]
        elif inst.name in ["드럼", "퍼커션"]:
            return []  # Single fixed method, no user choice needed
        else:
            # 나머지 모든 악기
            return [
                ("SM58 마이킹", "SM58 1개, XLR 5m 1개"),
                ("SM57 마이킹", "SM57 1개, XLR 5m 1개"),
                ("핀마이크·바디팩", "핀마이크·바디팩 1개, XLR 5m 1개"),
                ("픽업-믹서직결", "TS 5m 1개"),
                ("픽업-DI", "액티브 DI 모노 1개, TS 3m 1개, XLR 5m 1개"),
            ]

    def get_settings_key(self, inst, index):
        """Generates a settings key in the format '{inst.name}_{index}_conn'."""
        return f"{inst.name}_{index}_conn"

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def update_setting(self, val):
        if self.current_key:
            self.settings[self.current_key] = val

    def save_and_accept(self):
        # Sync back to data_handler
        self.data_handler.sound_design_settings = self.settings
        self.accept()
