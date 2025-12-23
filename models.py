from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

# Constants
DEFAULT_SECTION_NAMES = [
    "곡 전반", "Intro", "Verse 1 (1절)", "Verse 2 (2절)", "Verse 3 (3절)", "Pre-Chorus 1 (1절)", 
    "Pre-Chorus 2 (2절)", "Pre-Chorus 3 (3절)", "Chorus 1 (1절 후렴)", "Chorus 2 (2절 후렴)", "Chorus 3 (3절 후렴)", 
    "Bridge", "Interlude (간주)", "Interlude 1 (간주)", "Interlude 2 (간주)", "Outro", 
    "솔로", "솔로 (기타)", "솔로 (피아노)", "솔로 (베이스)", "솔로 (드럼)"
]

# Enums
class Grade(Enum):
    BON4 = "본4"
    BON3 = "본3"
    BON2 = "본2"
    BON1 = "본1"
    YE2 = "예2"
    YE1 = "예1"

class SkillLevel(Enum):
    YOUTUBER = "유튜버" # 16비트 bpm 180 이상
    EXPERT = "고수"    # 16비트 bpm 160-180
    HIGH = "상"      # 16비트 bpm 140-160
    MID = "중"       # 16비트 bpm 120-140
    LOW = "하"       # 16비트 bpm 90-120
    BEGINNER = "초보"  # 16비트 bpm 90 미만

class InstrumentCategory(Enum):
    GUITAR = "기타 계열"
    PIANO = "피아노 계열"
    PERCUSSION = "타악기"
    WIND = "관악기"
    STRING = "현악기"
    ETC = "etc"

class ConnectionType(Enum):
    TS_ACTIVE = "TS OUT(액티브)"
    TS_PASSIVE = "TS OUT(패시브)"
    BALANCED = "BALANCED OUT"
    NONE = "X"

class SongCategory(Enum):
    VOCAL = "보컬곡"
    INSTRUMENTAL = "기악곡"

# Base Mixin for Serialization
class SerializableMixin:
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

@dataclass
class Instrument(SerializableMixin):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    category: str = InstrumentCategory.GUITAR.value
    connection_type: str = ConnectionType.NONE.value
    is_default: bool = False # New field to prevent deletion

@dataclass
class MemberInstrument(SerializableMixin):
    instrument_id: str  # References Instrument.id
    skill: str = SkillLevel.BEGINNER.value

@dataclass
class Member(SerializableMixin):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    grade: str = Grade.YE1.value
    instruments: List[MemberInstrument] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data['instruments'] = [i.to_dict() for i in self.instruments]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        if 'instruments' in data:
            data['instruments'] = [MemberInstrument.from_dict(i) for i in data['instruments']]
        return cls(**data)

@dataclass
class SongSession(SerializableMixin):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    instrument_id: str = "" # References Instrument.id
    # For Vocal: max_note (E5-C7), For Inst: max_beat (1, 4, 8, 16, 24, 32)
    # Storing as string or distinct fields? String is flexible.
    difficulty_param: str = ""

@dataclass
class CueSection(SerializableMixin):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "새 섹션" # Intro, Verse 1, etc.
    # Notes for each instrument in the song
    # Key: instrument_id (or session_id?), Value: note string
    # Using session_id is safer as one song might have 2 Guitars
    instrument_notes: Dict[str, str] = field(default_factory=dict) 
    memo: str = ""

@dataclass
class Song(SerializableMixin):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "새 곡"
    nickname: str = "" # Added nickname field
    bpm: int = 100
    category: str = SongCategory.INSTRUMENTAL.value
    reference_url: str = ""
    sessions: List[SongSession] = field(default_factory=list)
    cue_sections: List[CueSection] = field(default_factory=list) # Added

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data['sessions'] = [s.to_dict() for s in self.sessions]
        data['cue_sections'] = [s.to_dict() for s in self.cue_sections]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        if 'sessions' in data:
            data['sessions'] = [SongSession.from_dict(s) for s in data['sessions']]
        # Handle nickname if missing in older files
        if 'nickname' not in data:
             data['nickname'] = ""
        # Handle cue_sections
        if 'cue_sections' in data:
            data['cue_sections'] = [CueSection.from_dict(s) for s in data['cue_sections']]
        else:
            data['cue_sections'] = []
            
        return cls(**data)

@dataclass
class Equipment(SerializableMixin):
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    owned_count: int = 0
    required_count: int = 0
    is_default: bool = False # New field to prevent deletion

# To manage session assignments
@dataclass
class SessionAssignment(SerializableMixin):
    song_id: str
    session_id: str # References SongSession.id
    member_id: Optional[str] = None # References Member.id, None if unassigned
    ignore_warnings: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        # Handle ignore_warnings if missing in older files
        if 'ignore_warnings' not in data:
            data['ignore_warnings'] = False
        return cls(**data)
