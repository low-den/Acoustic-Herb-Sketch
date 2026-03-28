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
        Calculates equipment requirements based on per-instance connection method settings.
        Each instrument instance (e.g., 일렉기타_0, 일렉기타_1) has its own connection
        method stored in settings as '{name}_{index}_conn'.

        Returns: (needs: dict, log1_lines: list, log2_lines: list)
        """
        needs = {}  # EquipmentName -> Count
        log1_lines = []
        log2_lines = []

        # Log 2 Data: { InstrumentName: { 'count': x, 'songs': set, 'added_eq': {EqName: count} } }
        log2_data = {}

        def add(name, qty, source_inst=None):
            if qty <= 0: return
            needs[name] = needs.get(name, 0) + qty
            if source_inst:
                if source_inst not in log2_data:
                    log2_data[source_inst] = {'count': 0, 'songs': set(), 'added_eq': {}}
                log2_data[source_inst]['added_eq'][name] = log2_data[source_inst]['added_eq'].get(name, 0) + qty

        # 1. Calculate Max Simultaneous Usage (x) per Instrument Name
        max_usage = {}  # Name -> Int
        inst_songs_map = {}  # Name -> Set[SongTitle]

        for song in self.data_handler.songs:
            current_song_counts = {}  # Name -> Int

            for session in song.sessions:
                inst = next((i for i in self.data_handler.instruments if i.id == session.instrument_id), None)
                if not inst: continue

                name = inst.name
                current_song_counts[name] = current_song_counts.get(name, 0) + 1

                if name not in inst_songs_map: inst_songs_map[name] = set()
                inst_songs_map[name].add(song.title)

            for name, count in current_song_counts.items():
                max_usage[name] = max(max_usage.get(name, 0), count)

        # Initialize Log 2 Data with max usage and songs
        for name, x in max_usage.items():
            if x > 0:
                log2_data[name] = {'count': x, 'songs': inst_songs_map.get(name, set()), 'added_eq': {}}

        # 2. Build category sets for instrument classification
        guitar_family_names = set()  # 기타계열 (excluding 일렉기타, 베이스)
        for inst in self.data_handler.instruments:
            if inst.category == InstrumentCategory.GUITAR.value and inst.name not in ["일렉기타", "베이스"]:
                guitar_family_names.add(inst.name)

        # Names handled by specific rules (everything else falls to "나머지")
        specific_names = {"보컬/랩", "일렉기타", "베이스", "드럼", "카혼", "퍼커션", "디지털 피아노", "신디사이저"}
        specific_names.update(guitar_family_names)

        processed_instruments = set()

        # --- 보컬/랩 ---
        vocal_x = max_usage.get("보컬/랩", 0)
        if vocal_x > 0:
            processed_instruments.add("보컬/랩")
            for i in range(vocal_x):
                key = f"보컬/랩_{i}_conn"
                conn = settings.get(key, 0)  # 0: 믹서 직결
                if conn == 0:  # 믹서 직결
                    add("XLR 5m", 1, "보컬/랩")
                    add("롱 마이크 스탠드", 1, "보컬/랩")
                elif conn == 1:  # 보컬 이펙터
                    add("XLR 5m", 2, "보컬/랩")
                    add("롱 마이크 스탠드", 1, "보컬/랩")

        # --- 기타계열 (일렉기타, 베이스 제외) ---
        for gname in guitar_family_names:
            gx = max_usage.get(gname, 0)
            if gx > 0:
                processed_instruments.add(gname)
                for i in range(gx):
                    key = f"{gname}_{i}_conn"
                    conn = settings.get(key, 0)  # 0: 통기타 이펙터
                    if conn == 0:  # 통기타 이펙터
                        add("TS 3m", 1, gname)
                        add("XLR 5m", 1, gname)
                    elif conn == 1:  # 믹서 직결
                        add("TS 5m", 1, gname)
                    elif conn == 2:  # 마이킹
                        add("XLR 5m", 1, gname)
                    elif conn == 3:  # 패시브 DI
                        add("패시브 DI 모노", 1, gname)
                        add("TS 3m", 1, gname)
                        add("XLR 5m", 1, gname)

        # --- 일렉기타 ---
        eg_x = max_usage.get("일렉기타", 0)
        if eg_x > 0:
            processed_instruments.add("일렉기타")
            if eg_x >= 3:
                log1_lines.append("일렉기타 3개 이상: 3개째의 일렉기타부터는 앰프를 추가하지 않았습니다.")

            for i in range(eg_x):
                key = f"일렉기타_{i}_conn"
                conn = settings.get(key, 0)  # 0: Fx Loop 사용
                if conn == 0:  # 기타-이펙터-앰프 (Fx Loop 사용)
                    add("TS 3m", 3, "일렉기타")
                elif conn == 1:  # 기타-이펙터-앰프 (Fx Loop 미사용)
                    add("TS 3m", 2, "일렉기타")
                elif conn == 2:  # 기타-앰프
                    add("TS 3m", 1, "일렉기타")

                add("XLR 5m", 1, "일렉기타")
                add("SM57 (악기 마이크)", 1, "일렉기타")
                add("숏 마이크 스탠드", 1, "일렉기타")

                # Amp
                if i < 2:
                    add("일렉 앰프", 1, "일렉기타")

        # --- 베이스 ---
        bass_x = max_usage.get("베이스", 0)
        if bass_x > 0:
            processed_instruments.add("베이스")
            if bass_x >= 2:
                log1_lines.append("베이스 2개 이상: 2개째의 베이스부터는 앰프를 추가하지 않았습니다.")

            for i in range(bass_x):
                key = f"베이스_{i}_conn"
                conn = settings.get(key, 0)  # 0: 이펙터-앰프/믹서
                if conn == 0:  # 기타-이펙터-앰프/믹서
                    add("TS 3m", 2, "베이스")
                    add("XLR 5m", 1, "베이스")
                elif conn == 1:  # 기타-이펙터-앰프 마이킹
                    add("TS 3m", 1, "베이스")
                    add("XLR 5m", 1, "베이스")
                    add("SM57 (악기 마이크)", 1, "베이스")
                    add("숏 마이크 스탠드", 1, "베이스")

                # Amp (1개만)
                if i < 1:
                    add("베이스 앰프", 1, "베이스")

        # --- 디지털 피아노 ---
        dp_x = max_usage.get("디지털 피아노", 0)
        if dp_x > 0:
            processed_instruments.add("디지털 피아노")
            for i in range(dp_x):
                key = f"디지털 피아노_{i}_conn"
                conn = settings.get(key, 0)  # 0: 패시브DI
                if conn == 0:  # 패시브DI
                    add("패시브 DI 스테레오", 1, "디지털 피아노")
                elif conn == 1:  # 액티브DI
                    add("액티브 DI 스테레오", 1, "디지털 피아노")
                add("TS 3m", 2, "디지털 피아노")
                add("XLR 5m", 2, "디지털 피아노")

        # --- 신디사이저 ---
        synth_x = max_usage.get("신디사이저", 0)
        if synth_x > 0:
            processed_instruments.add("신디사이저")
            for i in range(synth_x):
                key = f"신디사이저_{i}_conn"
                conn = settings.get(key, 0)  # 0: 패시브DI
                if conn == 0:  # 패시브DI
                    add("패시브 DI 스테레오", 1, "신디사이저")
                elif conn == 1:  # 액티브DI
                    add("액티브 DI 스테레오", 1, "신디사이저")
                add("TS 3m", 2, "신디사이저")
                add("XLR 5m", 2, "신디사이저")

        # --- 드럼 ---
        drum_x = max_usage.get("드럼", 0)
        if drum_x > 0:
            processed_instruments.add("드럼")
            add("드럼 마이크 세트", 1, "드럼")
            add("숏 마이크 스탠드", 1, "드럼")
            add("롱 마이크 스탠드", 2, "드럼")
            add("XLR 5m", 6, "드럼")

        # --- 카혼 ---
        cajon_x = max_usage.get("카혼", 0)
        if cajon_x > 0:
            processed_instruments.add("카혼")
            for i in range(cajon_x):
                key = f"카혼_{i}_conn"
                conn = settings.get(key, 0)  # 0: 마이킹
                if conn == 0:  # 마이킹
                    add("SM57 (악기 마이크)", 2, "카혼")
                    add("XLR 5m", 2, "카혼")
                    add("숏 마이크 스탠드", 1, "카혼")
                    add("롱 마이크 스탠드", 1, "카혼")
                elif conn == 1:  # 픽업-믹서직결
                    add("TS 5m", 1, "카혼")
                elif conn == 2:  # 픽업-DI
                    add("액티브 DI 모노", 1, "카혼")
                    add("TS 3m", 1, "카혼")
                    add("XLR 5m", 1, "카혼")

        # --- 퍼커션 ---
        perc_x = max_usage.get("퍼커션", 0)
        if perc_x > 0:
            processed_instruments.add("퍼커션")
            add("SM57 (악기 마이크)", 3, "퍼커션")
            add("XLR 5m", 3, "퍼커션")
            add("롱 마이크 스탠드", 3, "퍼커션")

        # --- 나머지 모든 악기 ---
        for name, x in max_usage.items():
            if name in processed_instruments:
                continue

            for i in range(x):
                key = f"{name}_{i}_conn"
                conn = settings.get(key, 0)  # 0: SM58 마이킹
                if conn == 0:  # SM58 마이킹
                    add("SM58 (보컬 마이크)", 1, name)
                    add("XLR 5m", 1, name)
                elif conn == 1:  # SM57 마이킹
                    add("SM57 (악기 마이크)", 1, name)
                    add("XLR 5m", 1, name)
                elif conn == 2:  # 핀마이크·바디팩
                    add("핀마이크·바디팩", 1, name)
                    add("XLR 5m", 1, name)
                elif conn == 3:  # 픽업-믹서직결
                    add("TS 5m", 1, name)
                elif conn == 4:  # 픽업-DI
                    add("액티브 DI 모노", 1, name)
                    add("TS 3m", 1, name)
                    add("XLR 5m", 1, name)

        # Prepare Log 2 Lines
        for inst_name, data in log2_data.items():
            if data['count'] > 0 and data.get('added_eq'):
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
