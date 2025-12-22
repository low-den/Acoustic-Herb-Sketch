from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QPushButton, QGroupBox, QLabel, QSizePolicy)
from models import Grade

class GradeGroupWidget(QGroupBox):
    def __init__(self, grade_label: str):
        super().__init__(grade_label)
        self.grade_label = grade_label
        
        # Bold Title
        self.setStyleSheet("QGroupBox { font-weight: bold; }")
        
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("추가")
        self.btn_edit = QPushButton("편집")
        self.btn_del = QPushButton("삭제")
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

class ProfileWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Top Row (4 Grades): Bon2, Bon1, Ye2, Ye1
        top_layout = QHBoxLayout()
        self.group_bon2 = GradeGroupWidget(Grade.BON2.value)
        self.group_bon1 = GradeGroupWidget(Grade.BON1.value)
        self.group_ye2 = GradeGroupWidget(Grade.YE2.value)
        self.group_ye1 = GradeGroupWidget(Grade.YE1.value)
        
        top_layout.addWidget(self.group_bon2)
        top_layout.addWidget(self.group_bon1)
        top_layout.addWidget(self.group_ye2)
        top_layout.addWidget(self.group_ye1)
        
        main_layout.addLayout(top_layout, stretch=1)
        
        # Bottom Row
        bottom_layout = QHBoxLayout()
        
        # Left side of bottom (2 Grades): Bon4, Bon3
        bottom_left = QHBoxLayout()
        self.group_bon4 = GradeGroupWidget(Grade.BON4.value)
        self.group_bon3 = GradeGroupWidget(Grade.BON3.value)
        bottom_left.addWidget(self.group_bon4)
        bottom_left.addWidget(self.group_bon3)
        
        bottom_layout.addLayout(bottom_left, stretch=1)
        
        # Right side of bottom (Description + Global Buttons)
        right_panel_layout = QHBoxLayout()
        
        desc_group = QGroupBox("실력 기준")
        desc_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        desc_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        desc_layout = QVBoxLayout()
        desc_text = """<b>[유튜버] 16비트 bpm 180 ↑<br>
[고수] 16비트 bpm 160-180<br>
[상] 16비트 bpm 140-160<br>
[중] 16비트 bpm 120-140<br>
[하] 16비트 bpm 90-120<br>
[초보] 16비트 bpm 90 ↓</b><br>
<br>
* 수치화를 위해 실력은 박자에 맞게 연주가 가능한지로만 결정합니다.<br>
* 기타/피아노 계열은 솔로 기준으로 결정해주세요.<br>
* 관악기는 고음 가능 여부, 현악기는 음정 정확도까지 체크한 후 결정해주세요.<br>
<br>
* 보컬은 예외적으로 최고음 가능 여부로 결정합니다.<br>
* 중-상-고수 등급은 실력이 가장 많이 구분되는 구간이므로 더욱 세분화했습니다.<br>
<br>
* '공연 곡 편집' 탭에서 한 사람이 여러 악기를 사용하는 경우에는 가장 잘하는 악기로 설정해주세요.<br>
* 이 경우 테크라이더에는 추가로 사용하는 악기를 수기로 작성해주세요."""
        desc_layout.addWidget(QLabel(desc_text))
        desc_layout.addStretch() 
        desc_group.setLayout(desc_layout)
        right_panel_layout.addWidget(desc_group)
          
        # Buttons Layout (Vertical, Right side)
        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_edit_instruments = QPushButton("악기 편집")
        self.btn_edit_instruments.setFixedWidth(80)
        self.btn_edit_instruments.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        
        self.btn_year_pass = QPushButton("1년 경과")
        self.btn_year_pass.setFixedWidth(80)
        self.btn_year_pass.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.btn_year_pass.setStyleSheet("background-color: #ffaaaa; color: white; font-weight: bold;")
        
        btn_layout.addWidget(self.btn_edit_instruments)
        btn_layout.addWidget(self.btn_year_pass)
        
        right_panel_layout.addLayout(btn_layout)
        
        bottom_layout.addLayout(right_panel_layout, stretch=1)
        
        main_layout.addLayout(bottom_layout, stretch=1)

