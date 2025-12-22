from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt, QObject, QEvent
from profile_ui import ProfileWidget
from profile_service import ProfileService
from dialogs import ProfileAddEditDialog, InstrumentEditDialog
from models import Grade

class ProfileController(QObject):
    def __init__(self, ui: ProfileWidget, service: ProfileService):
        super().__init__()
        self.ui = ui
        self.service = service
        
        self.grade_widgets = {
            Grade.BON4.value: self.ui.group_bon4,
            Grade.BON3.value: self.ui.group_bon3,
            Grade.BON2.value: self.ui.group_bon2,
            Grade.BON1.value: self.ui.group_bon1,
            Grade.YE2.value: self.ui.group_ye2,
            Grade.YE1.value: self.ui.group_ye1,
        }
        
        self.connect_signals()
        self.refresh_ui()

    def connect_signals(self):
        self.service.data_changed.connect(self.refresh_ui)
        self.ui.btn_edit_instruments.clicked.connect(self.open_instrument_edit_dialog)
        self.ui.btn_year_pass.clicked.connect(self.pass_year)
        
        for grade_val, widget in self.grade_widgets.items():
            widget.btn_add.clicked.connect(lambda _, g=grade_val: self.open_add_dialog(g))
            widget.btn_edit.clicked.connect(lambda _, w=widget: self.open_edit_dialog(w))
            widget.btn_del.clicked.connect(lambda _, w=widget: self.delete_member(w))
            
            # Shortcuts
            widget.list_widget.itemDoubleClicked.connect(lambda item, w=widget: self.open_edit_dialog(w))
            widget.list_widget.installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                for widget in self.grade_widgets.values():
                    if source == widget.list_widget:
                        if widget.list_widget.currentItem():
                            self.open_edit_dialog(widget)
                            return True
            elif event.key() == Qt.Key.Key_Delete:
                for widget in self.grade_widgets.values():
                    if source == widget.list_widget:
                        if widget.list_widget.currentItem():
                            self.delete_member(widget)
                            return True
        return super().eventFilter(source, event)

    def refresh_ui(self):
        for widget in self.grade_widgets.values():
            widget.list_widget.clear()
            
        for member in self.service.data_handler.members:
            widget = self.grade_widgets.get(member.grade)
            if widget:
                inst_summary = ", ".join([self.get_inst_name(i.instrument_id) for i in member.instruments])
                text = f"{member.name} ({inst_summary})" if inst_summary else member.name
                widget.list_widget.addItem(text)
                item_obj = widget.list_widget.item(widget.list_widget.count()-1)
                item_obj.setData(Qt.ItemDataRole.UserRole, member.id)

    def get_inst_name(self, inst_id):
        for i in self.service.data_handler.instruments:
            if i.id == inst_id:
                return i.name
        return "?"

    def open_add_dialog(self, default_grade=None):
        dlg = ProfileAddEditDialog(self.ui, instruments_pool=self.service.data_handler.instruments)
        if default_grade:
             dlg.grade_combo.setCurrentText(default_grade)
             
        if dlg.exec():
            new_member = dlg.get_data()
            self.service.add_member(new_member)

    def open_edit_dialog(self, widget):
        item = widget.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self.ui, "경고", "편집할 부원을 선택해주세요.")
            return
            
        member_id = item.data(Qt.ItemDataRole.UserRole)
        member = next((m for m in self.service.data_handler.members if m.id == member_id), None)
        if not member:
            return

        dlg = ProfileAddEditDialog(self.ui, member=member, instruments_pool=self.service.data_handler.instruments)
        if dlg.exec():
            updated_member = dlg.get_data()
            self.service.update_member(member, updated_member)

    def delete_member(self, widget):
        item = widget.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self.ui, "경고", "삭제할 부원을 선택해주세요.")
            return

        member_id = item.data(Qt.ItemDataRole.UserRole)
        member = next((m for m in self.service.data_handler.members if m.id == member_id), None)
        
        reply = QMessageBox.question(self.ui, '삭제', '정말 해당 세션을 삭제하시겠습니까?', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.service.delete_member(member)

    def open_instrument_edit_dialog(self):
        dlg = InstrumentEditDialog(self.service.data_handler, self.ui)
        dlg.instruments_changed.connect(self.refresh_ui) # Refresh names if renamed
        dlg.exec()
        
    def pass_year(self):
        reply = QMessageBox.question(self.ui, '경고', 
            '본4 세션이 모두 삭제됩니다. 정말 삭제하시겠습니까?\n(삭제 후 백업되지 않으며, 모든 학년이 진급합니다.)',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
             self.service.pass_year()

