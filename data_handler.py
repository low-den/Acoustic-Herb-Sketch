import json
import os
from typing import List, Set
from models import Member, Instrument, Song, Equipment, SessionAssignment, InstrumentCategory, ConnectionType, SongCategory, SongSession

class DataHandler:
    def __init__(self, filepath: str = "data.acou"):
        self.filepath = filepath
        self.members: List[Member] = []
        self.instruments: List[Instrument] = []
        self.songs: List[Song] = []
        self.equipments: List[Equipment] = []
        self.assignments: List[SessionAssignment] = []
        self.sound_design_settings: dict = {}
        self.performance_memo: str = ""
        
        self.recent_files: List[str] = []
        self.load_recent_files_list()

    def save_data(self, filepath: str = None):
        target_path = filepath if filepath else self.filepath
        if not target_path:
            return # Should handle error

        data = {
            "members": [m.to_dict() for m in self.members],
            "instruments": [i.to_dict() for i in self.instruments],
            "songs": [s.to_dict() for s in self.songs],
            "equipments": [e.to_dict() for e in self.equipments],
            "assignments": [a.to_dict() for a in self.assignments],
            "sound_design_settings": self.sound_design_settings,
            "performance_memo": self.performance_memo
        }
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            self.filepath = target_path
            self.add_recent_file(target_path)
            
        except Exception as e:
            print(f"Failed to save data: {e}")
            raise e

    def load_data(self, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Use SerializableMixin logic mostly via from_dict
            self.members = [Member.from_dict(m) for m in data.get("members", [])]
            self.instruments = [Instrument.from_dict(i) for i in data.get("instruments", [])]
            self.songs = [Song.from_dict(s) for s in data.get("songs", [])]
            self.equipments = [Equipment.from_dict(e) for e in data.get("equipments", [])]
            self.assignments = [SessionAssignment.from_dict(a) for a in data.get("assignments", [])]
            self.sound_design_settings = data.get("sound_design_settings", {})
            self.performance_memo = data.get("performance_memo", "")
            
            self.filepath = filepath
            self.check_integrity()
            self.migration_log = self.migrate_data()
            self.add_recent_file(filepath)
            
        except (json.JSONDecodeError, KeyError, Exception) as e:
            print(f"Error loading data: {e}")
            raise e # Let UI handle error

    def create_new_project(self, filepath: str):
        # Clear data
        self.members = []
        self.instruments = []
        self.songs = []
        self.equipments = []
        self.assignments = []
        self.sound_design_settings = {}
        self.performance_memo = ""
        
        # Load defaults
        self.create_defaults()
        
        # Save immediately
        self.save_data(filepath)

    def check_integrity(self):
        member_ids = {m.id for m in self.members}
        song_ids = {s.id for s in self.songs}
        
        # Ensure all equipments have IDs
        import uuid
        for eq in self.equipments:
            if not eq.id:
                eq.id = str(uuid.uuid4())
        
        valid_session_ids = set()
        for song in self.songs:
            for session in song.sessions:
                valid_session_ids.add(session.id)

        valid_assignments = []
        for a in self.assignments:
            if a.song_id not in song_ids:
                continue
            if a.session_id not in valid_session_ids:
                continue
            if a.member_id and a.member_id not in member_ids:
                a.member_id = None
            valid_assignments.append(a)
        
        self.assignments = valid_assignments

    def migrate_data(self):
        """Migrates data from older versions to the current schema.
        Returns a list of change descriptions (empty if no changes were made).
        """
        changes = []

        # 1. Instruments: Reset connection_type to default 'X'
        for inst in self.instruments:
            if hasattr(inst, 'connection_type') and inst.connection_type != ConnectionType.NONE.value:
                inst.connection_type = ConnectionType.NONE.value
                if not changes or not any("연결 방식" in c for c in changes):
                    changes.append("악기 연결 방식 설정이 초기화되었습니다. (음향 설계에서 관리)")

        # 2. Equipment name changes
        eq_rename_map = {
            "SM57": "SM57 (악기 마이크)",
            "일렉 앰프1": "일렉 앰프",
            "일렉 앰프2": "일렉 앰프",
        }
        merged_ids = []  # Track IDs of equipment merged into another
        for eq in self.equipments:
            if eq.name in eq_rename_map:
                new_name = eq_rename_map[eq.name]
                # Check if target name already exists (for merge case like 앰프1+앰프2 → 앰프)
                existing = next((e for e in self.equipments if e.name == new_name and e.id != eq.id), None)
                if existing and eq.name.startswith("일렉 앰프"):
                    # Merge: add owned_count to existing, mark for removal
                    existing.owned_count += eq.owned_count
                    merged_ids.append(eq.id)
                    changes.append(f"장비 '{eq.name}'이(가) '{new_name}'으로 통합되었습니다.")
                else:
                    old_name = eq.name
                    eq.name = new_name
                    changes.append(f"장비명 변경: '{old_name}' → '{new_name}'")

        # Remove merged equipment
        if merged_ids:
            self.equipments = [e for e in self.equipments if e.id not in merged_ids]

        # 3. Sound design settings: convert legacy keys to new format
        old_settings = self.sound_design_settings
        new_settings = {}
        settings_migrated = False

        legacy_key_map = {
            'eg1_cable': ('일렉기타_0_conn', self._convert_eg_cable),
            'eg2_cable': ('일렉기타_1_conn', self._convert_eg_cable),
            'piano1_di': ('디지털 피아노_0_conn', None),  # 0=패시브, 1=액티브 (same)
            'piano2_di': ('신디사이저_0_conn', None),     # 0=패시브, 1=액티브 (same)
        }

        has_legacy_keys = any(k in old_settings for k in legacy_key_map)

        if has_legacy_keys:
            # Copy non-legacy keys as-is
            for key, value in old_settings.items():
                if key not in legacy_key_map:
                    new_settings[key] = value

            # Convert legacy keys
            for old_key, (new_key, converter) in legacy_key_map.items():
                if old_key in old_settings:
                    old_val = old_settings[old_key]
                    new_val = converter(old_val) if converter else old_val
                    new_settings[new_key] = new_val
                    settings_migrated = True

            if settings_migrated:
                self.sound_design_settings = new_settings
                changes.append("음향 설계 설정이 새 형식으로 변환되었습니다.")

        return changes

    @staticmethod
    def _convert_eg_cable(old_val):
        """Converts old eg_cable value (3=FxLoop, 2=NoFxLoop, 1=DirectAmp) 
        to new conn index (0=FxLoop, 1=NoFxLoop, 2=DirectAmp)."""
        # Old: 0=3개(FxLoop), 1=2개(NoFxLoop), 2=1개(직결)
        # New: 0=FxLoop, 1=NoFxLoop, 2=기타-앰프
        # The old radio button index maps directly to new index
        return old_val

    def create_defaults(self):
        # Default Instruments
        defaults_inst = [
            (InstrumentCategory.GUITAR, ["통기타", "일렉기타", "베이스", "클래식기타", "우쿨렐레"]),
            (InstrumentCategory.PIANO, ["디지털 피아노", "신디사이저", "멜로디언", "실로폰"]),
            (InstrumentCategory.PERCUSSION, ["드럼", "카혼", "젬베", "퍼커션", "쉐이커", "캐스터네츠", "트라이앵글"]),
            (InstrumentCategory.WIND, ["플룻", "클라리넷", "색소폰", "트럼펫", "트럼본", "호른", "오보에", "바순"]),
            (InstrumentCategory.STRING, ["바이올린", "첼로", "비올라", "콘트라베이스"]),
            (InstrumentCategory.ETC, ["보컬/랩"]),
        ]
        
        self.instruments = []
        
        # Define connection types for defaults
        conn_map = {
            "통기타": ConnectionType.TS_ACTIVE.value,
            "일렉기타": ConnectionType.TS_PASSIVE.value,
            "베이스": ConnectionType.TS_PASSIVE.value,
            "클래식기타": ConnectionType.TS_ACTIVE.value,
            "디지털 피아노": ConnectionType.TS_ACTIVE.value,
            "신디사이저": ConnectionType.TS_ACTIVE.value,
            "보컬/랩": ConnectionType.BALANCED.value 
        }
        
        for cat, names in defaults_inst:
            for name in names:
                conn_type = ConnectionType.NONE.value
                if name in conn_map:
                    conn_type = conn_map[name]
                
                self.instruments.append(Instrument(name=name, category=cat.value, connection_type=conn_type, is_default=True))

        # Default Song
        vocal_inst = next((i for i in self.instruments if i.name == "보컬/랩"), None)
        default_song = Song(title="새 곡", bpm=100, category=SongCategory.VOCAL.value)
        if vocal_inst:
            default_song.sessions.append(SongSession(instrument_id=vocal_inst.id, difficulty_param="A5"))
            
        self.songs = [default_song]

        # Default Equipment
        default_eqs = [
            "TS 3m", "TS 5m", "XLR 5m", "SM58 (보컬 마이크)", "SM57 (악기 마이크)", "핀마이크·바디팩", "드럼 마이크 세트",
            "롱 마이크 스탠드", "숏 마이크 스탠드", "일렉 앰프", "베이스 앰프", 
            "패시브 DI 모노", "패시브 DI 스테레오", "액티브 DI 모노", "액티브 DI 스테레오"
        ]
        self.equipments = []
        for name in default_eqs:
            self.equipments.append(Equipment(name=name, is_default=True))

    # Recent Files Management
    def load_recent_files_list(self):
        config_path = "recent_files.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.recent_files = json.load(f)
            except:
                self.recent_files = []
        else:
            self.recent_files = []

    def save_recent_files_list(self):
        config_path = "recent_files.json"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.recent_files, f, ensure_ascii=False, indent=4)
        except:
            pass

    def add_recent_file(self, filepath: str):
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        
        # Keep max 10
        if len(self.recent_files) > 10:
            self.recent_files = self.recent_files[:10]
            
        self.save_recent_files_list()
