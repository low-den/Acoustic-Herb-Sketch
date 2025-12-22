from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import QObject, pyqtSignal
from models import Song, SongSession
from data_handler import DataHandler
import copy

class AddSongCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, song: Song, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.song = song
        self.update_signal = update_signal
        self.setText(f"Add Song {song.title}")

    def redo(self):
        self.data_handler.songs.append(self.song)
        self.update_signal.emit()

    def undo(self):
        if self.song in self.data_handler.songs:
            self.data_handler.songs.remove(self.song)
            self.update_signal.emit()

class DeleteSongCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, song: Song, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.song = song
        self.update_signal = update_signal
        self.setText(f"Delete Song {song.title}")
        self.index = 0
        self.deleted_assignments = []

    def redo(self):
        if self.song in self.data_handler.songs:
            self.index = self.data_handler.songs.index(self.song)
            self.data_handler.songs.remove(self.song)
            
            # Remove related assignments
            self.deleted_assignments = [a for a in self.data_handler.assignments if a.song_id == self.song.id]
            for a in self.deleted_assignments:
                self.data_handler.assignments.remove(a)
                
            self.update_signal.emit()

    def undo(self):
        self.data_handler.songs.insert(self.index, self.song)
        # Restore assignments
        self.data_handler.assignments.extend(self.deleted_assignments)
        self.update_signal.emit()

class MoveSongCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, old_idx: int, new_idx: int, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.old_idx = old_idx
        self.new_idx = new_idx
        self.update_signal = update_signal
        self.setText("Move Song")

    def redo(self):
        songs = self.data_handler.songs
        if 0 <= self.old_idx < len(songs) and 0 <= self.new_idx < len(songs):
            songs[self.old_idx], songs[self.new_idx] = songs[self.new_idx], songs[self.old_idx]
            self.update_signal.emit()

    def undo(self):
        # Swap back
        self.redo()

class UpdateSongCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, old_song: Song, new_song: Song, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.old_song = old_song
        self.new_song = new_song
        self.update_signal = update_signal
        self.setText(f"Update Song {new_song.title}")

    def redo(self):
        try:
            if self.old_song in self.data_handler.songs:
                idx = self.data_handler.songs.index(self.old_song)
                self.data_handler.songs[idx] = self.new_song
                self.update_signal.emit()
        except ValueError:
            pass

    def undo(self):
        try:
            if self.new_song in self.data_handler.songs:
                idx = self.data_handler.songs.index(self.new_song)
                self.data_handler.songs[idx] = self.old_song
                self.update_signal.emit()
        except ValueError:
            pass

class ResetConcertCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.update_signal = update_signal
        self.backup_songs = []
        self.backup_assignments = []
        self.backup_equipments = []
        self.setText("Reset Concert")

    def redo(self):
        self.backup_songs = list(self.data_handler.songs)
        self.backup_assignments = list(self.data_handler.assignments)
        self.backup_equipments = [copy.deepcopy(eq) for eq in self.data_handler.equipments]
        
        from models import SongCategory, SongSession # Import here to avoid circular imports

        # Create default vocal song
        vocal_inst = next((i for i in self.data_handler.instruments if i.name == "보컬/랩"), None)
        new_first = Song(title="새 곡", bpm=100, category=SongCategory.VOCAL.value)
        if vocal_inst:
            new_first.sessions.append(SongSession(instrument_id=vocal_inst.id, difficulty_param="A5"))

        # Keep ID of first song if exists? 
        if self.data_handler.songs:
            new_first.id = self.data_handler.songs[0].id
            
        self.data_handler.songs = [new_first]
        self.data_handler.assignments = []
        
        # Reset equipment required_count
        for eq in self.data_handler.equipments:
            eq.required_count = 0
            
        self.update_signal.emit()

    def undo(self):
        self.data_handler.songs = self.backup_songs
        self.data_handler.assignments = self.backup_assignments
        self.data_handler.equipments = self.backup_equipments
        self.update_signal.emit()

class SongService(QObject):
    data_changed = pyqtSignal()

    def __init__(self, data_handler: DataHandler, undo_stack):
        super().__init__()
        self.data_handler = data_handler
        self.undo_stack = undo_stack

    def add_song(self, song: Song = None):
        if song is None:
            song = Song()
        cmd = AddSongCommand(self.data_handler, song, self.data_changed)
        self.undo_stack.push(cmd)

    def delete_song(self, song: Song):
        cmd = DeleteSongCommand(self.data_handler, song, self.data_changed)
        self.undo_stack.push(cmd)
        
    def move_song(self, song_id, direction):
        songs = self.data_handler.songs
        idx = next((i for i, s in enumerate(songs) if s.id == song_id), -1)
        if idx == -1: return
        
        new_idx = idx + direction
        if 0 <= new_idx < len(songs):
             cmd = MoveSongCommand(self.data_handler, idx, new_idx, self.data_changed)
             self.undo_stack.push(cmd)

    def update_song(self, old_song: Song, new_song: Song):
        cmd = UpdateSongCommand(self.data_handler, old_song, new_song, self.data_changed)
        self.undo_stack.push(cmd)
        
    def reset_concert(self):
         cmd = ResetConcertCommand(self.data_handler, self.data_changed)
         self.undo_stack.push(cmd)
         
    # Session management inside song is treated as Song Update for simplicity now, 
    # but ideally should have granular commands if we want undo for just adding a session.
    # For now, I will assume the Controller constructs the new Song object with sessions modified 
    # and calls update_song.

