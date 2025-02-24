# models.py

from typing import List, Dict, Optional

class Subject:
    def __init__(self, subject_id: str, subject_name: str, category: Optional[str] = None):
        self.subject_id = subject_id
        self.subject_name = subject_name
        self.category = category

class Teacher:
    def __init__(self,
                 teacher_id: str,
                 teacher_name: str,
                 desired_shift_count: int,
                 min_classes: int,
                 teachable_subjects: List[Subject]):
        self.teacher_id = teacher_id
        self.teacher_name = teacher_name
        self.desired_shift_count = desired_shift_count
        self.min_classes = min_classes
        self.teachable_subjects = teachable_subjects  # List[Subject]
        self.available_timeslots = []  # List[TimeSlot]

class Student:
    def __init__(self,
                 student_id: str,
                 student_name: str,
                 grade: str,
                 gap_preference: str,
                 requirements: Dict[str, int]):
        self.student_id = student_id
        self.student_name = student_name
        self.grade = grade
        self.gap_preference = gap_preference
        self.requirements = requirements
        self.available_timeslots = []  # List[TimeSlot]

class TimeSlot:
    def __init__(self,
                 timeslot_id: str,
                 date: str,
                 period_index: int,
                 campaign_id: str,
                 period_label: Optional[str] = None):
        self.timeslot_id = timeslot_id
        self.date = date
        self.period_index = period_index
        self.campaign_id = campaign_id
        self.period_label = period_label

class Campaign:
    def __init__(self,
                 campaign_id: str,
                 name: str,
                 start_date: str,
                 end_date: str,
                 description: str):
        self.campaign_id = campaign_id
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.description = description

class RegularClass:
    """
    subject を Subject クラスに変更。
    """
    def __init__(self,
                 regular_class_id: str,
                 teacher_id: str,
                 subject: Subject,
                 timeslot_id: str,
                 enrolled_student_ids: List[str]):
        self.regular_class_id = regular_class_id
        self.teacher_id = teacher_id
        self.subject = subject            # Subject オブジェクト
        self.timeslot_id = timeslot_id
        self.enrolled_student_ids = enrolled_student_ids

class Shift:
    def __init__(self,
                 shift_id: str,
                 timeslot: TimeSlot,
                 teacher: Teacher,
                 subject: Subject,
                 assigned_students: List[Student]):
        self.shift_id = shift_id
        self.timeslot = timeslot
        self.teacher = teacher
        self.subject = subject
        self.assigned_students = assigned_students
