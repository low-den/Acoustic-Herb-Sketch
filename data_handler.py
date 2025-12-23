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
            "TS 3m", "TS 5m", "XLR 5m", "SM58 (보컬 마이크)", "SM57", "핀마이크·바디팩", "드럼 마이크 세트",
            "롱 마이크 스탠드", "숏 마이크 스탠드", "일렉 앰프1", "일렉 앰프2", "베이스 앰프", 
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
