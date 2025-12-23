from tech_ui import TechWidget
from tech_service import TechService
from song_service import SongService
from PyQt6.QtWidgets import (QTableWidgetItem, QSpinBox, QTreeWidgetItem, QMessageBox, 
                             QListWidgetItem, QInputDialog, QFileDialog, QDialog, 
                             QVBoxLayout, QTextEdit, QPushButton, QLabel)
from PyQt6.QtCore import Qt, QSizeF, QObject, QEvent
from PyQt6.QtGui import QPdfWriter, QPainter, QPageSize, QPageLayout, QColor, QFont, QTextDocument
from dialogs import CueSheetEditDialog
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
        
        # Sound Design Signals
        self.ui.eg1_row.group.idClicked.connect(lambda id: self.update_sound_setting("eg1_cable", id))
        self.ui.eg2_row.group.idClicked.connect(lambda id: self.update_sound_setting("eg2_cable", id))
        self.ui.piano1_row.group.idClicked.connect(lambda id: self.update_sound_setting("piano1_di", id))
        self.ui.piano2_row.group.idClicked.connect(lambda id: self.update_sound_setting("piano2_di", id))
        
        # Memo Signal
        self.ui.memo_edit.textChanged.connect(self.update_performance_memo)
        
        # Shortcuts
        self.ui.eq_table.installEventFilter(self)
        self.ui.cue_table.installEventFilter(self)

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
        
        # Restore Sound Design Settings
        settings = self.service.data_handler.sound_design_settings
        
        def restore_group(group, key):
            val = settings.get(key, -1)
            if val != -1:
                btn = group.button(val)
                if btn: btn.setChecked(True)
        
        restore_group(self.ui.eg1_row.group, "eg1_cable")
        restore_group(self.ui.eg2_row.group, "eg2_cable")
        restore_group(self.ui.piano1_row.group, "piano1_di")
        restore_group(self.ui.piano2_row.group, "piano2_di")
        
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
        # Gather Settings from UI
        settings = {}
        
        # Helper to get checked index from ButtonGroup
        def get_checked_index(group):
            return group.checkedId()
            
        # EG1 Cable Count (3개: 0, 2개: 1, 1개: 2) -> Map to 3, 2, 1
        eg1_idx = get_checked_index(self.ui.eg1_row.group)
        if eg1_idx == -1:
            QMessageBox.warning(self.ui, "경고", "음향 설계에서 '일렉기타 1' 항목을 선택해주세요.")
            return
        if eg1_idx == 0: settings['eg1_cable'] = 3
        elif eg1_idx == 1: settings['eg1_cable'] = 2
        else: settings['eg1_cable'] = 1
        
        # EG2 Cable Count
        eg2_idx = get_checked_index(self.ui.eg2_row.group)
        if eg2_idx == -1:
            QMessageBox.warning(self.ui, "경고", "음향 설계에서 '일렉기타 2' 항목을 선택해주세요.\n사용하지 않아도 체크해주세요. 계산되지 않습니다.")
            return
        if eg2_idx == 0: settings['eg2_cable'] = 3
        elif eg2_idx == 1: settings['eg2_cable'] = 2
        else: settings['eg2_cable'] = 1
        
        # Piano 1 DI (Passive: 0, Active: 1)
        p1_idx = get_checked_index(self.ui.piano1_row.group)
        if p1_idx == -1:
            QMessageBox.warning(self.ui, "경고", "음향 설계에서 '피아노/신디 1' 항목을 선택해주세요.")
            return
        settings['piano1_di'] = p1_idx
        
        # Piano 2 DI
        p2_idx = get_checked_index(self.ui.piano2_row.group)
        if p2_idx == -1:
            QMessageBox.warning(self.ui, "경고", "음향 설계에서 '피아노/신디 2' 항목을 선택해주세요.\n사용하지 않아도 체크해주세요. 계산되지 않습니다.")
            return
        settings['piano2_di'] = p2_idx
        
        # Confirm Calculation
        reply = QMessageBox.question(self.ui, '자동 계산', 
                                     '필요 개수의 현재 값이 모두 지워지고 자동으로 계산됩니다. 진행하시겠습니까?', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        success, log1, log2 = self.service.calculate_needs(settings)
        
        if success:
            # Show Log 1
            if log1:
                log1_msg = "\n".join(log1)
                QMessageBox.information(self.ui, "계산 알림 (1/2)", f"다음과 같은 예외 사항이 적용되었습니다:\n\n{log1_msg}")
            else:
                QMessageBox.information(self.ui, "계산 알림 (1/2)", "특이 사항 없이 계산되었습니다.")
                
            # Show Log 2 (Custom Dialog)
            if log2:
                log2_msg = "\n\n".join(log2)
                
                dialog = QDialog(self.ui)
                dialog.setWindowTitle("계산 알림 (2/2)")
                dialog.resize(600, 400)
                
                layout = QVBoxLayout(dialog)
                layout.addWidget(QLabel("악기별 계산 결과:"))
                
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setText(log2_msg)
                layout.addWidget(text_edit)
                
                btn_ok = QPushButton("확인")
                btn_ok.clicked.connect(dialog.accept)
                layout.addWidget(btn_ok)
                
                dialog.exec()
            else:
                QMessageBox.information(self.ui, "계산 알림 (2/2)", "계산된 악기가 없습니다.")
        else:
            QMessageBox.warning(self.ui, "오류", "계산 중 오류가 발생했습니다.")

    def reset_equipment(self):
        pass # Removed button

    def export_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(self.ui, "테크라이더 내보내기", "테크라이더.pdf", "PDF Files (*.pdf)")
        if not filename:
            return

        writer = QPdfWriter(filename)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setResolution(300) # 300 DPI for high quality
        
        painter = QPainter(writer)
        
        try:
            # Constants for layout
            page_width = writer.width()
            page_height = writer.height()
            margin = 300 # 1 inch approx at 300dpi is 300
            content_width = page_width - (2 * margin)
            
            y = margin
            line_height = 100
            
            font = painter.font()
            base_size = font.pointSize()
            
            # --- 1. 곡별 사용 악기 ---
            # Title
            font.setPointSize(base_size + 2)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "1. 곡별 사용 악기")
            y += line_height * 1.5
            
            # Desc
            font.setPointSize(base_size)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "곡별로 이런 악기들을 사용합니다! 🎸🎹")
            y += line_height * 1.5
            
            # [전체] Summary
            # Calculate max usage per instrument
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
            
            summary_items = [] # (sort_index, instrument_name, count)

            for name, count in max_inst_usage.items():
                if count > 0:
                    # Find instrument object to get category
                    inst_obj = next((i for i in self.service.data_handler.instruments if i.name == name), None)
                    cat_name = inst_obj.category if inst_obj else InstrumentCategory.ETC.value
                    sort_idx = category_order.get(cat_name, 99)
                    
                    summary_items.append((sort_idx, name, count))

            # Sort: Primary=Category, Secondary=Name
            summary_items.sort(key=lambda x: (x[0], x[1]))
            
            summary_list = [f"{item[1]} {item[2]}개" for item in summary_items]
            
            if summary_list:
                font.setBold(True)
                painter.setFont(font)
                summary_text = "[전체] " + ", ".join(summary_list)
                
                rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, summary_text)
                painter.drawText(int(margin), int(y), int(content_width), int(rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, summary_text)
                
                y += rect.height() + 50

            # Content
            for song in self.service.data_handler.songs:
                # [Song Name]
                font.setBold(True)
                painter.setFont(font)
                song_text = f"[{song.title}] "
                rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, song_text)
                painter.drawText(int(margin), int(y), int(rect.width()), int(rect.height()), Qt.AlignmentFlag.AlignLeft, song_text)
                
                # Instruments
                font.setBold(False)
                painter.setFont(font)
                
                # Collect instruments for this song in order
                inst_list = []
                for sess in song.sessions:
                    inst = next((i for i in self.service.data_handler.instruments if i.id == sess.instrument_id), None)
                    if inst:
                        inst_list.append(inst.name)
                
                inst_text = ", ".join(inst_list)
                
                # Draw instruments after song title, wrap if needed
                text_rect = painter.boundingRect(int(margin + rect.width()), int(y), int(content_width - rect.width()), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, inst_text)
                painter.drawText(int(margin + rect.width()), int(y), int(content_width - rect.width()), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, inst_text)
                
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
            
            # Desc
            font.setPointSize(base_size)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "이런 장비들이 필요합니다! 🔌🎤")
            y += line_height * 1.5
            
            # Pre-check for Drum Mic Set to ask input
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
            
            # Content
            for eq in self.service.data_handler.equipments:
                needed = eq.required_count - eq.owned_count
                if needed > 0:
                    # [Eq Name]
                    font.setBold(True)
                    painter.setFont(font)
                    painter.setPen(QColor(0, 0, 0)) # Ensure Black
                    name_text = f"[{eq.name}] "
                    rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, name_text)
                    painter.drawText(int(margin), int(y), int(rect.width()), int(rect.height()), Qt.AlignmentFlag.AlignLeft, name_text)
                    
                    # Count
                    font.setBold(False)
                    painter.setFont(font)
                    count_text = f"{needed}개"
                    painter.drawText(int(margin + rect.width()), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, count_text)
                    
                    y += line_height
                    
                    # Drum Mic Note
                    if eq.name == "드럼 마이크 세트":
                        y -= line_height * 0.2 # Reduce gap
                        
                        drum_note = f"* 드럼은 기본 5기통에 크래시 심벌 {crash_cymbal_count}개, 라이드 심벌 1개, 하이햇 심벌을 사용합니다!\n드럼 마이크에 사용할 스탠드 및 케이블은 편하신대로 따로 계산해서 가져와주시면 감사하겠습니다!"
                        
                        painter.save()
                        font.setBold(False)
                        painter.setFont(font)
                        painter.setPen(QColor(0, 0, 255)) # Blue
                        
                        note_rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, drum_note)
                        painter.drawText(int(margin), int(y), int(content_width), int(note_rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, drum_note)
                        
                        y += note_rect.height() + line_height * 0.5
                        painter.restore()

                    # Pin Mic Note
                    elif eq.name == "핀마이크·바디팩":
                        y -= line_height * 0.2 # Reduce gap
                        
                        pin_note = "* 핀마이크·바디팩은 관현악기에 사용하고 싶습니다!"
                        
                        painter.save()
                        font.setBold(False)
                        painter.setFont(font)
                        painter.setPen(QColor(0, 0, 255)) # Blue
                        
                        note_rect = painter.boundingRect(int(margin), int(y), int(content_width), int(line_height * 10), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, pin_note)
                        painter.drawText(int(margin), int(y), int(content_width), int(note_rect.height()), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, pin_note)
                        
                        y += note_rect.height() + line_height * 0.5
                        painter.restore()

                    if y > page_height - margin:
                        writer.newPage()
                        y = margin

            # Part 2: Auto Calc Log Verification
            def get_checked_index(group): return group.checkedId()
            
            settings = {}
            eg1_idx = get_checked_index(self.ui.eg1_row.group)
            if eg1_idx == 0: settings['eg1_cable'] = 3
            elif eg1_idx == 1: settings['eg1_cable'] = 2
            else: settings['eg1_cable'] = 1
            
            eg2_idx = get_checked_index(self.ui.eg2_row.group)
            if eg2_idx == 0: settings['eg2_cable'] = 3
            elif eg2_idx == 1: settings['eg2_cable'] = 2
            else: settings['eg2_cable'] = 1
            
            settings['piano1_di'] = get_checked_index(self.ui.piano1_row.group)
            settings['piano2_di'] = get_checked_index(self.ui.piano2_row.group)
            
            valid_settings = True
            if eg1_idx == -1 or eg2_idx == -1 or settings['piano1_di'] == -1 or settings['piano2_di'] == -1:
                valid_settings = False
                
            if valid_settings:
                needs, log1, log2 = self.service.get_calculated_requirements(settings)
                
                # Check if matches current data
                matches = True
                for eq in self.service.data_handler.equipments:
                    calc_val = needs.get(eq.name, 0)
                    if eq.required_count != calc_val:
                        matches = False
                        break
                        
                if matches and log2:
                    y += line_height * 2
                    
                    # Estimate height
                    font.setBold(True)
                    painter.setFont(font)
                    title_h = line_height
                    
                    font.setBold(False)
                    painter.setFont(font)
                    log_text = "\n\n".join(log2)
                    rect = painter.boundingRect(int(margin), 0, int(content_width), 0, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, log_text)
                    content_h = rect.height()
                    
                    if y + title_h + content_h > page_height - margin:
                        writer.newPage()
                        y = margin
                        
                    # Draw Log 2 Title
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "필요한 장비 상세")
                    y += line_height * 1.5
                    
                    # Draw Log 2 Content
                    font.setBold(False)
                    painter.setFont(font)
                    painter.drawText(int(margin), int(y), int(content_width), int(content_h), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, log_text)
                    y += content_h + 50

            # --- 3. 공연 전반 메모 (New Page) ---
            writer.newPage()
            y = margin
            
            # Title
            font.setPointSize(base_size + 2)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "3. 공연 전반 메모")
            y += line_height * 1.5
            
            # Desc
            font.setPointSize(base_size)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "공연 전반적으로 이렇게 부탁드릴게요! 🙏✨")
            y += line_height * 1.5
            
            # Content (Bold + Blue)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(0, 0, 255)) # Blue
            
            memo_text = self.ui.memo_edit.toPlainText()
            rect = painter.boundingRect(int(margin), int(y), int(content_width), int(page_height - y - margin), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, memo_text)
            painter.drawText(int(margin), int(y), int(content_width), int(page_height - y - margin), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, memo_text)
            y += rect.height() + 50
            
            painter.setPen(QColor(0, 0, 0)) # Reset to Black

            # --- 4. 곡별 큐시트 ---
            y += line_height * 2
            if y > page_height - margin - 300: # Ensure some space for header
                writer.newPage()
                y = margin

            # Title
            font.setPointSize(base_size + 2)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "4. 곡별 큐시트")
            y += line_height * 1.5
            
            # Desc
            font.setPointSize(base_size)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, "곡별 큐시트는 이렇습니다! 잘 부탁드려요! 🎵📝")
            y += line_height * 2
            
            # Iterate Songs
            for idx, song in enumerate(self.service.data_handler.songs):
                # Check space for song header and at least 1 row (approx 500 height)
                if y > page_height - margin - 500:
                    writer.newPage()
                    y = margin
                    
                # Song Header
                font.setBold(True)
                painter.setFont(font)
                header_text = f"({idx+1}) [{song.title}]"
                painter.drawText(int(margin), int(y), int(content_width), int(line_height), Qt.AlignmentFlag.AlignLeft, header_text)
                y += line_height * 1.5
                
                # Reference URL
                if song.reference_url:
                    # Use QTextDocument for HTML link
                    doc = QTextDocument()
                    # Apply current font settings (unbold)
                    font.setBold(False)
                    painter.setFont(font)
                    doc.setDefaultFont(font)
                    
                    # Create HTML with link
                    html = f'<a href="{song.reference_url}">참고영상: {song.reference_url}</a>'
                    doc.setHtml(html)
                    doc.setTextWidth(content_width)
                    
                    painter.save()
                    painter.translate(int(margin), int(y)) 
                    doc.drawContents(painter)
                    painter.restore()
                    
                    y += doc.size().height() + line_height * 0.5
                
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
                painter.setBrush(QColor(230, 230, 230)) # Header BG
                painter.drawRect(int(x), int(y), int(content_width), int(row_height))
                painter.restore()
                
                for i, title in enumerate(cols):
                    painter.drawRect(int(x), int(y), int(col_widths[i]), int(row_height)) # Border
                    painter.drawText(int(x + 10), int(y), int(col_widths[i] - 20), int(row_height), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)
                    x += col_widths[i]
                
                y += row_height
                
                # Draw Rows
                font.setBold(False)
                painter.setFont(font)
                
                import json
                for section in song.cue_sections:
                    entries = []
                    for note_json in section.instrument_notes.values():
                        try:
                            entries.append(json.loads(note_json))
                        except:
                            continue
                            
                    if not entries:
                        continue

                    for idx, data in enumerate(entries):
                        sec_name = section.name if idx == 0 else ""
                        inst_name = data.get('instrument_name', '')
                        
                        effect_str = ""
                        if data.get('use_effect', False):
                            effect_str = f"{data.get('effect_name', '')} {data.get('effect_level_str', '')}"
                            
                        memo = data.get('memo', '')
                        
                        texts = [sec_name, inst_name, effect_str, memo]
                    
                        # Calculate heights
                        max_h = row_height
                        text_heights = []
                        
                        for i, text in enumerate(texts):
                            rect = painter.boundingRect(0, 0, int(col_widths[i] - 20), 0, Qt.TextFlag.TextWordWrap, text)
                            h = rect.height() + 20 # Padding
                            text_heights.append(h)
                            max_h = max(max_h, h)
                        
                        # Check page break
                        if y + max_h > page_height - margin:
                            writer.newPage()
                            y = margin
                        
                        x = margin
                        for i, text in enumerate(texts):
                            painter.drawRect(int(x), int(y), int(col_widths[i]), int(max_h)) # Cell Border
                            
                            painter.save()
                            
                            # Font Style
                            current_font = painter.font()
                            
                            # Bold for Section(0), Session(1), Effect(2)
                            if i in [0, 1, 2] and text:
                                current_font.setBold(True)
                            else:
                                current_font.setBold(False)
                            painter.setFont(current_font)
                            
                            # Color for Effect(2)
                            if i == 2 and text:
                                painter.setPen(QColor(0, 0, 255)) # Blue
                            else:
                                painter.setPen(QColor(0, 0, 0)) # Black
                                
                            painter.drawText(int(x + 10), int(y + 10), int(col_widths[i] - 20), int(max_h - 20), Qt.TextFlag.TextWordWrap, text)
                            painter.restore()
                                
                            x += col_widths[i]
                        
                        y += max_h
                
                y += line_height * 2 # Space between songs

            QMessageBox.information(self.ui, "완료", f"테크라이더가 저장되었습니다:\n{filename}")
            
        except Exception as e:
            QMessageBox.critical(self.ui, "오류", f"PDF 저장 중 오류가 발생했습니다:\n{str(e)}")
        finally:
            painter.end()
