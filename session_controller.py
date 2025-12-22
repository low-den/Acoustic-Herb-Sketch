from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget, QMessageBox, QStyleOptionViewItem, QStyle, QProgressDialog
from session_ui import SessionWidget, SessionTableModel, FrozenTableView
from session_service import SessionService
from dialogs import SessionEditDialog
from PyQt6.QtCore import Qt, QRect, QObject, QEvent
from PyQt6.QtGui import QPixmap, QPainter, QColor
import os
from datetime import datetime

class SessionController(QObject):
    def __init__(self, ui: SessionWidget, service: SessionService):
        super().__init__()
        self.ui = ui
        self.service = service
        
        self.model = SessionTableModel(self.service.data_handler)
        self.table_view = FrozenTableView(self.model, self.service)
        
        # Setup Table Layout
        layout = QVBoxLayout(self.ui.table_container)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.table_view)
        
        self.connect_signals()
        self.refresh_data() # Initial refresh
        
    def connect_signals(self):
        self.service.data_changed.connect(self.refresh_data)
        self.table_view.clicked.connect(self.on_cell_clicked)
        self.ui.btn_export.clicked.connect(self.export_image)
        
        # Shortcuts
        self.table_view.installEventFilter(self)
        self.table_view.frozen_view.installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                view = self.table_view
                if source == self.table_view.frozen_view:
                    view = self.table_view.frozen_view
                
                index = view.currentIndex()
                if index.isValid():
                    # Map frozen index to main model index if needed?
                    # Frozen view shares the same model, so index is valid for model.
                    # But col index might be different if frozen columns logic was complex.
                    # Here frozen view shows col 0, main view shows all but hides col 0.
                    # So index is consistent.
                    self.on_cell_clicked(index)
                    return True
        return super().eventFilter(source, event)

    def refresh_data(self):
        # Full refresh of structure (columns/rows might change)
        self.model.refresh_structure()
        self.table_view.update_frozen_geometry()
        
        self.update_log()

    def update_log(self):
        # Clear existing log
        while self.ui.log_layout.count():
            item = self.ui.log_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        # Get warnings
        warnings = self.service.get_all_warnings()
        
        if not warnings:
            self.ui.log_layout.addWidget(QLabel("경고 없음"))
        else:
            for w in warnings:
                lbl = QLabel(w)
                if "배정되지 않았습니다" in w or "너무 적습니다" in w:
                    lbl.setStyleSheet("color: #FF8C00;") # Dark Orange
                elif "너무 많습니다" in w:
                    lbl.setStyleSheet("color: #FF4800;") # Red-Orange
                elif "너무 높습니다" in w:
                    lbl.setStyleSheet("color: blue;")
                else:
                    lbl.setStyleSheet("color: red;")
                self.ui.log_layout.addWidget(lbl)
                
        # Add stretch to push logs to top
        self.ui.log_layout.addStretch()

    def on_cell_clicked(self, index):
        if not index.isValid(): return
        
        col_type, song_id, _ = self.model.cols_map[index.column()]
        
        if col_type == "SONG":
            member = self.model.rows[index.row()]
            if not member: return

            song = next((s for s in self.service.data_handler.songs if s.id == song_id), None)
            
            if not song: return
            
            # Get current assignments for this member in this song
            current_assignments = self.service.get_member_assignments_for_song(song.id, member.id)
            
            dlg = SessionEditDialog(self.ui, member, song, current_assignments, self.service.data_handler.instruments, self.service)
            if dlg.exec():
                new_assignments = dlg.get_selected_sessions()
                ignore_warnings = dlg.cb_ignore_warning.isChecked()
                
                # Always call update to handle potential changes in assignments OR ignore_warnings state
                self.service.update_member_assignments(song.id, member.id, new_assignments, ignore_warnings)

    def export_image(self):
        reply = QMessageBox.question(self.ui, '내보내기', 
                                     "이미지 파일이 'output' 폴더에 저장됩니다. 계속하시겠습니까?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Setup Progress Dialog
        progress = QProgressDialog("이미지를 내보내는 중입니다...", "취소", 0, 100, self.ui)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        # Prepare Directory
        if self.service.data_handler.filepath:
            base_dir = os.path.dirname(self.service.data_handler.filepath)
            output_dir = os.path.join(base_dir, "output")
        else:
            output_dir = "output"
            
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        progress.setValue(10)

        # Generate Filename
        now = datetime.now()
        base_filename = now.strftime("%Y%m%d%H%M_공연세션")
        extension = ".png"
        filename = f"{base_filename}{extension}"
        counter = 1
        while os.path.exists(os.path.join(output_dir, filename)):
            filename = f"{base_filename}_{counter}{extension}"
            counter += 1
        
        full_path = os.path.join(output_dir, filename)

        progress.setValue(20)

        # --- Filter Rows Logic ---
        rows_to_print = [] # List of original row indices
        
        # 1. First pass: Filter by count (Rule 1)
        temp_rows = [] # (original_index, is_separator)
        for r in range(self.model.rowCount()):
            member = self.model.rows[r]
            if member is None: # Separator
                temp_rows.append((r, True))
            else:
                count = self.model.calculate_count(member, True)
                if count > 0:
                    temp_rows.append((r, False))
        
        progress.setValue(30)
        
        # 2. Rule 2 & 3: Handle Separators
        final_rows = []
        for i, (r_idx, is_sep) in enumerate(temp_rows):
            if is_sep:
                # Rule 2: Check if previous was separator
                # Check based on what's added to final_rows
                if final_rows and self.model.rows[final_rows[-1]] is None:
                    continue # Skip consecutive separator
                final_rows.append(r_idx)
            else:
                final_rows.append(r_idx)
        
        # Rule 3: First row separator
        if final_rows and self.model.rows[final_rows[0]] is None:
            final_rows.pop(0)
            
        # Rule 3: Last row separator
        if final_rows and self.model.rows[final_rows[-1]] is None:
            final_rows.pop(-1)
            
        rows_to_print = final_rows

        progress.setValue(40)

        # Calculate Size
        total_width = 0
        for c in range(self.model.columnCount()):
            total_width += self.table_view.columnWidth(c)
            
        header_height = self.table_view.horizontalHeader().height()
        total_height = header_height
        for r in rows_to_print:
            total_height += self.table_view.rowHeight(r)

        # Create Pixmap
        pixmap = QPixmap(total_width, total_height)
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)

        # Set Export Mode
        self.table_view.delegate.export_mode = True

        progress.setValue(50)

        try:
            # Draw Header
            x = 0
            for col in range(self.model.columnCount()):
                w = self.table_view.columnWidth(col)
                rect = QRect(x, 0, w, header_height)
                # Use custom header paint logic
                self.table_view.header.paintSection(painter, rect, col)
                x += w

            # Draw Data
            y = header_height
            for i, row in enumerate(rows_to_print):
                if progress.wasCanceled():
                    break
                
                # Update progress based on row processing (50-80 range)
                progress_val = 50 + int((i / len(rows_to_print)) * 30)
                progress.setValue(progress_val)

                h = self.table_view.rowHeight(row)
                x = 0
                for col in range(self.model.columnCount()):
                    w = self.table_view.columnWidth(col)
                    rect = QRect(x, y, w, h)
                    index = self.model.index(row, col)
                    
                    option = QStyleOptionViewItem()
                    option.rect = rect
                    option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
                    
                    self.table_view.delegate.initStyleOption(option, index)
                    
                    # Draw Cell Content
                    self.table_view.delegate.paint(painter, option, index)
                    
                    # Draw Grid
                    painter.save()
                    painter.setPen(QColor("#cccccc"))
                    painter.drawRect(rect)
                    painter.restore()
                    
                    x += w
                y += h
                
        finally:
            painter.end()
            self.table_view.delegate.export_mode = False

        if progress.wasCanceled():
            return

        progress.setValue(85)

        # Save
        saved_main = False
        if pixmap.save(full_path):
            saved_main = True
        
        progress.setValue(90)
        
        # Export individual feedback images
        feedback_path = self.export_feedback_images(output_dir, base_filename)

        progress.setValue(100)
        
        if saved_main:
            msg = f"저장되었습니다:\n{full_path}"
            if feedback_path:
                msg += f"\n\n피드백 이미지도 저장되었습니다:\n{feedback_path}"
            QMessageBox.information(self.ui, "완료", msg)
        else:
            QMessageBox.warning(self.ui, "실패", "이미지 저장에 실패했습니다.")

    def export_feedback_images(self, output_dir, base_filename):
        # 1. Collect Data
        feedback_data = [] # List of tuples: (song, song_feedback)
        
        # Sort assignments to maintain order if possible, or just iterate
        # Better to iterate songs -> sessions to keep song order
        
        for song in self.service.data_handler.songs:
            song_feedback = []
            for session in song.sessions:
                # Find assignment
                assign = next((a for a in self.service.data_handler.assignments 
                               if a.song_id == song.id and a.session_id == session.id), None)
                if not assign or not assign.member_id: continue
                
                # Skip if warnings are ignored
                if assign.ignore_warnings: continue
                
                member = next((m for m in self.service.data_handler.members if m.id == assign.member_id), None)
                if not member: continue
                
                warnings = self.service.validate_assignment(member, song, session)
                is_insufficient = any("모자랍니다" in w or "낮습니다" in w or "부족합니다" in w for w in warnings)
                
                if is_insufficient:
                    inst = next((i for i in self.service.data_handler.instruments if i.id == session.instrument_id), None)
                    inst_name = inst.name if inst else ""
                    
                    req_str = ""
                    if inst_name == "보컬/랩":
                        req_str = f"최고음 '{session.difficulty_param}'"
                    else:
                        try:
                            max_beat = int(session.difficulty_param)
                            target_bpm = (song.bpm * max_beat) / 16
                            req_str = f"16비트 {target_bpm:.0f}bpm"
                        except:
                            req_str = "알 수 없음"
                    
                    song_feedback.append((member.name, req_str))
            
            if song_feedback:
                feedback_data.append((song, song_feedback))

        if not feedback_data:
            return None

        # 2. Draw Image
        width = 420
        margin = 30
        
        # Calculate Height
        total_height = 150 # Header + Margins
        for song, members in feedback_data:
            total_height += 30 + (len(members) * 30) + 15
        
        pixmap = QPixmap(width, total_height)
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)
        
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QColor(0, 0, 0)) # Black text
            
            y = margin + 20
            
            # Header
            font = painter.font()
            orig_size = font.pointSize()
            
            font.setPointSize(orig_size + 1)
            painter.setFont(font)
            painter.drawText(margin, y, "아래 부원들은 조금 더 어려운 곡을 맡게 되었어요! 🥺")
            y += 30
            
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(margin, y, "스케일이랑 하농 연습 열심히 해서 💪")
            y += 30
            painter.drawText(margin, y, "목표 BPM까지 기본기를 탄탄하게 다져봐요! 파이팅 🔥")
            y += 50
            
            font.setPointSize(orig_size) # Reset size
            
            # Content
            for song, members in feedback_data:
                # Song Title
                font.setBold(True)
                painter.setFont(font)
                song_title = f"[{song.title}]"
                painter.drawText(margin, y, song_title)
                y += 30
                
                # Members
                for m_name, req in members:
                    # Draw "- " (Normal)
                    font.setBold(False)
                    painter.setFont(font)
                    prefix = "- "
                    painter.drawText(margin, y, prefix)
                    prefix_w = painter.fontMetrics().horizontalAdvance(prefix)
                    
                    # Draw Name (Bold)
                    font.setBold(True)
                    painter.setFont(font)
                    name_str = f"{m_name}: "
                    painter.drawText(margin + prefix_w, y, name_str)
                    name_w = painter.fontMetrics().horizontalAdvance(name_str)
                    
                    # Draw Req (Normal)
                    font.setBold(False)
                    painter.setFont(font)
                    painter.drawText(margin + prefix_w + name_w, y, req)
                    
                    y += 30
                    
                y += 15 # Spacing between songs
                
        finally:
            painter.end()
            
        # 3. Save
        feedback_filename = f"{base_filename}_피드백.png"
        full_path = os.path.join(output_dir, feedback_filename)
        if pixmap.save(full_path):
            return full_path
        return None
