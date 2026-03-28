from tech_ui import TechWidget
from tech_service import TechService
from song_service import SongService
from PyQt6.QtWidgets import (QTableWidgetItem, QSpinBox, QTreeWidgetItem, QMessageBox, 
                             QListWidgetItem, QInputDialog, QFileDialog, QDialog, 
                             QVBoxLayout, QTextEdit, QPushButton, QLabel)
from PyQt6.QtCore import Qt, QSizeF, QObject, QEvent
from PyQt6.QtGui import QPdfWriter, QPainter, QPageSize, QPageLayout, QColor, QFont, QTextDocument, QPixmap, QTextCursor, QTextCharFormat
from dialogs import CueSheetEditDialog, SoundDesignDialog
from models import CueSection, Equipment, InstrumentCategory
import copy

class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class TechController(QObject):
    def __init__(self, ui: TechWidget, service: TechService, song_service: SongService):
        super().__init__()
        self.ui = ui
        self.service = service
        self.song_service = song_service
        
        self.connect_signals()
        self.refresh_ui()

    def connect_signals(self):
        self.service.data_changed.connect(self.refresh_ui)
        self.song_service.data_changed.connect(self.refresh_songs)
        
        # Cue Sheet Signals
        self.ui.song_list.itemSelectionChanged.connect(self.on_song_selected)
        self.ui.btn_cue_add.clicked.connect(self.add_cue_section)
        self.ui.btn_cue_edit.clicked.connect(self.edit_cue_section)
        self.ui.btn_cue_del.clicked.connect(self.delete_cue_section)
        self.ui.btn_cue_up.clicked.connect(self.move_cue_up)
        self.ui.btn_cue_down.clicked.connect(self.move_cue_down)
        
        # Double click to edit
        self.ui.cue_table.itemDoubleClicked.connect(self.on_table_double_clicked)
        
        # Equipment Signals
        self.ui.btn_eq_add.clicked.connect(self.add_equipment)
        self.ui.btn_eq_del.clicked.connect(self.delete_equipment)
        self.ui.btn_eq_auto.clicked.connect(self.auto_calc_equipment)
        self.ui.btn_export_cue.clicked.connect(self.export_pdf)
        
        # Sound Design Dialog
        self.ui.btn_sound_design.clicked.connect(self.open_sound_design_dialog)
        
        # Memo Signal
        self.ui.memo_edit.textChanged.connect(self.update_performance_memo)
        
        # Shortcuts
        self.ui.eq_table.installEventFilter(self)
        self.ui.cue_table.installEventFilter(self)

    def open_sound_design_dialog(self):
        dlg = SoundDesignDialog(self.service.data_handler, self.ui)
        if dlg.exec():
            # Data is already saved to data_handler on accept
            self.service.data_changed.emit()

    def update_sound_setting(self, key, value):
        self.service.update_sound_design_setting(key, value)

    def update_performance_memo(self):
        text = self.ui.memo_edit.toPlainText()
        # Avoid creating command if text hasn't changed (loop prevention)
        if text != self.service.data_handler.performance_memo:
            self.service.update_performance_memo(text)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            # Equipment Table
            if source == self.ui.eq_table:
                if event.key() == Qt.Key.Key_Delete:
                    self.delete_equipment()
                    return True
            
            # Cue Table
            elif source == self.ui.cue_table:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self.edit_cue_section()
                    return True
                elif event.key() == Qt.Key.Key_Delete:
                    self.delete_cue_section()
                    return True
                    
        return super().eventFilter(source, event)

    def refresh_ui(self):
        # Refresh Equipment List
        self.ui.eq_table.setRowCount(0)
        
        for eq in self.service.data_handler.equipments:
            row = self.ui.eq_table.rowCount()
            self.ui.eq_table.insertRow(row)
            
            # Name (Read-only)
            name_item = QTableWidgetItem(eq.name)
            # Explicitly cast to str just in case, and verify it's not empty
            eid = str(eq.id) if eq.id else ""
            name_item.setData(Qt.ItemDataRole.UserRole, eid)
            name_item.setFlags(name_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.ui.eq_table.setItem(row, 0, name_item)
            
            # Owned (SpinBox)
            sb_owned = NoScrollSpinBox()
            sb_owned.setRange(0, 999)
            sb_owned.setValue(eq.owned_count)
            sb_owned.valueChanged.connect(lambda v, e=eq: self.service.update_equipment(e.id, "owned_count", v))
            
            # Check for shortage
            if eq.owned_count < eq.required_count:
                sb_owned.setStyleSheet("background-color: rgb(255, 200, 200);")
            else:
                sb_owned.setStyleSheet("")
                
            self.ui.eq_table.setCellWidget(row, 1, sb_owned)
            
            # Required (SpinBox)
            sb_req = NoScrollSpinBox()
            sb_req.setRange(0, 999)
            sb_req.setValue(eq.required_count)
            sb_req.valueChanged.connect(lambda v, e=eq: self.service.update_equipment(e.id, "required_count", v))
            self.ui.eq_table.setCellWidget(row, 2, sb_req)
            
        # Refresh Song List (Cue Sheet)
        self.refresh_songs()
        
        # Restore Performance Memo
        # Block signal to prevent feedback loop or unnecessary updates during load
        self.ui.memo_edit.blockSignals(True)
        self.ui.memo_edit.setText(self.service.data_handler.performance_memo)
        self.ui.memo_edit.blockSignals(False)

    def refresh_songs(self):
        current_song_id = None
        if self.ui.song_list.currentItem():
            current_song_id = self.ui.song_list.currentItem().data(Qt.ItemDataRole.UserRole)
            
        self.ui.song_list.clear()
        
        for song in self.service.data_handler.songs:
            item = QListWidgetItem(song.title)
            item.setData(Qt.ItemDataRole.UserRole, song.id)
            self.ui.song_list.addItem(item)
            
            if song.id == current_song_id:
                self.ui.song_list.setCurrentItem(item)

    def on_song_selected(self):
        item = self.ui.song_list.currentItem()
        if not item:
            self.ui.cue_table.setRowCount(0)
            # Memo is global, do not clear
            return
            
        song_id = item.data(Qt.ItemDataRole.UserRole)
        song = next((s for s in self.service.data_handler.songs if s.id == song_id), None)
        if not song: return
        
        self.refresh_cue_table(song)


    def add_cue_section(self):
        item = self.ui.song_list.currentItem()
        if not item: return
        
        song_id = item.data(Qt.ItemDataRole.UserRole)
        song = next((s for s in self.service.data_handler.songs if s.id == song_id), None)
        if not song: return

        # Determine target section based on selection
        target_section = None
        
        table_items = self.ui.cue_table.selectedItems()
        if table_items:
            # Get data from first selected item
            first_item = table_items[0]
            row = self.ui.cue_table.row(first_item)
            sec_item = self.ui.cue_table.item(row, 0)
            section_data = sec_item.data(Qt.ItemDataRole.UserRole)
            
            if isinstance(section_data, CueSection):
                target_section_id = section_data.id
                target_section = next((s for s in song.cue_sections if s.id == target_section_id), None)
        
        # Open Dialog (target_section can be None if nothing selected)
        dlg = CueSheetEditDialog(self.ui, song, section_data=target_section, service=self.service)
        if dlg.exec():
            # Dialog returns (section_name, entry_data_dict)
            result = dlg.get_data()
            if not result: return
            
            # Use logic to update song
            self.add_cue_section_logic(result, song)

    def edit_cue_section(self):
        item = self.ui.song_list.currentItem()
        if not item: return
        song_id = item.data(Qt.ItemDataRole.UserRole)
        song = next((s for s in self.service.data_handler.songs if s.id == song_id), None)
        if not song: return

        table_items = self.ui.cue_table.selectedItems()
        if not table_items:
            QMessageBox.warning(self.ui, "선택", "섹션 내 항목을 선택해주세요")
            return
            
        first_item = table_items[0]
        # Check if it is a Section selection or Entry selection
        # Logic: If user clicked Column 0, and it is spanned, it's a section select?
        # Or if the item data in Col 1 is None?
        
        # In refresh_cue_table:
        # Col 1 (Instrument) has (sec_id, entry_id) in UserRole.
        # If entry doesn't exist (empty section), Col 1 has None? No, we didn't set UserRole for empty placeholder rows in Col 1.
        
        inst_item = self.ui.cue_table.item(self.ui.cue_table.row(first_item), 1)
        entry_info = inst_item.data(Qt.ItemDataRole.UserRole)
        
        if not entry_info:
             # This means it's a section header row with no entries, or user selected Col 0 of a multi-row section
             # But wait, if user selects Col 0, table selects the whole row.
             # If it's a spanned cell, selecting it selects the top row?
             
             # If entry_info is None, it's likely just a section header or empty placeholder.
             QMessageBox.warning(self.ui, "선택", "섹션 내 항목을 선택해주세요")
             return
             
        sec_id, entry_id = entry_info
        
        # Find data
        target_section = next((s for s in song.cue_sections if s.id == sec_id), None)
        if not target_section: return
        
        import json
        note_json = target_section.instrument_notes.get(entry_id)
        if not note_json: return
        
        existing_data = json.loads(note_json)
        
        # Open Dialog in "Edit Mode" -> Pre-fill data
        # CueSheetEditDialog supports `section_data`, but does it support filling fields?
        # It seems we need to pass existing_data to it.
        # Currently it doesn't accept `initial_data`. We might need to modify Dialog or hack it.
        # Or we can just set the values after init if we have access.
        
        dlg = CueSheetEditDialog(self.ui, song, section_data=target_section, service=self.service)
        
        # Manually pre-fill dialog widgets
        # CueSheetEditDialog uses section_list (QListWidget) for section selection
        
        # Select the section in the list
        items = dlg.section_list.findItems(target_section.name, Qt.MatchFlag.MatchExactly)
        if items:
            dlg.section_list.setCurrentItem(items[0])
            dlg.on_section_selected(items[0])
        
        # Fill input fields
        dlg.input_inst_name.setText(existing_data.get('instrument_name', ''))
        
        if existing_data.get('use_effect'):
            dlg.cb_effect.setChecked(True)
            dlg.input_effect_name.setText(existing_data.get('effect_name', ''))
            lvl = existing_data.get('effect_level')
            if lvl:
                btn = dlg.group_level.button(lvl)
                if btn: btn.setChecked(True)
        else:
            dlg.cb_effect.setChecked(False)
            
        dlg.edit_memo.setPlainText(existing_data.get('memo', ''))

        if dlg.exec():
            result = dlg.get_data()
            if not result: return
            
            section_name, entry_data = result
            
            # Update Logic
            new_song = copy.deepcopy(song)
            
            # If section name changed, we might need to move it to another section?
            # "섹션 내 항목을 선택한 상태에서만 해당 항목의 큐시트 편집" implies modifying THAT entry.
            # If user changes section name in combo, it effectively moves it to that section.
            
            target_sec_new = next((s for s in new_song.cue_sections if s.name == section_name), None)
            if not target_sec_new:
                 # Create new section if not exists? Or revert to old?
                 # Should exist as per dialog logic.
                 target_sec_new = CueSection(name=section_name)
                 new_song.cue_sections.append(target_sec_new)
            
            # If section changed, remove from old, add to new.
            # If same section, just update.
            
            old_section = next((s for s in new_song.cue_sections if s.id == sec_id), None)
            
            if old_section.id == target_sec_new.id:
                # Same section, update in place (preserve order)
                # Python 3.7+ dicts preserve insertion order. 
                # We just update value.
                old_section.instrument_notes[entry_id] = json.dumps(entry_data, ensure_ascii=False)
            else:
                # Move to new section
                if entry_id in old_section.instrument_notes:
                    del old_section.instrument_notes[entry_id]
                
                # Add to new section (at end)
                # Generate new ID or keep old? New ID is safer to avoid conflicts?
                # Keep old ID is fine if unique across song? UUID is unique globally.
                target_sec_new.instrument_notes[entry_id] = json.dumps(entry_data, ensure_ascii=False)
                
            self.song_service.update_song(song, new_song)

    def add_cue_section_logic(self, result, song):
        if not result: return
        section_name, entry_data = result
        new_song = copy.deepcopy(song)
        target_section = next((s for s in new_song.cue_sections if s.name == section_name), None)
        
        # Should not happen given we passed existing section, but for safety
        if not target_section:
            target_section = CueSection(name=section_name)
            new_song.cue_sections.append(target_section)
        
        import uuid
        import json
        entry_id = str(uuid.uuid4())
        target_section.instrument_notes[entry_id] = json.dumps(entry_data, ensure_ascii=False)
        self.song_service.update_song(song, new_song)

    def on_table_double_clicked(self, item):
        self.edit_cue_section()

    def delete_cue_section(self):
        item = self.ui.song_list.currentItem()
        if not item: return
        song_id = item.data(Qt.ItemDataRole.UserRole)
        song = next((s for s in self.service.data_handler.songs if s.id == song_id), None)
        if not song: return

        table_items = self.ui.cue_table.selectedItems()
        if not table_items:
            QMessageBox.warning(self.ui, "선택", "삭제할 섹션 또는 항목을 선택해주세요")
            return
            
        first_item = table_items[0]
        row = self.ui.cue_table.row(first_item)
        
        # Determine if Section or Entry
        inst_item = self.ui.cue_table.item(row, 1)
        entry_info = inst_item.data(Qt.ItemDataRole.UserRole)
        
        new_song = copy.deepcopy(song)
        
        if entry_info:
            # Entry Selected
            sec_id, entry_id = entry_info
            
            reply = QMessageBox.question(self.ui, '삭제', '정말 삭제하시겠습니까?', 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes: return
            
            target_section = next((s for s in new_song.cue_sections if s.id == sec_id), None)
            if target_section and entry_id in target_section.instrument_notes:
                del target_section.instrument_notes[entry_id]
                self.song_service.update_song(song, new_song)
                
        else:
            # Section Selected (No entry info in Col 1 means it's a section row with no entries OR user selected the Section cell of a spanned row?)
            # Wait, if user selects Section cell of a spanned row, Col 1 still has data.
            # But `first_item` is the clicked item.
            # If user clicked Col 0 (Section Name), `first_item` is Col 0.
            # We need to check if we should delete Section or Entry.
            # Prompt: "섹션을 선택한 상태는 해당 섹션 전체 삭제 ... 항목을 선택한 상태에서는 해당 큐시트 항목만 삭제"
            
            # If user clicks Col 0 (Section), we consider it "Section Selected".
            # If user clicks Col 1, 2, 3 (Entry), we consider it "Entry Selected".
            
            col = self.ui.cue_table.column(first_item)
            
            if col == 0:
                # Section Delete
                sec_item = self.ui.cue_table.item(row, 0)
                section_data = sec_item.data(Qt.ItemDataRole.UserRole)
                if not section_data: return # Should not happen

                # Check if Default Section? Prompt didn't specify non-deletable here but usually we protect defaults?
                # Prompt: "섹션을 모두 삭제합니다. 정말 삭제하시겠습니까? 필요"
                # "디폴트 섹션 목록... 삭제할 수 없어야 해" (Previous prompt)
                # So we must check.
                
                # Check against DEFAULT_SECTION_NAMES? Or was it protected in Dialog only?
                # "디폴트 섹션 목록... 삭제할 수 없어야 해" -> likely means from the song structure too?
                # Or just cannot remove from the 'List' in dialog?
                # Usually it means we cannot remove it from the song.
                # BUT, `cue_sections` in Song are instances.
                # If we delete "Intro" section from Song, is it gone forever?
                # The dialog ensures defaults are always in the list.
                # So if we delete here, it's just removing DATA from song.
                # Re-adding it later is possible.
                # However, if "삭제할 수 없어야 해" applies to existence in Song, we should block.
                # But typically a Cue Sheet might not use all sections.
                # Let's assume "Deletion" here means "Clear all entries in this section" or "Remove section from view".
                # If we remove from `song.cue_sections`, it disappears from view.
                # Dialog will show it again if we open it? Yes, ensure_defaults adds it back.
                # So safe to delete from `song.cue_sections`?
                # Wait, if I delete it, all notes inside are gone.
                # Let's proceed with deletion but warn.
                
                # ACTUALLY, "디폴트 섹션 목록... 삭제할 수 없어야 해" was about the LIST in Dialog.
                # Here we are in Tech Rider UI.
                # "섹션을 모두 삭제합니다" implies deleting the section + all its contents.
                
                reply = QMessageBox.question(self.ui, '삭제', '섹션을 모두 삭제합니다. 정말 삭제하시겠습니까?', 
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply != QMessageBox.StandardButton.Yes: return
                
                # Delete section from song
                new_song.cue_sections = [s for s in new_song.cue_sections if s.id != section_data.id]
                self.song_service.update_song(song, new_song)
                
            else:
                # Entry Delete (User clicked Col 1,2,3)
                # But we handled this in `if entry_info:` block?
                # If `entry_info` is present, we deleted entry.
                # If `entry_info` is NOT present (e.g. empty placeholder row), nothing to delete.
                if not entry_info:
                     QMessageBox.warning(self.ui, "선택", "삭제할 항목이 없습니다.")
                     return

    def refresh_cue_table(self, song):
        self.ui.cue_table.setRowCount(0)
        import json
        
        row_idx = 0
        for section in song.cue_sections:
            entries = []
            # Collect entries
            for entry_id, note_json in section.instrument_notes.items():
                try:
                    data = json.loads(note_json)
                    entries.append((entry_id, data))
                except:
                    continue
            
            if not entries:
                self.ui.cue_table.insertRow(row_idx)
                # Section Name
                sec_item = QTableWidgetItem(section.name)
                sec_item.setData(Qt.ItemDataRole.UserRole, section) # Store Section object
                sec_item.setFlags(sec_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.ui.cue_table.setItem(row_idx, 0, sec_item)
                
                # Others empty
                for c in range(1, 4):
                    empty = QTableWidgetItem("")
                    empty.setFlags(empty.flags() ^ Qt.ItemFlag.ItemIsEditable)
                    self.ui.cue_table.setItem(row_idx, c, empty)
                    
                row_idx += 1
                continue

            # If entries exist
            start_row = row_idx
            for entry_id, data in entries:
                self.ui.cue_table.insertRow(row_idx)
                
                # Section Name (will span later)
                sec_item = QTableWidgetItem(section.name)
                sec_item.setData(Qt.ItemDataRole.UserRole, section)
                sec_item.setFlags(sec_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.ui.cue_table.setItem(row_idx, 0, sec_item)
                
                # Instrument
                inst_name = data.get('instrument_name', '')
                inst_item = QTableWidgetItem(inst_name)
                inst_item.setData(Qt.ItemDataRole.UserRole, (section.id, entry_id)) # Store (sec_id, entry_id)
                inst_item.setFlags(inst_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.ui.cue_table.setItem(row_idx, 1, inst_item)
                
                # Effect
                effect_str = ""
                if data.get('use_effect'):
                    effect_name = data.get('effect_name')
                    effect_str = effect_name if effect_name else "이펙트"
                    
                    # Level?
                    lvl = data.get('effect_level')
                    levels = ["연하게", "살짝 연하게", "적당히", "살짝 진하게", "진하게"]
                    if lvl and 1 <= lvl <= 5:
                        effect_str += f" {levels[lvl-1]}"
                
                eff_item = QTableWidgetItem(effect_str)
                eff_item.setFlags(eff_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.ui.cue_table.setItem(row_idx, 2, eff_item)
                
                # Memo
                memo = data.get('memo', '')
                memo_item = QTableWidgetItem(memo)
                memo_item.setFlags(memo_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.ui.cue_table.setItem(row_idx, 3, memo_item)
                
                row_idx += 1
            
            # Span Section Column
            if len(entries) > 1:
                self.ui.cue_table.setSpan(start_row, 0, len(entries), 1)

        self.ui.cue_table.resizeRowsToContents()

    def move_cue_up(self):
        self.move_cue(-1)

    def move_cue_down(self):
        self.move_cue(1)

    def move_cue(self, direction):
        item = self.ui.song_list.currentItem()
        if not item: return
        song_id = item.data(Qt.ItemDataRole.UserRole)
        song = next((s for s in self.service.data_handler.songs if s.id == song_id), None)
        
        table_items = self.ui.cue_table.selectedItems()
        if not table_items: return
        
        first_item = table_items[0]
        col = self.ui.cue_table.column(first_item)
        row = self.ui.cue_table.row(first_item)
        
        new_song = copy.deepcopy(song)
        
        if col == 0:
            # Section Move
            sec_item = self.ui.cue_table.item(row, 0)
            section_data = sec_item.data(Qt.ItemDataRole.UserRole)
            
            idx = next((i for i, s in enumerate(new_song.cue_sections) if s.id == section_data.id), -1)
            if idx == -1: return
            
            new_idx = idx + direction
            if 0 <= new_idx < len(new_song.cue_sections):
                new_song.cue_sections[idx], new_song.cue_sections[new_idx] = new_song.cue_sections[new_idx], new_song.cue_sections[idx]
                self.song_service.update_song(song, new_song)
                
                # Restore selection?
                # Ideally yes, but refresh_ui clears it.
        else:
            # Entry Move
            inst_item = self.ui.cue_table.item(row, 1)
            entry_info = inst_item.data(Qt.ItemDataRole.UserRole)
            if not entry_info: return
            
            sec_id, entry_id = entry_info
            target_section = next((s for s in new_song.cue_sections if s.id == sec_id), None)
            if not target_section: return
            
            # Reorder instrument_notes
            # Dicts are ordered in Python 3.7+.
            keys = list(target_section.instrument_notes.keys())
            try:
                idx = keys.index(entry_id)
            except ValueError:
                return
                
            new_idx = idx + direction
            if 0 <= new_idx < len(keys):
                # Swap keys
                keys[idx], keys[new_idx] = keys[new_idx], keys[idx]
                
                # Reconstruct dict
                new_notes = {k: target_section.instrument_notes[k] for k in keys}
                target_section.instrument_notes = new_notes
                
                self.song_service.update_song(song, new_song)

    # Equipment Methods
    def add_equipment(self):
        name, ok = QInputDialog.getText(self.ui, "장비 추가", "장비 이름을 입력하세요:")
        if ok and name.strip():
            self.service.add_equipment(name.strip())

    def delete_equipment(self):
        # Prefer currentRow() as we set SelectRows behavior
        current_row = self.ui.eq_table.currentRow()
        
        # Fallback to selectedItems if currentRow is invalid (-1)
        if current_row == -1:
            selected_items = self.ui.eq_table.selectedItems()
            if selected_items:
                current_row = self.ui.eq_table.row(selected_items[0])
        
        if current_row == -1:
            QMessageBox.warning(self.ui, "선택", "삭제할 장비를 선택해주세요.")
            return

        item = self.ui.eq_table.item(current_row, 0)
        if not item:
            QMessageBox.warning(self.ui, "오류", "선택한 행의 데이터를 찾을 수 없습니다.")
            return
            
        eq_id = item.data(Qt.ItemDataRole.UserRole)
        
        # Debugging aid
        if not eq_id:
             QMessageBox.warning(self.ui, "오류", f"장비 ID가 유효하지 않습니다. (Row: {current_row})")
             return

        eq = next((e for e in self.service.data_handler.equipments if e.id == eq_id), None)
        if not eq:
            # Show debug info
            all_ids_sample = [e.id for e in self.service.data_handler.equipments[:3]]
            QMessageBox.warning(self.ui, "오류", f"해당 장비 데이터(ID:{eq_id})를 찾을 수 없습니다.\n현재 로드된 장비 수: {len(self.service.data_handler.equipments)}")
            return

        if getattr(eq, 'is_default', False):
            QMessageBox.warning(self.ui, "경고", "기본(디폴트) 장비는 삭제할 수 없습니다.")
            return

        reply = QMessageBox.question(self.ui, '삭제', '정말 삭제하시겠습니까?', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.service.delete_equipment(eq_id)

    def auto_calc_equipment(self):
        # Gather Settings from UI - NOW FROM DataHandler (Dialog Result)
        settings = self.service.data_handler.sound_design_settings
        
        # We need to map the new flexible settings back to what TechService expects (eg1_cable, etc.)
        # TechService.calculate_needs uses specific keys.
        # SoundDesignDialog attempts to save these keys if they match the legacy pattern (Electric Guitar #1 -> eg1_cable)
        # So we can just pass the settings dict.
        
        # Note: If user hasn't opened dialog, settings might be empty or old.
        # TechService defaults handle missing keys usually.
        
        # Validate critical settings if needed?
        # TechService checks specific keys.
        
        # Confirm Calculation
        reply = QMessageBox.question(self.ui, '자동 계산', 
                                     '필요 개수의 현재 값이 모두 지워지고 자동으로 계산됩니다. 진행하시겠습니까?', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        success, log = self.service.calculate_needs(settings)
        
        if success:
            # Show calculation result log
            if log:
                log_msg = "\n\n".join(log)
                
                dialog = QDialog(self.ui)
                dialog.setWindowTitle("자동 계산 결과")
                dialog.resize(600, 400)
                
                layout = QVBoxLayout(dialog)
                layout.addWidget(QLabel("악기별 계산 결과:"))
                
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setText(log_msg)
                layout.addWidget(text_edit)
                
                btn_ok = QPushButton("확인")
                btn_ok.clicked.connect(dialog.accept)
                layout.addWidget(btn_ok)
                
                dialog.exec()
            else:
                QMessageBox.information(self.ui, "자동 계산", "계산된 악기가 없습니다.")
        else:
            QMessageBox.warning(self.ui, "오류", "계산 중 오류가 발생했습니다.")

    def reset_equipment(self):
        pass # Removed button

    def export_pdf(self):
        import os
        filename, _ = QFileDialog.getSaveFileName(self.ui, "테크라이더 내보내기", "테크라이더.pdf", "PDF Files (*.pdf)")
        if not filename:
            return

        if os.path.exists(filename):
            reply = QMessageBox.warning(self.ui, "파일 존재함", 
                                        f"'{os.path.basename(filename)}' 파일이 이미 존재합니다.\n덮어쓰시겠습니까?\n\n(아니오를 선택하면 저장이 취소됩니다. 다른 이름으로 다시 시도해주세요.)", 
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
            
            # Check if file is open (locked)
            try:
                with open(filename, 'a'):
                    pass
            except PermissionError:
                QMessageBox.critical(self.ui, "파일 열려있음", 
                                     f"'{os.path.basename(filename)}' 파일이 다른 프로그램에서 열려있어 덮어쓸 수 없습니다.\n파일을 닫고 다시 시도해주세요.")
                return
            except Exception as e:
                QMessageBox.critical(self.ui, "오류", f"파일 접근 중 오류가 발생했습니다:\n{str(e)}")
                return

        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setResolution(300) # 300 DPI for high quality
        
        painter = QPainter(writer)
        
        try:
            # Constants for layout
            page_width = writer.width()
            page_height = writer.height()
            margin = 120 # Very narrow margin
            content_width = page_width - (2 * margin)
            
            y = margin
            line_height = 100
            
            # Set font to 돋움
            font = QFont("돋움")
            font.setPointSize(10)
            painter.setFont(font)
            base_size = font.pointSize()
            
            # --- Cover Page ---
            # Logo
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
            try:
                logo_path = self.ui.window().get_resource_path("logo.png")
            except:
                pass
            
            logo_bottom_y = page_height // 2
            if os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    # Scale logo 2x bigger (max width 3600)
                    max_logo_w = 3600
                    if pixmap.width() > max_logo_w:
                        pixmap = pixmap.scaledToWidth(max_logo_w, Qt.TransformationMode.SmoothTransformation)
                    else:
                        pixmap = pixmap.scaledToWidth(min(pixmap.width() * 2, max_logo_w), Qt.TransformationMode.SmoothTransformation)
                    
                    logo_x = (page_width - pixmap.width()) // 2
                    logo_y = (page_height // 2) - (pixmap.height() // 2) - 80
                    painter.drawPixmap(int(logo_x), int(logo_y), pixmap)
                    logo_bottom_y = logo_y + pixmap.height()
            
            # Title text: centered between logo bottom and page bottom
            font.setPointSize(base_size + 12)
            font.setBold(True)
            painter.setFont(font)
            title_y = (logo_bottom_y + page_height) // 2 - line_height
            painter.drawText(0, int(title_y), int(page_width), int(line_height * 3), 
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, 
                           "[ 어쿠스틱 허브 테크라이더 ]")
            
            # Reset font
            font.setPointSize(base_size)
            font.setBold(False)
            painter.setFont(font)
            
            # --- 1. 곡 순서 및 악기 (New Page) ---
            writer.newPage()
            y = margin
            
            # Title
            font.setPointSize(base_size + 2)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "1. 곡 순서 및 악기")
            y += line_height * 1.5
            
            # [전체] Summary
            font.setPointSize(base_size)
            max_inst_usage = {}
            for song in self.service.data_handler.songs:
                current_counts = {}
                for sess in song.sessions:
                    inst = next((i for i in self.service.data_handler.instruments if i.id == sess.instrument_id), None)
                    if inst:
                        current_counts[inst.name] = current_counts.get(inst.name, 0) + 1
                
                for name, count in current_counts.items():
                    max_inst_usage[name] = max(max_inst_usage.get(name, 0), count)
            
            # Format string with Category Grouping
            category_order = {
                InstrumentCategory.GUITAR.value: 0,
                InstrumentCategory.PIANO.value: 1,
                InstrumentCategory.PERCUSSION.value: 2,
                InstrumentCategory.WIND.value: 3,
                InstrumentCategory.STRING.value: 4,
                InstrumentCategory.ETC.value: 5
            }
            
            summary_items = []
            for name, count in max_inst_usage.items():
                if count > 0:
                    inst_obj = next((i for i in self.service.data_handler.instruments if i.name == name), None)
                    cat_name = inst_obj.category if inst_obj else InstrumentCategory.ETC.value
                    sort_idx = category_order.get(cat_name, 99)
                    summary_items.append((sort_idx, name, count))

            summary_items.sort(key=lambda x: (x[0], x[1]))
            summary_list = [f"{item[1]} {item[2]}개" for item in summary_items]
            
            if summary_list:
                font.setBold(True)
                painter.setFont(font)
                summary_text = "[전체] " + ", ".join(summary_list)
                
                rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, summary_text)
                painter.drawText(int(margin), int(y), int(content_width), int(rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, summary_text)
                
                y += rect.height() + 50

            # Numbering symbols
            num_symbols = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
                           "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"]

            # Content - Songs with numbering (tab separated)
            tab_x = margin + 1200  # Fixed tab stop for instrument column
            for song_idx, song in enumerate(self.service.data_handler.songs):
                num = num_symbols[song_idx] if song_idx < len(num_symbols) else f"({song_idx+1})"
                
                font.setBold(True)
                painter.setFont(font)
                song_text = f"{num} {song.title}"
                painter.drawText(int(margin), int(y), int(tab_x - margin), int(line_height), Qt.AlignmentFlag.AlignLeft, song_text)
                
                # Instruments (after tab)
                font.setBold(False)
                painter.setFont(font)
                
                inst_list = []
                for sess in song.sessions:
                    inst = next((i for i in self.service.data_handler.instruments if i.id == sess.instrument_id), None)
                    if inst:
                        inst_list.append(inst.name)
                
                inst_text = ", ".join(inst_list)
                remaining_w = content_width - (tab_x - margin)
                
                text_rect = painter.boundingRect(int(tab_x), int(y), int(remaining_w), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, inst_text)
                painter.drawText(int(tab_x), int(y), int(remaining_w), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, inst_text)
                
                y += text_rect.height() + 50
                
                if y > page_height - margin:
                    writer.newPage()
                    y = margin

            # --- 2. 필요한 장비 (New Page) ---
            writer.newPage()
            y = margin
            
            # Title
            font.setPointSize(base_size + 2)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "2. 필요한 장비")
            y += line_height * 1.5
            
            # Pre-check for Drum Mic Set to ask input
            font.setPointSize(base_size)
            crash_cymbal_count = 0
            drum_mic_needed_flag = False
            for eq in self.service.data_handler.equipments:
                if eq.name == "드럼 마이크 세트" and (eq.required_count - eq.owned_count) > 0:
                    drum_mic_needed_flag = True
                    break
            
            if drum_mic_needed_flag:
                val, ok = QInputDialog.getInt(self.ui, "크래시 심벌 개수", 
                                              "크래시 심벌 개수를 입력해 주세요.\n(오존, 차이나, 스플래시 심벌 등 이펙트 심벌을 포함한 개수를 입력해주세요.)", 
                                              value=2, min=0, max=20)
                if ok:
                    crash_cymbal_count = val

            # Build instrument usage map for DI/핀마이크 annotations
            settings = self.service.data_handler.sound_design_settings
            di_inst_map = {}  # eq_name -> list of instrument names
            pinmic_instruments = []
            
            for inst in self.service.data_handler.instruments:
                inst_name = inst.name
                # Check max usage
                inst_max = max_inst_usage.get(inst_name, 0)
                if inst_max == 0:
                    continue
                    
                for i in range(inst_max):
                    key = f"{inst_name}_{i}_conn"
                    conn = settings.get(key, 0)
                    
                    # Check guitar family for 패시브 DI
                    guitar_family_names = set()
                    for gi in self.service.data_handler.instruments:
                        if gi.category == InstrumentCategory.GUITAR.value and gi.name not in ["일렉기타", "베이스"]:
                            guitar_family_names.add(gi.name)
                    
                    if inst_name in guitar_family_names and conn == 3:
                        di_inst_map.setdefault("패시브 DI 모노", []).append(inst_name)
                    elif inst_name in ["디지털 피아노", "신디사이저"]:
                        if conn == 0:
                            di_inst_map.setdefault("패시브 DI 스테레오", []).append(inst_name)
                        elif conn == 1:
                            di_inst_map.setdefault("액티브 DI 스테레오", []).append(inst_name)
                    elif inst_name == "카혼" and conn == 2:
                        di_inst_map.setdefault("액티브 DI 모노", []).append(inst_name)
                    # 나머지 악기
                    elif inst_name not in ["보컬/랩", "일렉기타", "베이스", "드럼", "퍼커션", "카혼"] \
                         and inst_name not in guitar_family_names \
                         and inst_name not in ["디지털 피아노", "신디사이저"]:
                        if conn == 2:  # 핀마이크·바디팩
                            if inst_name not in pinmic_instruments:
                                pinmic_instruments.append(inst_name)
                        elif conn == 4:  # 픽업-DI
                            di_inst_map.setdefault("액티브 DI 모노", []).append(inst_name)
            
            # Content
            font.setBold(False)
            painter.setFont(font)
            
            for eq in self.service.data_handler.equipments:
                needed = eq.required_count - eq.owned_count
                if needed > 0:
                    # [Eq Name]
                    font.setBold(True)
                    painter.setFont(font)
                    painter.setPen(QColor(0, 0, 0))
                    name_text = f"[{eq.name}] "
                    rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, name_text)
                    painter.drawText(int(margin), int(y), int(rect.width()), int(rect.height()), Qt.AlignmentFlag.AlignLeft, name_text)
                    
                    # Count
                    font.setBold(False)
                    painter.setFont(font)
                    count_text = f"{needed}개"
                    count_rect = painter.boundingRect(int(margin + rect.width()), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, count_text)
                    painter.drawText(int(margin + rect.width()), int(y), int(count_rect.width()), int(count_rect.height()), Qt.AlignmentFlag.AlignLeft, count_text)
                    
                    # Annotation (blue)
                    annotation = ""
                    if eq.name == "핀마이크·바디팩" and pinmic_instruments:
                        annotation = f"  ← {', '.join(pinmic_instruments)}"
                    elif eq.name in di_inst_map:
                        annotation = f"  ← {', '.join(di_inst_map[eq.name])}"
                    
                    if annotation:
                        painter.save()
                        painter.setPen(QColor(0, 0, 255))
                        painter.drawText(int(margin + rect.width() + count_rect.width()), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, annotation)
                        painter.restore()
                    
                    y += line_height
                    
                    # Drum Mic Note
                    if eq.name == "드럼 마이크 세트":
                        y -= line_height * 0.2
                        
                        drum_note = f"* 드럼은 기본 5기통에 크래시 심벌 {crash_cymbal_count}개, 라이드 심벌 1개, 하이햇 심벌을 사용합니다!"
                        
                        painter.save()
                        font.setBold(False)
                        painter.setFont(font)
                        painter.setPen(QColor(0, 0, 255))
                        
                        note_rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, drum_note)
                        painter.drawText(int(margin), int(y), int(content_width), int(note_rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, drum_note)
                        
                        y += note_rect.height() + line_height * 0.5
                        painter.restore()

                    if y > page_height - margin:
                        writer.newPage()
                        y = margin


            # --- 3. 큐시트 ---
            writer.newPage()
            y = margin
            
            # Title
            font.setPointSize(base_size + 2)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "3. 큐시트")
            y += line_height * 1.5
            
            memo_text = self.ui.memo_edit.toPlainText().strip()
            if memo_text:
                memo_text = f"전체적으로 {memo_text}"
                font.setPointSize(base_size)
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QColor(255, 0, 0)) # Red
                
                rect = painter.boundingRect(int(margin), int(y), int(content_width), int(page_height - y - margin), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, memo_text)
                painter.drawText(int(margin), int(y), int(content_width), int(page_height - y - margin), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, memo_text)
                y += rect.height() + line_height
                
                painter.setPen(QColor(0, 0, 0))
            
            font.setPointSize(base_size)
            font.setBold(False)
            painter.setFont(font)
            
            import json
            
            # Iterate Songs - each song starts on a new page
            for idx, song in enumerate(self.service.data_handler.songs):
                # Each song starts a new page (except first if memo fits)
                if idx > 0 or y > margin + line_height * 5:
                    writer.newPage()
                    y = margin
                    
                # Song Header with instruments
                num = num_symbols[idx] if idx < len(num_symbols) else f"({idx+1})"
                font.setBold(True)
                painter.setFont(font)
                
                # Collect instruments for this song
                song_inst_list = []
                for sess in song.sessions:
                    inst = next((i for i in self.service.data_handler.instruments if i.id == sess.instrument_id), None)
                    if inst:
                        song_inst_list.append(inst.name)
                inst_str = ", ".join(song_inst_list)
                
                header_text = f"{num} {song.title}  //  {inst_str}"
                header_rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height * 3), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, header_text)
                painter.drawText(int(margin), int(y), int(content_width), int(header_rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, header_text)
                y += header_rect.height() + line_height * 0.5
                
                # Reference URL (normal font size)
                if song.reference_url:
                    painter.save()
                    
                    # 1. Draw "참고영상: " in black, no underline
                    font.setBold(False)
                    font.setUnderline(False)
                    painter.setFont(font)
                    painter.setPen(QColor(0, 0, 0))
                    
                    prefix_text = "참고영상: "
                    # Get exact width
                    prefix_width = painter.fontMetrics().horizontalAdvance(prefix_text)
                    painter.drawText(int(margin), int(y), int(prefix_width), int(line_height), Qt.AlignmentFlag.AlignLeft, prefix_text)
                    
                    # 2. Draw URL string in blue
                    if song.reference_url.startswith("http://") or song.reference_url.startswith("https://"):
                        font.setUnderline(True)
                    painter.setFont(font)
                    painter.setPen(QColor(0, 0, 255))
                    
                    url_x = margin + prefix_width
                    url_width = content_width - prefix_width
                    url_rect = painter.boundingRect(int(url_x), int(y), int(url_width), int(line_height * 3), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, song.reference_url)
                    painter.drawText(int(url_x), int(y), int(url_width), int(url_rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, song.reference_url)
                    
                    painter.restore()
                    
                    # Reset font for next elements
                    font.setUnderline(False)
                    painter.setFont(font)
                    
                    h = max(line_height, url_rect.height())
                    y += h + line_height * 0.5
                
                # Table Config
                cols = ["섹션", "세션", "이펙트", "메모"]
                col_ratios = [2, 3, 3, 5]
                total_ratio = sum(col_ratios)
                col_widths = [(r / total_ratio) * content_width for r in col_ratios]
                
                # Draw Table Header
                x = margin
                font.setBold(True)
                painter.setFont(font)
                
                row_height = line_height * 1.2
                
                painter.save()
                painter.setBrush(QColor(230, 230, 230))
                painter.drawRect(int(x), int(y), int(content_width), int(row_height))
                painter.restore()
                
                for i, title in enumerate(cols):
                    painter.drawRect(int(x), int(y), int(col_widths[i]), int(row_height))
                    painter.drawText(int(x + 10), int(y), int(col_widths[i] - 20), int(row_height), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter, title)
                    x += col_widths[i]
                
                y += row_height
                
                # Draw Rows
                font.setBold(False)
                painter.setFont(font)
                
                for sec_idx, section in enumerate(song.cue_sections):
                    entries = []
                    for note_json in section.instrument_notes.values():
                        try:
                            entries.append(json.loads(note_json))
                        except:
                            continue
                            
                    if not entries:
                        continue

                    # Section background color toggle
                    bg_color = QColor(255, 255, 255) if sec_idx % 2 == 0 else QColor("#D6E4ED")
                    
                    section_start_y = y

                    for entry_idx, data in enumerate(entries):
                        inst_name = data.get('instrument_name', '')
                        
                        effect_str = ""
                        if data.get('use_effect', False):
                            effect_name = data.get('effect_name', '')
                            effect_level = data.get('effect_level', 0)
                            level_symbols = ["①", "②", "③", "④", "⑤"]
                            if effect_level and 1 <= effect_level <= 5:
                                level_display = []
                                for li in range(5):
                                    if li == effect_level - 1:
                                        level_display.append("●")
                                    else:
                                        level_display.append(level_symbols[li])
                                effect_str = f"{effect_name} [{' '.join(level_display)}]"
                            else:
                                effect_str = effect_name
                            
                        memo = data.get('memo', '')
                        
                        # Note: we only calculate height for 2~4 cols, col 1 is merged visually
                        texts = ["", inst_name, effect_str, memo]
                    
                        max_h = row_height
                        for i in range(1, 4):
                            rect = painter.boundingRect(0, 0, int(col_widths[i] - 20), 0, Qt.TextFlag.TextWordWrap, texts[i])
                            h = rect.height() + 20
                            max_h = max(max_h, h)
                        
                        # Check page break (overflow within same song)
                        if y + max_h > page_height - margin:
                            # Complete the section header col 1 for the current page
                            h_diff = y - section_start_y
                            if h_diff > 0:
                                painter.fillRect(int(margin), int(section_start_y), int(col_widths[0]), int(h_diff), bg_color)
                                painter.drawRect(int(margin), int(section_start_y), int(col_widths[0]), int(h_diff))
                                painter.save()
                                f = painter.font()
                                f.setBold(True)
                                painter.setFont(f)
                                painter.setPen(QColor(0, 0, 0))
                                painter.drawText(int(margin + 10), int(section_start_y), int(col_widths[0] - 20), int(h_diff), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, section.name)
                                painter.restore()

                            writer.newPage()
                            y = margin
                            section_start_y = y
                        
                        # Draw Row columns 2 to 4
                        x = margin + col_widths[0]
                        for i in range(1, 4):
                            painter.fillRect(int(x), int(y), int(col_widths[i]), int(max_h), bg_color)
                            painter.drawRect(int(x), int(y), int(col_widths[i]), int(max_h))
                            
                            painter.save()
                            
                            current_font = painter.font()
                            if i in [1, 2] and texts[i]:
                                current_font.setBold(True)
                            else:
                                current_font.setBold(False)
                            painter.setFont(current_font)
                            
                            if i == 2 and texts[i]:
                                painter.setPen(QColor(0, 0, 255))
                            else:
                                painter.setPen(QColor(0, 0, 0))
                                
                            painter.drawText(int(x + 10), int(y), int(col_widths[i] - 20), int(max_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, texts[i])
                            painter.restore()
                                
                            x += col_widths[i]
                        
                        y += max_h

                    # Draw Section header col 1 after all entries of section fit in current page
                    h_diff = y - section_start_y
                    if h_diff > 0:
                        painter.fillRect(int(margin), int(section_start_y), int(col_widths[0]), int(h_diff), bg_color)
                        painter.drawRect(int(margin), int(section_start_y), int(col_widths[0]), int(h_diff))
                        painter.save()
                        f = painter.font()
                        f.setBold(True)
                        painter.setFont(f)
                        painter.setPen(QColor(0, 0, 0))
                        painter.drawText(int(margin + 10), int(section_start_y), int(col_widths[0] - 20), int(h_diff), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, section.name)
                        painter.restore()

            QMessageBox.information(self.ui, "완료", f"테크라이더가 저장되었습니다:\n{filename}")
            
        except Exception as e:
            QMessageBox.critical(self.ui, "오류", f"PDF 저장 중 오류가 발생했습니다:\n{str(e)}")
        finally:
            painter.end()
