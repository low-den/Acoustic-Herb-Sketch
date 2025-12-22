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

    def get_calculated_requirements(self, settings: dict):
        """
        Calculates requirements without applying changes.
        Returns: (needs: dict, log1_lines: list, log2_lines: list)
        """
        needs = {} # Name -> Count
        log1_lines = []
        log2_lines = []
        
        # Log 2 Data Structure: { InstrumentName: { 'count': x, 'songs': [titles], 'added_eq': {EqName: count} } }
        log2_data = {} 

        def add(name, qty, source_inst=None):
            if qty <= 0: return
            needs[name] = needs.get(name, 0) + qty
            if source_inst:
                if source_inst not in log2_data:
                    log2_data[source_inst] = {'count': 0, 'songs': set(), 'added_eq': {}}
                log2_data[source_inst]['added_eq'][name] = log2_data[source_inst]['added_eq'].get(name, 0) + qty

        # 1. Calculate Max Simultaneous Usage (x) per Instrument Name
        max_usage = {} # Name -> Int
        piano_max_usage = 0
        
        inst_songs_map = {} # Name -> Set[SongTitle]

        # Define Piano Group
        piano_group_names = ["디지털 피아노", "신디사이저"]

        for song in self.data_handler.songs:
            current_song_counts = {} # Name -> Int
            current_piano_count = 0
            
            for session in song.sessions:
                inst = next((i for i in self.data_handler.instruments if i.id == session.instrument_id), None)
                if not inst: continue
                
                name = inst.name
                current_song_counts[name] = current_song_counts.get(name, 0) + 1
                
                if name not in inst_songs_map: inst_songs_map[name] = set()
                inst_songs_map[name].add(song.title)
                
                if name in piano_group_names:
                    current_piano_count += 1
            
            # Update global max per instrument
            for name, count in current_song_counts.items():
                max_usage[name] = max(max_usage.get(name, 0), count)
            
            # Update global max for piano group
            piano_max_usage = max(piano_max_usage, current_piano_count)

        # Initialize Log 2 Data with max usage and songs
        for name, x in max_usage.items():
            if x > 0:
                if name not in log2_data:
                    log2_data[name] = {'count': x, 'songs': inst_songs_map.get(name, set()), 'added_eq': {}}
                else:
                    log2_data[name]['count'] = x
                    log2_data[name]['songs'] = inst_songs_map.get(name, set())

        # 2. Apply Logic based on Max Usage (x)
        processed_instruments = set() # Names processed by specific rules

        # --- Specific Rules ---

        # 통기타 (Acoustic Guitar)
        ag_x = max_usage.get("통기타", 0)
        if ag_x > 0:
            processed_instruments.add("통기타")
            if ag_x == 1:
                add("TS 5m", 1, "통기타")
                add("XLR 5m", 1, "통기타")
            elif ag_x >= 2:
                add("TS 5m", ag_x, "통기타")
                add("XLR 5m", ag_x, "통기타")
                add("패시브 DI 모노", ag_x - 1, "통기타")
                log1_lines.append("통기타 x>=2일 때: 2개째의 통기타부터는 패시브 DI 모노로 계수했습니다.")

        # 일렉기타 (Electric Guitar)
        eg_x = max_usage.get("일렉기타", 0)
        if eg_x > 0:
            processed_instruments.add("일렉기타")
            
            if eg_x >= 3:
                log1_lines.append("일렉기타 x>=3일 때: 3개째의 일렉기타부터는 계산하지 않았습니다.")
            
            # Common parts for EG logic
            def apply_eg_logic(cable_count, amp_num, source_name):
                # cable_count: 3, 2, 1 (from settings)
                # TS 5m +1, XLR 5m+1, SM57 +1, Short Stand +1 are common
                add("TS 5m", 1, source_name)
                add("XLR 5m", 1, source_name)
                add("SM57", 1, source_name)
                add("숏 마이크 스탠드", 1, source_name)
                
                amp_name = f"일렉 앰프{amp_num}"
                add(amp_name, 1, source_name)
                
                if cable_count == 3:
                    add("TS 3m", 2, source_name)
                elif cable_count == 2:
                    add("TS 3m", 1, source_name)
                # if 1, 0 extra TS 3m

            # EG 1 Logic
            eg1_setting = settings.get('eg1_cable', 3) 
            apply_eg_logic(eg1_setting, 1, "일렉기타")

            # EG 2 Logic (Only if x >= 2)
            if eg_x >= 2:
                eg2_setting = settings.get('eg2_cable', 3)
                apply_eg_logic(eg2_setting, 2, "일렉기타")

        # 베이스기타 (Bass Guitar)
        bass_x = max_usage.get("베이스", 0)
        if bass_x >= 1:
            processed_instruments.add("베이스")
            if bass_x >= 2:
                log1_lines.append("베이스 x>=2일 때: 2개째의 베이스기타부터는 계산하지 않았습니다.")
            
            add("TS 5m", 1, "베이스")
            add("TS 3m", 1, "베이스")
            add("XLR 5m", 1, "베이스")
            add("베이스 앰프", 1, "베이스")

        # 피아노/신디 (Piano Group)
        piano_key = "피아노/신디"
        if piano_max_usage > 0:
            for name in piano_group_names:
                if name in max_usage: processed_instruments.add(name)
            
            # Update Log 2 data manually for grouped instruments
            songs_union = set()
            for name in piano_group_names:
                if name in inst_songs_map:
                    songs_union.update(inst_songs_map[name])
            log2_data[piano_key] = {'count': piano_max_usage, 'songs': songs_union, 'added_eq': {}}

            if piano_max_usage >= 3:
                log1_lines.append("피아노/신디 x>=3일 때: 3개째의 피아노/신디부터는 계산하지 않았습니다.")

            def apply_piano_logic(di_type_idx, source_name):
                # di_type_idx: 0 (Passive), 1 (Active)
                add("TS 5m", 2, source_name)
                add("XLR 5m", 2, source_name)
                if di_type_idx == 0:
                    add("패시브 DI 스테레오", 1, source_name)
                else:
                    add("액티브 DI 스테레오", 1, source_name)

            # Piano 1 Logic
            p1_setting = settings.get('piano1_di', 0)
            apply_piano_logic(p1_setting, piano_key)

            # Piano 2 Logic (Only if x >= 2)
            if piano_max_usage >= 2:
                p2_setting = settings.get('piano2_di', 0)
                apply_piano_logic(p2_setting, piano_key)

        # 드럼 (Drum)
        drum_x = max_usage.get("드럼", 0)
        if drum_x > 0:
            processed_instruments.add("드럼")
            
            # Check owned count of Drum Mic Set
            drum_mic_eq = next((e for e in self.data_handler.equipments if e.name == "드럼 마이크 세트"), None)
            drum_mic_owned = drum_mic_eq.owned_count if drum_mic_eq else 0
            
            if drum_mic_owned == 0:
                add("드럼 마이크 세트", 1, "드럼")
                log1_lines.append("드럼 마이크 세트가 없어 롱/숏 마이크 스탠드 필요 개수는 추가하지 않고, 드럼 마이크 세트만 1개 추가했습니다.")
            else:
                add("드럼 마이크 세트", 1, "드럼")
                add("롱 마이크 스탠드", 5, "드럼")
                add("숏 마이크 스탠드", 1, "드럼")
                add("XLR 5m", 6, "드럼")

        # 카혼 (Cajon)
        cajon_x = max_usage.get("카혼", 0)
        if cajon_x > 0:
            processed_instruments.add("카혼")
            add("SM57", 2 * cajon_x, "카혼")
            add("XLR 5m", 2 * cajon_x, "카혼")
            add("롱 마이크 스탠드", 1 * cajon_x, "카혼")
            add("숏 마이크 스탠드", 1 * cajon_x, "카혼")

        # 퍼커션 (Percussion)
        percussion_x = max_usage.get("퍼커션", 0)
        if percussion_x > 0:
            processed_instruments.add("퍼커션")
            add("SM57", 3, "퍼커션")
            add("XLR 5m", 3, "퍼커션")
            add("롱 마이크 스탠드", 3, "퍼커션")

        # 보컬/랩 (Vocal/Rap)
        vocal_x = max_usage.get("보컬/랩", 0)
        if vocal_x > 0:
            processed_instruments.add("보컬/랩")
            add("SM58 (보컬 마이크)", vocal_x, "보컬/랩")
            add("XLR 5m", vocal_x, "보컬/랩")
            add("롱 마이크 스탠드", vocal_x, "보컬/랩")

        # 핀마이크·바디팩 (Pin Mic/Bodypack) - Wind & String Logic
        wind_string_inst_names = []
        for inst in self.data_handler.instruments:
            if inst.category in [InstrumentCategory.WIND.value, InstrumentCategory.STRING.value]:
                wind_string_inst_names.append(inst.name)
        
        if wind_string_inst_names:
            max_ws_count = 0
            ws_songs = set()
            
            for song in self.data_handler.songs:
                # Count wind/string sessions in this song
                count = 0
                for sess in song.sessions:
                    inst = next((i for i in self.data_handler.instruments if i.id == sess.instrument_id), None)
                    if inst and inst.name in wind_string_inst_names:
                        count += 1
                
                if count > max_ws_count:
                    max_ws_count = count
                    ws_songs = {song.title}
                elif count == max_ws_count and count > 0:
                    ws_songs.add(song.title)
            
            if max_ws_count > 0:
                # Add to processed to skip general logic
                for name in wind_string_inst_names:
                    processed_instruments.add(name)
                
                # Add Equipment
                key = "핀마이크·바디팩"
                # Initialize log2_data for this virtual key
                log2_data[key] = {'count': max_ws_count, 'songs': ws_songs, 'added_eq': {}}
                
                add("핀마이크·바디팩", max_ws_count, key)
                add("XLR 5m", max_ws_count, key)

        # --- General Logic (Fallback based on Connection Type) ---
        for name, x in max_usage.items():
            if name in processed_instruments:
                continue
            if name in piano_group_names: continue # Already handled
            
            inst = next((i for i in self.data_handler.instruments if i.name == name), None)
            if not inst: continue

            # Initialize log data if not exists
            if name not in log2_data:
                log2_data[name] = {'count': x, 'songs': inst_songs_map.get(name, set()), 'added_eq': {}}

            # Check Connection Type (Fallback)
            ctype = inst.connection_type
            if ctype == ConnectionType.TS_ACTIVE.value:
                add("TS 5m", x, name)
                add("XLR 5m", x, name)
                add("패시브 DI 모노", x, name)
            elif ctype == ConnectionType.TS_PASSIVE.value:
                add("TS 5m", x, name)
                add("XLR 5m", x, name)
                add("액티브 DI 모노", x, name)
            elif ctype == ConnectionType.BALANCED.value: # XLR
                add("XLR 5m", x, name)
            elif ctype == ConnectionType.NONE.value: # X
                add("XLR 5m", x, name)
                add("SM57", x, name)
                add("롱 마이크 스탠드", x, name)

        # Prepare Log 2 Lines
        for inst_name, data in log2_data.items():
            # Skip individual piano parts as they are merged into "피아노/신디"
            if inst_name in ["디지털 피아노", "신디사이저"]:
                continue
            
            # Skip wind/string instruments as they are merged into "핀마이크·바디팩"
            if inst_name in wind_string_inst_names:
                continue

            if data['count'] > 0:
                songs_str = ", ".join(sorted(list(data['songs'])))
                added_eq_str_list = []
                for eq_name, count in data['added_eq'].items():
                    added_eq_str_list.append(f"{eq_name}")
                added_eq_str = ", ".join(added_eq_str_list)
                
                line = f"[{inst_name}] {data['count']}개\n곡: {songs_str}\n   → {added_eq_str}"
                log2_lines.append(line)
        
        return needs, log1_lines, log2_lines

    def calculate_needs(self, settings: dict):
        """
        Returns: (success: bool, log1_lines: list, log2_lines: list)
        """
        needs, log1_lines, log2_lines = self.get_calculated_requirements(settings)

        # 3. Create Command to Update Equipment Models
        new_requirements = {}
        for eq in self.data_handler.equipments:
            count = needs.get(eq.name, 0)
            new_requirements[eq.id] = count
            
        cmd = BatchUpdateRequirementsCommand(self.data_handler, new_requirements, self.data_changed)
        self.undo_stack.push(cmd)
        
        return True, log1_lines, log2_lines
