from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import QObject, pyqtSignal
from models import Member, Grade
from data_handler import DataHandler

class AddMemberCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, member: Member, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.member = member
        self.update_signal = update_signal
        self.setText(f"Add Member {member.name}")

    def redo(self):
        self.data_handler.members.append(self.member)
        self.update_signal.emit()

    def undo(self):
        if self.member in self.data_handler.members:
            self.data_handler.members.remove(self.member)
            self.update_signal.emit()

class DeleteMemberCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, member: Member, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.member = member
        self.update_signal = update_signal
        self.setText(f"Delete Member {member.name}")

    def redo(self):
        if self.member in self.data_handler.members:
            self.data_handler.members.remove(self.member)
            self.update_signal.emit()

    def undo(self):
        self.data_handler.members.append(self.member)
        self.update_signal.emit()

class UpdateMemberCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, old_member: Member, new_member: Member, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.old_member = old_member
        self.new_member = new_member
        self.update_signal = update_signal
        self.setText(f"Update Member {new_member.name}")

    def redo(self):
        try:
            # We need to find the object in the list that matches the ID or reference
            # If reference logic is strictly followed, direct replacement works if object identity is preserved in list
            # But loading from file creates new objects.
            # Assuming old_member is the exact object in the list.
            if self.old_member in self.data_handler.members:
                idx = self.data_handler.members.index(self.old_member)
                self.data_handler.members[idx] = self.new_member
                self.update_signal.emit()
        except ValueError:
            pass

    def undo(self):
        try:
            if self.new_member in self.data_handler.members:
                idx = self.data_handler.members.index(self.new_member)
                self.data_handler.members[idx] = self.old_member
                self.update_signal.emit()
        except ValueError:
            pass

class YearPassCommand(QUndoCommand):
    def __init__(self, data_handler: DataHandler, update_signal):
        super().__init__()
        self.data_handler = data_handler
        self.update_signal = update_signal
        self.setText("1년 경과")
        
        # State for Undo
        self.deleted_members = []
        self.promoted_members = [] # (member, old_grade) tuples
        self.deleted_assignments = [] # (song_id, session_id, assignment_obj) tuples
        
        # Grade Promotion Map
        self.grade_map = {
            Grade.YE1.value: Grade.YE2.value,
            Grade.YE2.value: Grade.BON1.value,
            Grade.BON1.value: Grade.BON2.value,
            Grade.BON2.value: Grade.BON3.value,
            Grade.BON3.value: Grade.BON4.value
        }

    def redo(self):
        self.deleted_members = []
        self.promoted_members = []
        self.deleted_assignments = []
        
        # 1. Identify members to delete (BON4) and promote others
        # Iterate over copy to modify list safely
        for member in list(self.data_handler.members):
            if member.grade == Grade.BON4.value:
                self.deleted_members.append(member)
                self.data_handler.members.remove(member)
            elif member.grade in self.grade_map:
                old_grade = member.grade
                member.grade = self.grade_map[member.grade]
                self.promoted_members.append((member, old_grade))
                
        # 2. Cascade Delete Assignments for Deleted Members
        deleted_ids = {m.id for m in self.deleted_members}
        
        # Iterate over global assignments list
        for assign in list(self.data_handler.assignments):
            if assign.member_id in deleted_ids:
                # Save for Undo (assign object is removed but still exists in memory)
                self.deleted_assignments.append(assign)
                self.data_handler.assignments.remove(assign)
                        
        self.update_signal.emit()

    def undo(self):
        # 1. Restore Assignments
        for assign in self.deleted_assignments:
            self.data_handler.assignments.append(assign)
        
        # 2. Restore Member Grades
        for member, old_grade in self.promoted_members:
            member.grade = old_grade
            
        # 3. Restore Deleted Members
        for member in self.deleted_members:
            self.data_handler.members.append(member)
            
        self.update_signal.emit()

class ProfileService(QObject):
    data_changed = pyqtSignal()

    def __init__(self, data_handler: DataHandler, undo_stack):
        super().__init__()
        self.data_handler = data_handler
        self.undo_stack = undo_stack

    def add_member(self, member: Member):
        cmd = AddMemberCommand(self.data_handler, member, self.data_changed)
        self.undo_stack.push(cmd)

    def delete_member(self, member: Member):
        cmd = DeleteMemberCommand(self.data_handler, member, self.data_changed)
        self.undo_stack.push(cmd)

    def update_member(self, old_member: Member, new_member: Member):
        cmd = UpdateMemberCommand(self.data_handler, old_member, new_member, self.data_changed)
        self.undo_stack.push(cmd)
        
    def pass_year(self):
        cmd = YearPassCommand(self.data_handler, self.data_changed)
        self.undo_stack.push(cmd)
        
    def get_members_by_grade(self, grade_value: str):
        return sorted([m for m in self.data_handler.members if m.grade == grade_value], key=lambda x: x.name)
