from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import QObject, pyqtSignal
from models import SessionAssignment, Member, Song, SongSession, SkillLevel
from data_handler import DataHandler
import re

class AssignSessionCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, song_id: str, session_id: str, member_id: str, ignore_warnings: bool, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.song_id = song_id
        self.session_id = session_id
        self.new_member_id = member_id
        self.new_ignore_warnings = ignore_warnings
        self.update_signal = update_signal
        
        # Find existing assignment to save for undo
        self.old_member_id = None
        self.old_ignore_warnings = False
        self.existing_assignment = None
        
        for a in self.data_handler.assignments:
            if a.song_id == song_id and a.session_id == session_id:
                self.existing_assignment = a
                self.old_member_id = a.member_id
                self.old_ignore_warnings = a.ignore_warnings
                break
                
        self.setText(f"Assign Session")

    def redo(self):
        if self.existing_assignment:
            self.existing_assignment.member_id = self.new_member_id
            self.existing_assignment.ignore_warnings = self.new_ignore_warnings
        else:
            # Create new assignment record if it doesn't exist
            new_assignment = SessionAssignment(
                song_id=self.song_id, 
                session_id=self.session_id, 
                member_id=self.new_member_id,
                ignore_warnings=self.new_ignore_warnings
            )
            self.data_handler.assignments.append(new_assignment)
            
        self.update_signal.emit()

    def undo(self):
        if self.existing_assignment:
            self.existing_assignment.member_id = self.old_member_id
            self.existing_assignment.ignore_warnings = self.old_ignore_warnings
        else:
            to_remove = None
            for a in self.data_handler.assignments:
                if a.song_id == self.song_id and a.session_id == self.session_id and a.member_id == self.new_member_id:
                     to_remove = a
                     break
            if to_remove:
                self.data_handler.assignments.remove(to_remove)
            
        self.update_signal.emit()

class UpdateMemberAssignmentsCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, song_id: str, member_id: str, new_session_ids: list, ignore_warnings: bool, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.song_id = song_id
        self.member_id = member_id
        self.new_session_ids = new_session_ids
        self.new_ignore_warnings = ignore_warnings
        self.update_signal = update_signal
        self.setText(f"Update Assignments for {member_id}")
        
        self.old_state = {} # session_id -> (member_id, ignore_warnings)
        
        for a in self.data_handler.assignments:
            if a.song_id == song_id:
                self.old_state[a.session_id] = (a.member_id, a.ignore_warnings)

    def redo(self):
        existing_session_ids = [a.session_id for a in self.data_handler.assignments if a.song_id == self.song_id]
        
        # 1. Update existing assignments
        for a in self.data_handler.assignments:
            if a.song_id == self.song_id:
                if a.session_id in self.new_session_ids:
                    a.member_id = self.member_id
                    a.ignore_warnings = self.new_ignore_warnings
                elif a.member_id == self.member_id:
                    a.member_id = None
                    # Reset ignore_warnings when unassigning? Maybe default to False, or keep as is.
                    # Usually if unassigned, ignore_warnings doesn't matter, but better reset to clean state.
                    a.ignore_warnings = False 
                    
        # 2. Create missing assignments if any
        for sid in self.new_session_ids:
            if sid not in existing_session_ids:
                self.data_handler.assignments.append(SessionAssignment(
                    song_id=self.song_id, 
                    session_id=sid, 
                    member_id=self.member_id,
                    ignore_warnings=self.new_ignore_warnings
                ))
                existing_session_ids.append(sid)
                
        self.update_signal.emit()

    def undo(self):
        assignments_copy = list(self.data_handler.assignments)
        
        for a in assignments_copy:
            if a.song_id == self.song_id:
                if a.session_id in self.old_state:
                    saved_member_id, saved_ignore = self.old_state[a.session_id]
                    a.member_id = saved_member_id
                    a.ignore_warnings = saved_ignore
                else:
                    self.data_handler.assignments.remove(a)
                    
        self.update_signal.emit()

class SessionService(QObject):
    data_changed = pyqtSignal()
    
    def __init__(self, data_handler: DataHandler, undo_stack):
        super().__init__()
        self.data_handler = data_handler
        self.undo_stack = undo_stack

    def assign_member(self, song_id: str, session_id: str, member_id: str, ignore_warnings: bool = False):
        cmd = AssignSessionCommand(self.data_handler, song_id, session_id, member_id, ignore_warnings, self.data_changed)
        self.undo_stack.push(cmd)
        
    def update_member_assignments(self, song_id: str, member_id: str, new_session_ids: list, ignore_warnings: bool = False):
        cmd = UpdateMemberAssignmentsCommand(self.data_handler, song_id, member_id, new_session_ids, ignore_warnings, self.data_changed)
        self.undo_stack.push(cmd)

    def _note_to_int(self, note_str):
        if not note_str: return -1
        note_map = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
        
        try:
            match = re.match(r"([A-G]#?)([0-9]+)", note_str)
            if not match: return -1
            
            note = match.group(1)
            octave = int(match.group(2))
            
            val = octave * 12 + note_map.get(note, 0)
            return val
        except:
            return -1

    def validate_assignment(self, member: Member, song: Song, session: SongSession) -> list[str]:
        """
        Returns a list of warning messages. Empty if fine.
        """
        warnings = []
        if not member or not song or not session:
            return warnings

        # Find member's skill for this instrument
        member_inst = next((i for i in member.instruments if i.instrument_id == session.instrument_id), None)
        
        # Get instrument name
        inst_def = next((i for i in self.data_handler.instruments if i.id == session.instrument_id), None)
        inst_name = inst_def.name if inst_def else "Unknown"
        
        if not member_inst:
            # Member doesn't play this instrument
            warnings.append(f"{member.name}은(는) '{inst_name}'을(를) 할 수 없습니다.")
            return warnings

        # Logic 1: Vocal/Rap
        if inst_name == "보컬/랩":
            # Compare Highest Note
            req_note = self._note_to_int(session.difficulty_param)
            mem_note = self._note_to_int(member_inst.skill)
            
            if req_note != -1 and mem_note != -1:
                if mem_note < req_note:
                    warnings.append(f"{member.name}의 {inst_name} 음역({member_inst.skill})이 곡의 최고음({session.difficulty_param})보다 낮습니다.")
                
        # Logic 2: Instruments (Non-Vocal)
        else:
            # Special case: Youtuber can play anything (unlimited cap)
            # if member_inst.skill == SkillLevel.YOUTUBER.value:
            #     return warnings
            
            # Calculate levels for ordinal comparison
            # 5: Youtuber, 4: Expert, 3: High, 2: Mid, 1: Low, 0: Beginner
            skill_levels = {
                SkillLevel.YOUTUBER.value: 5,
                SkillLevel.EXPERT.value: 4,
                SkillLevel.HIGH.value: 3,
                SkillLevel.MID.value: 2,
                SkillLevel.LOW.value: 1,
                SkillLevel.BEGINNER.value: 0
            }
            
            skill_base_bpm = {
                SkillLevel.YOUTUBER.value: 180,
                SkillLevel.EXPERT.value: 160,
                SkillLevel.HIGH.value: 140,
                SkillLevel.MID.value: 120,
                SkillLevel.LOW.value: 90,
                SkillLevel.BEGINNER.value: 50 
            }
            
            member_level_idx = skill_levels.get(member_inst.skill, 0)
            member_base = skill_base_bpm.get(member_inst.skill, 0)
            member_cap_val = member_base * 16 # Skill x 16

            # Calculate Song Requirement
            try:
                max_beat = int(session.difficulty_param)
            except:
                max_beat = 16 # Default fallback
                
            song_req_val = song.bpm * max_beat
            
            # Determine "Required Skill Level"
            req_level_idx = 0
            if song_req_val > 2880: # > 180*16
                 req_level_idx = 5 # Youtuber
            elif song_req_val > 2560: # > 160*16
                 req_level_idx = 4 # Expert
            elif song_req_val > 2240: # > 140*16
                 req_level_idx = 3 # High
            elif song_req_val > 1920: # > 120*16
                 req_level_idx = 2 # Mid
            elif song_req_val > 1440: # > 90*16
                 req_level_idx = 1 # Low
            else:
                 req_level_idx = 0 # Beginner
            
            # 1. Check Too Low
            # Youtuber exception applies ONLY here
            if song_req_val > member_cap_val and member_inst.skill != SkillLevel.YOUTUBER.value:
                warnings.append(f"{member.name}의 {inst_name} 실력({member_inst.skill})이 곡의 난이도(BPM {song.bpm} x {max_beat}비트)에 비해 부족합니다.")

            # 2. Check Too High (Member Level >= Req Level + 2)
            # If song_req_val >= 2880, skip Too High warning.
            
            if song_req_val >= 2880:
                pass # Skip Too High check
            elif member_level_idx >= req_level_idx + 3:
                warnings.append(f"{member.name}의 {inst_name} 실력({member_inst.skill})이 곡의 난이도에 비해 너무 높습니다.")
        
        return warnings

    def get_assignment(self, song_id, session_id):
        for a in self.data_handler.assignments:
            if a.song_id == song_id and a.session_id == session_id:
                return a.member_id
        return None
    
    def get_assignment_object(self, song_id, session_id):
        for a in self.data_handler.assignments:
            if a.song_id == song_id and a.session_id == session_id:
                return a
        return None

    def get_member_assignments_for_song(self, song_id, member_id):
        session_ids = []
        for a in self.data_handler.assignments:
            if a.song_id == song_id and a.member_id == member_id:
                session_ids.append(a.session_id)
        return session_ids

    def get_assignment_stats(self):
        # Calculate stats for all members
        # Return: { member_id: "OVER" | "UNDER" | "NORMAL" | "NONE" }
        stats = {}
        
        # 1. Calculate count for each member
        member_counts = {}
        valid_members_count = 0
        total_count = 0
        
        for m in self.data_handler.members:
            count = 0
            for a in self.data_handler.assignments:
                if a.member_id == m.id:
                    # Check if session is Vocal/Rap? No, prompt says "보컬 포함 배정 개수"
                    count += 1
            member_counts[m.id] = count
            
            if count >= 1:
                valid_members_count += 1
                total_count += count
                
        # 2. Calculate Average (x)
        if valid_members_count > 0:
            avg = total_count / valid_members_count
        else:
            avg = 0
            
        # 3. Determine Status
        for m_id, count in member_counts.items():
            if count == 0:
                stats[m_id] = "NONE" # No status for 0
            elif count >= avg + 1:
                stats[m_id] = "OVER"
            elif count <= avg - 1:
                stats[m_id] = "UNDER"
            else:
                stats[m_id] = "NORMAL"
                
        return stats

    def get_all_warnings(self) -> list[str]:
        all_warnings = []
        
        # 1. Unassigned Session Warnings
        for song in self.data_handler.songs:
            for session in song.sessions:
                is_assigned = False
                for a in self.data_handler.assignments:
                    if a.song_id == song.id and a.session_id == session.id and a.member_id:
                        is_assigned = True
                        break
                
                if not is_assigned:
                    inst = next((i for i in self.data_handler.instruments if i.id == session.instrument_id), None)
                    inst_name = inst.name if inst else "Unknown"
                    prefix = f"[{song.nickname or song.title}]"
                    all_warnings.append(f"{prefix} {inst_name} 세션이 배정되지 않았습니다.")

        # 2. Skill Warnings
        for a in self.data_handler.assignments:
            if not a.member_id: continue
            
            # Check ignore_warnings flag
            if a.ignore_warnings:
                continue

            song = next((s for s in self.data_handler.songs if s.id == a.song_id), None)
            if not song: continue
            
            session = next((s for s in song.sessions if s.id == a.session_id), None)
            if not session: continue
            
            member = next((m for m in self.data_handler.members if m.id == a.member_id), None)
            if not member: continue
            
            warnings = self.validate_assignment(member, song, session)
            prefix = f"[{song.nickname or song.title}]"
            for w in warnings:
                all_warnings.append(f"{prefix} {w}")
                
        # 3. Assignment Count Warnings
        stats = self.get_assignment_stats()
        for m in self.data_handler.members:
            status = stats.get(m.id, "NORMAL")
            if status == "OVER":
                all_warnings.append(f"[{m.name}] 배정된 세션이 너무 많습니다.")
            elif status == "UNDER":
                all_warnings.append(f"[{m.name}] 배정된 세션이 너무 적습니다.")
        
        return all_warnings
