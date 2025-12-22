from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableView, QHeaderView, 
                             QStyledItemDelegate, QAbstractItemView, QStyleOptionViewItem,
                             QApplication, QStyle, QHBoxLayout, QLabel, QScrollArea, QFrame,
                             QLineEdit, QComboBox, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QRect, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QFontMetrics, QFont
from data_handler import DataHandler # Import explicitly
from session_service import SessionService

class SessionHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(False)
        self.setDefaultSectionSize(100)
    
    def sizeHint(self):
        s = super().sizeHint()
        s.setHeight(60) # Increased height for 2 rows
        return s

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        model = self.model()
        
        # Data from model
        # UserRole: Top Text (Category / Group)
        # DisplayRole: Bottom Text (Title / Specific)
        top_text = model.headerData(logicalIndex, Qt.Orientation.Horizontal, Qt.ItemDataRole.UserRole)
        bottom_text = model.headerData(logicalIndex, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        
        # Geometry
        h = rect.height()
        half_h = h // 2
        
        top_rect = QRect(rect.left(), rect.top(), rect.width(), half_h)
        bottom_rect = QRect(rect.left(), rect.top() + half_h, rect.width(), h - half_h)
        
        # Draw Background
        painter.fillRect(rect, QColor("#dcdcdc"))
        
        # Prepare Font (Bold)
        bold_font = painter.font()
        bold_font.setBold(True)
        painter.setFont(bold_font)
        
        # --- Draw Bottom Cell ---
        painter.setPen(QColor("#d0d0d0"))
        # Draw borders for bottom cell
        painter.drawLine(bottom_rect.bottomLeft(), bottom_rect.bottomRight())
        painter.drawLine(bottom_rect.topRight(), bottom_rect.bottomRight())
        painter.drawLine(bottom_rect.bottomLeft(), bottom_rect.topLeft()) # Shared with next
        painter.drawLine(bottom_rect.topRight(), bottom_rect.topLeft()) # Middle line
        
        # Draw Text
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(bottom_rect, Qt.AlignmentFlag.AlignCenter, bottom_text)
        
        # --- Draw Top Cell (Merged Logic) ---
        if top_text:
            # Find start and end of the merge group
            start_idx = logicalIndex
            while start_idx > 0:
                prev_top = model.headerData(start_idx - 1, Qt.Orientation.Horizontal, Qt.ItemDataRole.UserRole)
                if prev_top == top_text:
                    start_idx -= 1
                else:
                    break
                    
            end_idx = logicalIndex
            while end_idx < model.columnCount() - 1:
                next_top = model.headerData(end_idx + 1, Qt.Orientation.Horizontal, Qt.ItemDataRole.UserRole)
                if next_top == top_text:
                    end_idx += 1
                else:
                    break
            
            # Calculate total width of the group
            total_width = 0
            for i in range(start_idx, end_idx + 1):
                total_width += self.sectionSize(i)
                
            # Calculate offset of current section within the group
            current_offset = 0
            for i in range(start_idx, logicalIndex):
                current_offset += self.sectionSize(i)
                
            # Construct the rectangle for the FULL merged cell, relative to current section's position
            full_rect_x = rect.left() - current_offset
            full_rect = QRect(full_rect_x, rect.top(), total_width, half_h)
            
            # Draw Borders
            painter.setPen(QColor("#d0d0d0"))
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top()) # Top border segment
            
            # Left border if start
            if logicalIndex == start_idx:
                 painter.drawLine(rect.topLeft(), rect.bottomLeft()) # Left border
                 
            # Right border if end
            if logicalIndex == end_idx:
                 painter.drawLine(rect.topRight(), rect.bottomRight()) # Right border
            
            # Draw Text
            painter.setPen(Qt.GlobalColor.black)
            painter.setClipping(False) # Allow drawing outside current section to cover full merged area
            
            painter.drawText(full_rect, Qt.AlignmentFlag.AlignCenter, top_text)
            painter.setClipping(True)
            
        else:
             # Empty top text, just draw borders?
             pass
             
        painter.restore()


class SessionDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, service: SessionService = None):
        super().__init__(parent)
        self.service = service
        self.hover_row = -1
        self.hover_col = -1
        self.export_mode = False # Flag for image export

    def set_hover(self, row, col):
        self.hover_row = row
        self.hover_col = col

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Bold Font for 1st Column (1열)
        if index.column() == 0:
            option.font.setBold(True)
            option.font.setPointSize(option.font.pointSize() + 1)
            
        if not self.service: return
        model = index.model()
        if not model or not hasattr(model, 'rows') or not hasattr(model, 'cols_map'): return

        try:
            member = model.rows[index.row()]
            if member is None:
                return # Separator row
            col_type, song_id, _ = model.cols_map[index.column()]
        except IndexError:
            return

        # --- Export Mode Logic ---
        if self.export_mode:
            # 1. Alternating Row Colors (Manual to ensure visibility)
            if index.row() % 2 == 1:
                option.backgroundBrush = QBrush(QColor("#d6e4ed")) # Custom Alternating Color
            else:
                option.backgroundBrush = QBrush(Qt.GlobalColor.white)
            
            # 2. Assignment Count Column Highlight (Preserve in Export)
            if col_type == "COUNT_VOCAL":
                stats = self.service.get_assignment_stats()
                status = stats.get(member.id, "NONE")
                if status == "OVER":
                    option.backgroundBrush = QBrush(QColor(255, 200, 200)) # Red-ish
                elif status == "UNDER":
                    option.backgroundBrush = QBrush(QColor(255, 255, 200)) # Yellow-ish
                elif status == "NORMAL":
                    option.backgroundBrush = QBrush(QColor(200, 255, 200)) # Green-ish
            return

        # --- Normal Mode Logic ---
        # 1. Hover Highlight (Low Priority)
        if self.hover_row != -1 and self.hover_col != -1:
            is_hover_cell = (index.row() == self.hover_row and index.column() == self.hover_col)
            is_col_highlight = (index.column() == self.hover_col and index.row() <= self.hover_row)
            is_row_highlight = (index.row() == self.hover_row and index.column() <= self.hover_col)
            
            if is_hover_cell:
                 option.backgroundBrush = QBrush(QColor("#66A3FF")) # Darker Blue for current cell
            elif is_col_highlight or is_row_highlight:
                # Apply light blue highlight
                option.backgroundBrush = QBrush(QColor("#B3D9FF")) # Stronger Light Blue

        try:
            # 2. Assignment Count Column (Vocal Included) - High Priority
            if col_type == "COUNT_VOCAL":
                stats = self.service.get_assignment_stats()
                status = stats.get(member.id, "NONE")
                if status == "OVER":
                    option.backgroundBrush = QBrush(QColor(255, 200, 200)) # Red-ish
                elif status == "UNDER":
                    option.backgroundBrush = QBrush(QColor(255, 255, 200)) # Yellow-ish
                elif status == "NORMAL":
                    option.backgroundBrush = QBrush(QColor(200, 255, 200)) # Green-ish
            
            # 3. Song Column (Skill check) - High Priority
            elif col_type == "SONG":
                # Find assignment for this cell
                assignment = None
                for a in self.service.data_handler.assignments:
                    if a.song_id == song_id and a.member_id == member.id:
                        assignment = a
                        break
                        
                if assignment:
                    if getattr(assignment, 'ignore_warnings', False):
                         return
                    
                    song = next((s for s in self.service.data_handler.songs if s.id == song_id), None)
                    if song:
                        session = next((s for s in song.sessions if s.id == assignment.session_id), None)
                        if session:
                            warnings = self.service.validate_assignment(member, song, session)
                            if warnings:
                                # Determine color based on warning type
                                is_too_high = any("너무 높습니다" in w for w in warnings)
                                is_insufficient = any("부족합니다" in w or "낮습니다" in w for w in warnings)
                                
                                if is_insufficient:
                                    option.backgroundBrush = QBrush(QColor(255, 200, 200)) # Red (Insufficient)
                                elif is_too_high:
                                    option.backgroundBrush = QBrush(QColor("#C9C2E8"))
                                else:
                                    option.backgroundBrush = QBrush(QColor(255, 200, 200)) # Default Red
        except:
            pass

class SessionTableModel(QAbstractTableModel):
    def __init__(self, data_handler: DataHandler):
        super().__init__()
        self.data_handler = data_handler
        self.rows = [] 
        self.cols_map = [] 
        
        self.refresh_structure()

    def refresh_structure(self):
        self.beginResetModel()
        
        from models import Grade # Lazy import or ensure imported
        
        # 1. Rows
        grade_order = [Grade.BON2.value, Grade.BON1.value, Grade.YE2.value, Grade.YE1.value, Grade.BON4.value, Grade.BON3.value]
        groups = []
        for g in grade_order:
            members = sorted([m for m in self.data_handler.members if m.grade == g], key=lambda x: x.name)
            if members:
                groups.append(members)
                
        self.rows = []
        for i, group in enumerate(groups):
            self.rows.extend(group)
            if i < len(groups) - 1:
                self.rows.append(None)
            
        # 2. Columns
        # First column: Name (combined with Grade)
        self.cols_map = [
            ("MEMBER_INFO", "name", None)
        ]
        
        # One column per Song
        for song in self.data_handler.songs:
            self.cols_map.append(("SONG", song.id, None))
        
        # Order requested: Count No Vocal, then Count Vocal
        self.cols_map.append(("COUNT_NO_VOCAL", None, None))
        self.cols_map.append(("COUNT_VOCAL", None, None))
        
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.cols_map)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        row_idx = index.row()
        if row_idx < len(self.rows) and self.rows[row_idx] is None:
            return Qt.ItemFlag.NoItemFlags
            
        return super().flags(index)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        
        row_idx = index.row()
        col_idx = index.column()
        member = self.rows[row_idx]
        
        # Handle Separator Row
        if member is None:
            return None

        col_type, song_id, _ = self.cols_map[col_idx]
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col_type == "MEMBER_INFO":
                return member.name
            
            elif col_type == "SONG":
                assigned_instruments = []
                song = next((s for s in self.data_handler.songs if s.id == song_id), None)
                if song:
                    for a in self.data_handler.assignments:
                        if a.song_id == song_id and a.member_id == member.id:
                            session = next((s for s in song.sessions if s.id == a.session_id), None)
                            if session:
                                inst = next((i for i in self.data_handler.instruments if i.id == session.instrument_id), None)
                                if inst:
                                    assigned_instruments.append(inst.name)
                
                return "\n".join(assigned_instruments)
            
            elif col_type == "COUNT_VOCAL":
                return str(self.calculate_count(member, include_vocal=True))
                
            elif col_type == "COUNT_NO_VOCAL":
                return str(self.calculate_count(member, include_vocal=False))
        
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col_type == "MEMBER_INFO":
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter
        
        # BackgroundRole and FontRole moved to SessionDelegate

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
            
        if section >= len(self.cols_map):
            return None
            
        col_type, song_id, _ = self.cols_map[section]
        
        if role == Qt.ItemDataRole.DisplayRole:
            if col_type == "MEMBER_INFO":
                return "이름"
            elif col_type == "SONG":
                song = next((s for s in self.data_handler.songs if s.id == song_id), None)
                title_text = "Unknown"
                if song:
                    title_text = song.nickname if song.nickname else song.title
                return title_text
            elif col_type == "COUNT_NO_VOCAL":
                return "보컬 미포함"
            elif col_type == "COUNT_VOCAL":
                return "보컬 포함"
                
        elif role == Qt.ItemDataRole.UserRole:
            if col_type == "MEMBER_INFO":
                return ""
            elif col_type == "SONG":
                song = next((s for s in self.data_handler.songs if s.id == song_id), None)
                return song.category if song else ""
            elif col_type == "COUNT_NO_VOCAL" or col_type == "COUNT_VOCAL":
                return "배정 개수"
                
        return None

    def calculate_count(self, member, include_vocal):
        count = 0
        for a in self.data_handler.assignments:
            if a.member_id == member.id:
                if include_vocal:
                    count += 1
                else:
                    song = next((s for s in self.data_handler.songs if s.id == a.song_id), None)
                    if song:
                        session = next((s for s in song.sessions if s.id == a.session_id), None)
                        if session:
                            inst = next((i for i in self.data_handler.instruments if i.id == session.instrument_id), None)
                            if inst and inst.name != "보컬/랩":
                                count += 1
        return count

class FrozenTableView(QTableView):
    def __init__(self, model, service: SessionService):
        super().__init__()
        self.setModel(model)
        self.service = service
        
        self.setAlternatingRowColors(True)
        # Apply custom alternating color
        self.setStyleSheet("QTableView { alternate-background-color: #d6e4ed; background-color: white; gridline-color: #cccccc; }")
        
        # Enable Mouse Tracking for Hover
        self.setMouseTracking(True)

        # Main Header
        self.header = SessionHeaderView(Qt.Orientation.Horizontal, self)
        self.setHorizontalHeader(self.header)
        
        self.frozen_view = QTableView(self)
        self.frozen_view.setModel(model)
        self.frozen_view.setAlternatingRowColors(True)
        self.frozen_view.setMouseTracking(True) # Enable here too

        # Frozen View Header
        self.frozen_header = SessionHeaderView(Qt.Orientation.Horizontal, self.frozen_view)
        self.frozen_view.setHorizontalHeader(self.frozen_header)
        
        # Set Delegate
        self.delegate = SessionDelegate(self, service=self.service)
        self.setItemDelegate(self.delegate)
        self.frozen_view.setItemDelegate(self.delegate)
        
        # Connect entered signals for hover
        self.entered.connect(self.on_cell_entered)
        self.frozen_view.entered.connect(self.on_cell_entered)
        
        # Connect model reset signal
        model.modelReset.connect(self.update_frozen_view_structure)
        
        self.init_frozen()
        
        self.horizontalHeader().show()
        self.verticalHeader().hide()
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)
        
        # Disallow column resizing by user
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.frozen_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        self.frozen_view.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        self.verticalScrollBar().valueChanged.connect(self.frozen_view.verticalScrollBar().setValue)

    def on_cell_entered(self, index):
        if not index.isValid():
            self.reset_hover()
            return
            
        # Check if column is SONG type (Index 1 to N)
        model = self.model()
        if index.column() < len(model.cols_map):
            col_type, _, _ = model.cols_map[index.column()]
            if col_type == "SONG":
                self.delegate.set_hover(index.row(), index.column())
                self.viewport().update()
                self.frozen_view.viewport().update()
            else:
                self.reset_hover()
        else:
            self.reset_hover()

    def reset_hover(self):
        if self.delegate.hover_row != -1:
            self.delegate.set_hover(-1, -1)
            self.viewport().update()
            self.frozen_view.viewport().update()

    def leaveEvent(self, event):
        self.reset_hover()
        super().leaveEvent(event)

    def init_frozen(self):
        self.frozen_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frozen_view.verticalHeader().hide()
        
        self.frozen_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen_view.show()
        
        self.frozen_view.setStyleSheet("""
            QTableView { 
                border: none; 
                gridline-color: #cccccc;
                background-color: #ffffff;
                alternate-background-color: #d6e4ed;
            }
        """)
        self.setStyleSheet("""
            QTableView { 
                gridline-color: #cccccc;
                background-color: #ffffff;
                alternate-background-color: #d6e4ed;
            }
        """)
        
        self.viewport().stackUnder(self.frozen_view)
        self.update_frozen_view_structure()

    def update_frozen_view_structure(self):
        # 1. Calculate Required Widths First
        col_count = self.model().columnCount()
        fm = self.fontMetrics()
        
        # Fixed Columns
        name_col_width = 100
        count_col_width = 0
        song_col_min_widths = {}
        
        if col_count > 0:
            pass 
            
        # Identify indices
        count_no_vocal_idx = -1
        count_vocal_idx = -1
        
        if col_count >= 3:
            count_no_vocal_idx = col_count - 2
            count_vocal_idx = col_count - 1
            count_col_width = fm.horizontalAdvance("보컬 미포함") + 20 
            
        # Calculate min widths for Song Columns (2 to N-2)
        total_song_min_width = 0
        song_cols = []
        
        for col in range(1, col_count):
            if col == count_no_vocal_idx or col == count_vocal_idx:
                continue
            
            song_cols.append(col)
            
            # (1) Header Width
            header_text = self.model().headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            max_width = 60 # Absolute minimum
            if header_text:
                max_width = max(max_width, fm.horizontalAdvance(header_text) + 20)
            
            # (2) Data Width
            rows = self.model().rowCount()
            for row in range(rows):
                index = self.model().index(row, col)
                data_text = self.model().data(index, Qt.ItemDataRole.DisplayRole)
                if data_text:
                    lines = data_text.split('\n')
                    for line in lines:
                        width = fm.horizontalAdvance(line) + 20
                        max_width = max(max_width, width)
            
            song_col_min_widths[col] = max_width
            total_song_min_width += max_width

        # 2. Check Available Width vs Required Width
        viewport_width = self.viewport().width()
        available_width = viewport_width - name_col_width - (count_col_width * 2)
        
        final_song_widths = {}
        
        if not song_cols:
            pass
        elif available_width > total_song_min_width:
            # Case (1): Fill space
            max_min_width = 0
            if song_col_min_widths:
                max_min_width = max(song_col_min_widths.values())
                
            target_uniform_width = available_width // len(song_cols)
            
            if target_uniform_width >= max_min_width:
                for col in song_cols:
                    final_song_widths[col] = target_uniform_width
            else:
                final_song_widths = song_col_min_widths
        else:
            # Case (2): Scrollbar
            final_song_widths = song_col_min_widths

        # 3. Apply Widths
        if col_count > 0:
            self.setColumnWidth(0, name_col_width)
            self.frozen_view.setColumnWidth(0, name_col_width)
            
        for col in song_cols:
            w = final_song_widths.get(col, 60)
            self.setColumnWidth(col, w)
            self.frozen_view.setColumnWidth(col, w)
            
        if count_no_vocal_idx != -1:
            self.setColumnWidth(count_no_vocal_idx, count_col_width)
            self.setColumnWidth(count_vocal_idx, count_col_width)
            self.frozen_view.setColumnWidth(count_no_vocal_idx, count_col_width)
            self.frozen_view.setColumnWidth(count_vocal_idx, count_col_width)

        for col in range(col_count):
            if col < 1:
                self.frozen_view.setColumnHidden(col, False)
            else:
                self.frozen_view.setColumnHidden(col, True)
                
        self.update_frozen_geometry()

    def update_section_width(self, logicalIndex, oldSize, newSize):
        if logicalIndex < 1:
            self.frozen_view.setColumnWidth(logicalIndex, newSize)
            self.update_frozen_geometry()

    def update_section_height(self, logicalIndex, oldSize, newSize):
        self.frozen_view.setRowHeight(logicalIndex, newSize)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_frozen_view_structure() 

    def moveCursor(self, cursorAction, modifiers):
        current = super().moveCursor(cursorAction, modifiers)
        if (cursorAction == QAbstractItemView.CursorAction.MoveLeft and 
            current.column() < 1 and 
            self.visualRect(current).topLeft().x() < self.frozen_view.columnWidth(0)):
            
            x = self.visualRect(current).topLeft().x()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + x - self.frozen_view.width())
            
        return current

    def update_frozen_geometry(self):
        if self.model().columnCount() >= 1:
            w = self.columnWidth(0)
            self.frozen_view.setGeometry(0, 0, w, self.height())


class SessionWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.table_container = QWidget() 
        layout.addWidget(self.table_container)
        
        # Log and Export Area

        
        log_export_layout = QHBoxLayout()
        
        self.log_area = QScrollArea()
        self.log_area.setFixedHeight(150)
        self.log_container = QWidget()
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_area.setWidget(self.log_container)
        self.log_area.setWidgetResizable(True)
        
        log_export_layout.addWidget(self.log_area)
        
        self.btn_export = QPushButton("내보내기")
        self.btn_export.setFixedWidth(80) # Narrow width
        self.btn_export.setFixedHeight(150) # Same height as log area
        self.btn_export.setStyleSheet("""
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
        
        log_export_layout.addWidget(self.btn_export)
        
        layout.addLayout(log_export_layout)
