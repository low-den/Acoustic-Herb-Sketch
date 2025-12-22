from PyQt6.QtWidgets import QMessageBox
from song_ui import SongWidget, SongBoxWidget, SessionBoxWidget
from song_service import SongService
from models import Song, SongSession, SongCategory
from PyQt6.QtCore import Qt
import copy
from dialogs import InstrumentSelectDialog

class SongController:
    def __init__(self, ui: SongWidget, service: SongService):
        self.ui = ui
        self.service = service
        self.widget_map = {} 
        
        self.connect_signals()
        self.refresh_ui()

    def connect_signals(self):
        self.service.data_changed.connect(self.refresh_ui)
        self.ui.btn_add_song.clicked.connect(self.add_default_song)
        self.ui.btn_reset.clicked.connect(self.confirm_reset)

    def add_default_song(self):
        # Create a default song structure
        # Must be Vocal song with "Vocal/Rap" session by default
        vocal_inst = next((i for i in self.service.data_handler.instruments if i.name == "보컬/랩"), None)
        new_song = Song(category=SongCategory.VOCAL.value)
        if vocal_inst:
            new_song.sessions.append(SongSession(instrument_id=vocal_inst.id, difficulty_param="A5"))
        
        # Add command
        self.service.add_song(new_song)
        
        # Scroll to bottom
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.ui.scroll_area.verticalScrollBar().setValue(
            self.ui.scroll_area.verticalScrollBar().maximum()
        ))

    def confirm_reset(self):
        reply = QMessageBox.question(self.ui, '경고', '해당 공연 곡이 모두 삭제됩니다. 정말 삭제하시겠습니까?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.service.reset_concert()

    def refresh_ui(self):
        # Clear existing
        while self.ui.songs_layout.count():
            item = self.ui.songs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.widget_map = {}

        songs = self.service.data_handler.songs
        if not songs:
             # Do not force add here if load is empty, wait for user action or init
             pass

        for index, song in enumerate(songs):
            box = SongBoxWidget()
            self.setup_box(box, song, index)
            self.ui.songs_layout.addWidget(box)
            self.widget_map[song.id] = box
            
    def setup_box(self, box: SongBoxWidget, song: Song, index: int):
        # Fill data
        box.lbl_number.setText(f"No.{index + 1}")
        box.edit_name.setText(song.title)
        box.edit_nickname.setText(song.nickname) # Fill nickname
        box.edit_bpm.setText(str(song.bpm))
        box.combo_category.setCurrentText(song.category)
        box.edit_ref.setText(song.reference_url)
        
        # Always show delete button, but disable if only one song
        box.btn_delete.show()
        if len(self.service.data_handler.songs) <= 1:
            box.btn_delete.setEnabled(False)
        else:
            box.btn_delete.setEnabled(True)

        # Connect signals
        box.edit_name.editingFinished.connect(lambda: self.update_field(song, "title", box.edit_name.text()))
        box.edit_nickname.editingFinished.connect(lambda: self.update_field(song, "nickname", box.edit_nickname.text())) # Nickname signal
        box.edit_bpm.editingFinished.connect(lambda: self.update_field(song, "bpm", box.edit_bpm.text()))
        box.combo_category.currentTextChanged.connect(lambda t: self.on_category_changed(song, t))
        # Use textChanged for URL to ensure it's saved even without Enter
        box.edit_ref.textChanged.connect(lambda t: self.update_ref_direct(song, t))
        
        box.btn_delete.clicked.connect(lambda: self.delete_song_confirm(song))
        box.btn_up.clicked.connect(lambda: self.service.move_song(song.id, -1))
        box.btn_down.clicked.connect(lambda: self.service.move_song(song.id, 1))
        
        box.btn_add_session.clicked.connect(lambda: self.add_session(song))
        
        # Populate sessions
        for sess_idx, session in enumerate(song.sessions):
            self.add_session_widget(box, song, session, sess_idx)

    def add_session_widget(self, box, song, session, index):
        sess_widget = SessionBoxWidget()
        
        inst_name = self.get_inst_name(session.instrument_id)
        sess_widget.btn_inst.setText(inst_name)
        
        # Logic: Label and Options based on Instrument Name (Vocal/Rap vs Others)
        # Assuming "보컬/랩" is the name. ID check is safer but name is used in logic req.
        is_vocal_inst = (inst_name == "보컬/랩")
        
        if is_vocal_inst:
            sess_widget.lbl_difficulty.setText("최고음")
            opts = ["E5", "F5", "F#5", "G5", "G#5", "A5", "A#5", "B5", "C6", "C#6", "D6", "D#6", "E6", "F6", "F#6", "G6", "G#6", "A6", "A#6", "B6", "C7"]
        else:
            sess_widget.lbl_difficulty.setText("최대비트")
            opts = ["1", "4", "8", "16", "24", "32"]
            
        sess_widget.combo_difficulty.clear()
        sess_widget.combo_difficulty.addItems(opts)
        
        if session.difficulty_param in opts:
            sess_widget.combo_difficulty.setCurrentText(session.difficulty_param)
        
        # Hide remove button for FIRST session always
        if index == 0:
            sess_widget.btn_remove.hide()
            
            # Disable instrument select ONLY if Vocal Song (Locked to Vocal/Rap)
            if song.category == SongCategory.VOCAL.value:
                sess_widget.btn_inst.setEnabled(False)
            else:
                sess_widget.btn_inst.setEnabled(True)
        else:
            sess_widget.btn_remove.show()
            sess_widget.btn_inst.setEnabled(True)
        
        # Signals
        sess_widget.btn_inst.clicked.connect(lambda: self.select_instrument(song, session))
        sess_widget.combo_difficulty.currentTextChanged.connect(lambda t: self.update_session_field(song, session, "difficulty_param", t))
        sess_widget.btn_remove.clicked.connect(lambda: self.delete_session(song, session))
        
        # Insert before add button
        count = box.sessions_layout.count()
        box.sessions_layout.insertWidget(count - 1, sess_widget)

    def get_inst_name(self, inst_id):
        for i in self.service.data_handler.instruments:
            if i.id == inst_id:
                return i.name
        return "악기 선택"

    def update_ref_direct(self, song, value):
        song.reference_url = value

    def update_field(self, song, field_name, value):
        if getattr(song, field_name) == value:
            return

        new_song = copy.deepcopy(song)
        if field_name == "bpm":
            try:
                setattr(new_song, field_name, int(value))
            except ValueError:
                return 
        else:
            setattr(new_song, field_name, value)
            
        self.service.update_song(song, new_song)

    def on_category_changed(self, song, new_category):
        if song.category == new_category:
            return

        new_song = copy.deepcopy(song)
        new_song.category = new_category
        
        vocal_inst = next((i for i in self.service.data_handler.instruments if i.name == "보컬/랩"), None)
        vocal_id = vocal_inst.id if vocal_inst else "UNKNOWN"

        if new_category == SongCategory.VOCAL.value:
            # Instrumental -> Vocal
            # Add 'Vocal/Rap' at the beginning
            # Check if already exists? Usually not in Inst song.
            # Just insert at 0
            new_session = SongSession(instrument_id=vocal_id, difficulty_param="A5")
            new_song.sessions.insert(0, new_session)
            
        else:
            # Vocal -> Instrumental
            # Remove 'Vocal/Rap' sessions (or just the first one?)
            # Req: "'보컬/랩'에 해당하는 악기를 지워야 해."
            # Remove all vocal/rap instances or just the first locked one?
            # Safest is to remove all instances of Vocal/Rap
            new_song.sessions = [s for s in new_song.sessions if s.instrument_id != vocal_id]
            
            # If sessions become empty, add a default placeholder?
            # An instrumental song needs at least one instrument usually?
            # If empty, maybe add a default instrument? (e.g. Piano or Guitar)
            if not new_song.sessions:
                 # Add dummy
                 pass 

        self.service.update_song(song, new_song)

    def delete_song_confirm(self, song):
        reply = QMessageBox.question(self.ui, '삭제', '정말 이 곡을 지우시겠습니까?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.service.delete_song(song)

    def add_session(self, song):
        new_song = copy.deepcopy(song)
        new_session = SongSession()
        
        # Default logic
        # If Vocal song, default added is? Usually instrument.
        # If Inst song, default is?
        # Let's just add empty/default and let user select.
        new_session.difficulty_param = "16" 
        
        new_song.sessions.append(new_session)
        self.service.update_song(song, new_song)
        
    def delete_session(self, song, session_to_delete):
         new_song = copy.deepcopy(song)
         new_song.sessions = [s for s in new_song.sessions if s.id != session_to_delete.id]
         self.service.update_song(song, new_song)
         
    def select_instrument(self, song, session):
        dlg = InstrumentSelectDialog(self.service.data_handler.instruments, self.ui)
        if dlg.exec():
            selected = dlg.selected_inst
            if selected:
                # Prevent selecting Vocal/Rap if current song is Instrumental?
                # "기악곡은 '보컬/랩' 악기가 존재할 수 없어."
                if song.category == SongCategory.INSTRUMENTAL.value and selected.name == "보컬/랩":
                    QMessageBox.warning(self.ui, "경고", "기악곡에는 보컬/랩 세션을 추가할 수 없습니다.")
                    return

                new_song = copy.deepcopy(song)
                for s in new_song.sessions:
                    if s.id == session.id:
                        s.instrument_id = selected.id
                        # Reset difficulty param based on type
                        if selected.name == "보컬/랩":
                            s.difficulty_param = "A5"
                        else:
                            s.difficulty_param = "16"
                        break
                self.service.update_song(song, new_song)

    def update_session_field(self, song, session, field, value):
        new_song = copy.deepcopy(song)
        changed = False
        for s in new_song.sessions:
            if s.id == session.id:
                if getattr(s, field) != value:
                    setattr(s, field, value)
                    changed = True
                break
        
        if changed:
            self.service.update_song(song, new_song)
