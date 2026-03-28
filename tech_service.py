from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import QObject, pyqtSignal
from models import Equipment, ConnectionType, InstrumentCategory
from data_handler import DataHandler

class AddEquipmentCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, eq: Equipment, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.eq = eq
        self.update_signal = update_signal
        self.setText(f"Add Equipment {eq.name}")

    def redo(self):
        self.data_handler.equipments.append(self.eq)
        self.update_signal.emit()

    def undo(self):
        if self.eq in self.data_handler.equipments:
            self.data_handler.equipments.remove(self.eq)
            self.update_signal.emit()

class DeleteEquipmentCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, eq: Equipment, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.eq = eq
        self.update_signal = update_signal
        self.setText(f"Delete Equipment {eq.name}")
        self.index = 0

    def redo(self):
        if self.eq in self.data_handler.equipments:
            self.index = self.data_handler.equipments.index(self.eq)
            self.data_handler.equipments.remove(self.eq)
            self.update_signal.emit()

    def undo(self):
        self.data_handler.equipments.insert(self.index, self.eq)
        self.update_signal.emit()

class UpdateEquipmentCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, eq_id: str, field: str, new_val, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.eq_id = eq_id
        self.field = field
        self.new_val = new_val
        self.update_signal = update_signal
        
        self.old_val = None
        self.target_eq = next((e for e in self.data_handler.equipments if e.id == eq_id), None)
        if self.target_eq:
            self.old_val = getattr(self.target_eq, field)
            
        self.setText(f"Update Equipment {self.target_eq.name if self.target_eq else ''}")

    def redo(self):
        if self.target_eq:
            setattr(self.target_eq, self.field, self.new_val)
            self.update_signal.emit()

    def undo(self):
        if self.target_eq:
            setattr(self.target_eq, self.field, self.old_val)
            self.update_signal.emit()

class BatchUpdateRequirementsCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, new_requirements: dict, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.new_requirements = new_requirements # {eq_id: new_count}
        self.update_signal = update_signal
        self.old_requirements = {} # {eq_id: old_count}
        
        for eq in self.data_handler.equipments:
            self.old_requirements[eq.id] = eq.required_count
            
        self.setText("Auto Calculate Equipment")

    def redo(self):
        for eq in self.data_handler.equipments:
            if eq.id in self.new_requirements:
                eq.required_count = self.new_requirements[eq.id]
            else:
                eq.required_count = 0 # Reset others to 0? Or keep? Prompt says "Start from 0"
        self.update_signal.emit()

    def undo(self):
        for eq in self.data_handler.equipments:
            if eq.id in self.old_requirements:
                eq.required_count = self.old_requirements[eq.id]
        self.update_signal.emit()

class UpdatePerformanceMemoCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, new_memo: str, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.new_memo = new_memo
        self.old_memo = data_handler.performance_memo
        self.update_signal = update_signal
        self.setText("Update Performance Memo")

    def redo(self):
        self.data_handler.performance_memo = self.new_memo
        # Memo update usually doesn't need to refresh entire UI, but consistent with others
        # self.update_signal.emit() 

    def undo(self):
        self.data_handler.performance_memo = self.old_memo
        self.update_signal.emit() # Signal needed to update UI text box

    def id(self):
        return 1001 # Unique ID for this command type

    def mergeWith(self, other):
        if other.id() != self.id():
            return False
        # Update new value, keep original old value
        self.new_memo = other.new_memo
        return True

class UpdateSoundDesignCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, key: str, value: int, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.key = key
        self.new_value = value
        self.old_value = data_handler.sound_design_settings.get(key, -1)
        self.update_signal = update_signal
        self.setText(f"Update Sound Design {key}")

    def redo(self):
        self.data_handler.sound_design_settings[self.key] = self.new_value
        # self.update_signal.emit() # Optional, radio buttons are already updated by UI

    def undo(self):
        if self.old_value == -1:
            if self.key in self.data_handler.sound_design_settings:
                del self.data_handler.sound_design_settings[self.key]
        else:
            self.data_handler.sound_design_settings[self.key] = self.old_value
        self.update_signal.emit() # Need to update UI

class TechService(QObject):
    data_changed = pyqtSignal()
    
    def __init__(self, data_handler: DataHandler, undo_stack):
        super().__init__()
        self.data_handler = data_handler
        self.undo_stack = undo_stack

    def add_equipment(self, name: str):
        eq = Equipment(name=name)
        cmd = AddEquipmentCommand(self.data_handler, eq, self.data_changed)
        self.undo_stack.push(cmd)

    def delete_equipment(self, eq_id: str):
        eq = next((e for e in self.data_handler.equipments if e.id == eq_id), None)
        if eq:
            cmd = DeleteEquipmentCommand(self.data_handler, eq, self.data_changed)
            self.undo_stack.push(cmd)

    def update_equipment(self, eq_id: str, field: str, value):
        cmd = UpdateEquipmentCommand(self.data_handler, eq_id, field, value, self.data_changed)
        self.undo_stack.push(cmd)

    def update_performance_memo(self, text: str):
        cmd = UpdatePerformanceMemoCommand(self.data_handler, text, self.data_changed)
        self.undo_stack.push(cmd)

    def update_sound_design_setting(self, key: str, value: int):
        cmd = UpdateSoundDesignCommand(self.data_handler, key, value, self.data_changed)
        self.undo_stack.push(cmd)

    def get_calculated_requirements(self, settings: dict):
        """
        Calculates equipment requirements using per-song-max approach.
        For each song, calculates the equipment needed, then takes the maximum
        of each equipment across all songs. This minimizes costs by reusing
        equipment between songs.

        Returns: (needs: dict, log_lines: list)
        """
        needs = {}  # EquipmentName -> max count across songs
        log_lines = []

        # Build guitar family set
        guitar_family_names = set()
        for inst in self.data_handler.instruments:
            if inst.category == InstrumentCategory.GUITAR.value and inst.name not in ["일렉기타", "베이스"]:
                guitar_family_names.add(inst.name)

        # Track instrument usage for logging
        max_usage = {}
        inst_songs_map = {}

        # Calculate per-song equipment needs, then take max across songs
        for song in self.data_handler.songs:
            song_needs = {}  # equipment -> count for this song
            song_inst_counts = {}  # inst_name -> count in this song

            for session in song.sessions:
                inst = next((i for i in self.data_handler.instruments if i.id == session.instrument_id), None)
                if not inst: continue
                song_inst_counts[inst.name] = song_inst_counts.get(inst.name, 0) + 1
                inst_songs_map.setdefault(inst.name, set()).add(song.title)

            # Update max usage for logging
            for name, count in song_inst_counts.items():
                max_usage[name] = max(max_usage.get(name, 0), count)

            # Add equipment for each instrument instance in this song
            def song_add(eq_name, qty, source=None):
                if qty <= 0: return
                song_needs[eq_name] = song_needs.get(eq_name, 0) + qty

            for name, count in song_inst_counts.items():
                for i in range(count):
                    conn = settings.get(f"{name}_{i}_conn", 0)
                    self._add_equipment_for(name, conn, guitar_family_names, song_add)

            # Update max needs: keep the maximum of each equipment across songs
            for eq_name, qty in song_needs.items():
                needs[eq_name] = max(needs.get(eq_name, 0), qty)

        # Generate log lines (instrument usage info)
        for name, x in max_usage.items():
            if x > 0:
                songs_str = ", ".join(sorted(inst_songs_map.get(name, set())))
                log_lines.append(f"[{name}] 최대 {x}개\n곡: {songs_str}")

        return needs, log_lines

    def _add_equipment_for(self, name, conn, guitar_family_names, add):
        """Adds equipment for a single instrument instance based on its connection method."""

        if name == "보컬/랩":
            add("SM58 (보컬 마이크)", 1, name)
            add("롱 마이크 스탠드", 1, name)
            if conn == 0:    add("XLR 5m", 1, name)
            elif conn == 1:  add("XLR 5m", 2, name)

        elif name in guitar_family_names:
            if conn == 0:    add("TS 5m", 1, name); add("XLR 5m", 1, name)
            elif conn == 1:  add("TS 5m", 1, name)
            elif conn == 2:  add("SM57 (악기 마이크)", 1, name); add("XLR 5m", 1, name)
            elif conn == 3:  add("패시브 DI 모노", 1, name); add("TS 5m", 1, name); add("XLR 5m", 1, name)

        elif name == "일렉기타":
            if conn == 0:    add("TS 3m", 2, name); add("TS 5m", 1, name)
            elif conn == 1:  add("TS 3m", 1, name); add("TS 5m", 1, name)
            elif conn == 2:  add("TS 5m", 1, name)
            add("XLR 5m", 1, name)
            add("SM57 (악기 마이크)", 1, name)
            add("숏 마이크 스탠드", 1, name)
            add("일렉 앰프", 1, name)

        elif name == "베이스":
            if conn == 0:    add("TS 3m", 1, name); add("TS 5m", 1, name); add("XLR 5m", 1, name)
            elif conn == 1:  add("TS 5m", 1, name); add("XLR 5m", 1, name); add("SM57 (악기 마이크)", 1, name); add("숏 마이크 스탠드", 1, name)
            add("베이스 앰프", 1, name)

        elif name in ["디지털 피아노", "신디사이저"]:
            if conn == 0:    add("패시브 DI 스테레오", 1, name)
            elif conn == 1:  add("액티브 DI 스테레오", 1, name)
            add("TS 3m", 2, name)
            add("XLR 5m", 2, name)

        elif name == "드럼":
            add("드럼 마이크 세트", 1, name)
            add("숏 마이크 스탠드", 1, name)
            add("롱 마이크 스탠드", 2, name)
            add("XLR 5m", 6, name)

        elif name == "카혼":
            if conn == 0:    add("SM57 (악기 마이크)", 2, name); add("XLR 5m", 2, name); add("숏 마이크 스탠드", 1, name); add("롱 마이크 스탠드", 1, name)
            elif conn == 1:  add("TS 5m", 1, name)
            elif conn == 2:  add("액티브 DI 모노", 1, name); add("TS 3m", 1, name); add("XLR 5m", 1, name)

        elif name == "퍼커션":
            add("SM57 (악기 마이크)", 3, name)
            add("XLR 5m", 3, name)
            add("롱 마이크 스탠드", 3, name)

        else:  # 나머지
            if conn == 0:    add("SM58 (보컬 마이크)", 1, name); add("XLR 5m", 1, name)
            elif conn == 1:  add("SM57 (악기 마이크)", 1, name); add("XLR 5m", 1, name)
            elif conn == 2:  add("핀마이크·바디팩", 1, name); add("XLR 5m", 1, name)
            elif conn == 3:  add("TS 5m", 1, name)
            elif conn == 4:  add("액티브 DI 모노", 1, name); add("TS 3m", 1, name); add("XLR 5m", 1, name)

    def calculate_needs(self, settings: dict):
        """
        Returns: (success: bool, log_lines: list)
        """
        needs, log_lines = self.get_calculated_requirements(settings)

        # Create Command to Update Equipment Models
        new_requirements = {}
        for eq in self.data_handler.equipments:
            count = needs.get(eq.name, 0)
            new_requirements[eq.id] = count
            
        cmd = BatchUpdateRequirementsCommand(self.data_handler, new_requirements, self.data_changed)
        self.undo_stack.push(cmd)
        
        return True, log_lines
