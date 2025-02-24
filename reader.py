# reader.py

import csv
import logging
from typing import Dict
from models import Teacher, Student, TimeSlot, Campaign, RegularClass, Subject

logger = logging.getLogger(__name__)

def load_subjects(csv_path: str) -> Dict[str, Subject]:
    subjects = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row["subject_id"]
                sname = row["subject_name"]
                cat = row.get("category", "")
                subj_obj = Subject(subject_id=sid, subject_name=sname, category=cat)
                subjects[sid] = subj_obj
        logger.info(f"Loaded {len(subjects)} subjects from {csv_path}")
    except Exception as e:
        logger.error(f"Error reading subjects from {csv_path}: {e}")
    return subjects

def load_teachers(csv_path: str, subjects_dict: Dict[str, Subject]) -> Dict[str, Teacher]:
    teachers = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t_id = row["teacher_id"]
                t_name = row["teacher_name"]
                desired = int(row["desired_shift_count"])
                minimum = int(row["min_classes"])

                subs_str = row["teachable_subjects"]
                subject_list = []
                if subs_str:
                    for sid in subs_str.split("|"):
                        if sid in subjects_dict:
                            subject_list.append(subjects_dict[sid])
                        else:
                            logger.warning(f"Subject {sid} not in dict.")
                teacher = Teacher(
                    teacher_id=t_id,
                    teacher_name=t_name,
                    desired_shift_count=desired,
                    min_classes=minimum,
                    teachable_subjects=subject_list
                )
                teachers[t_id] = teacher
        logger.info(f"Loaded {len(teachers)} teachers from {csv_path}")
    except Exception as e:
        logger.error(f"Error reading teachers from {csv_path}: {e}")
    return teachers

def load_students(csv_path: str) -> Dict[str, Student]:
    students = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s_id = row["student_id"]
                s_name = row["student_name"]
                grade = row["grade"]
                gap_pref = row["gap_preference"]

                requirements = {}
                for k, v in row.items():
                    if k.startswith("required_"):
                        subj_id = k.replace("required_", "")
                        requirements[subj_id] = int(v) if v.isdigit() else 0

                stu = Student(
                    student_id=s_id,
                    student_name=s_name,
                    grade=grade,
                    gap_preference=gap_pref,
                    requirements=requirements
                )
                students[s_id] = stu
        logger.info(f"Loaded {len(students)} students from {csv_path}")
    except Exception as e:
        logger.error(f"Error reading students from {csv_path}: {e}")
    return students

def load_student_requirements(csv_path: str) -> Dict[str, Dict[str, int]]:
    """
    student_requirements.csv:
      student_id, student_name, subject_id, required_count
    の形を想定。
    戻り値: { s_id: { subj_id: required_count, ... }, ... }
    """
    requirements = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s_id = row["student_id"]
                # student_name は人間向け表示/ログ用（必須でない）
                s_name = row.get("student_name", "")
                subj_id = row["subject_id"]
                req_count = int(row["required_count"])

                logger.debug(f"Reading requirement: {s_id}({s_name}) -> {subj_id}:{req_count}")

                if s_id not in requirements:
                    requirements[s_id] = {}
                requirements[s_id][subj_id] = req_count

        logger.info(f"Loaded student requirements from {csv_path}")
    except Exception as e:
        logger.error(f"Error reading student_requirements from {csv_path}: {e}")

    return requirements

def load_timeslots(csv_path: str) -> Dict[str, TimeSlot]:
    timeslots = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_id = row["timeslot_id"]
                date_str = row["date"]
                pidx = int(row["period_index"])
                camp_id = row["campaign_id"]
                plabel = row.get("period_label", None)
                ts = TimeSlot(
                    timeslot_id=ts_id,
                    date=date_str,
                    period_index=pidx,
                    campaign_id=camp_id,
                    period_label=plabel
                )
                timeslots[ts_id] = ts
        logger.info(f"Loaded {len(timeslots)} timeslots from {csv_path}")
    except Exception as e:
        logger.error(f"Error reading timeslots from {csv_path}: {e}")
    return timeslots

def load_campaigns(csv_path: str) -> Dict[str, Campaign]:
    campaigns = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row["campaign_id"]
                c = Campaign(
                    campaign_id=cid,
                    name=row["name"],
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    description=row["description"]
                )
                campaigns[cid] = c
        logger.info(f"Loaded {len(campaigns)} campaigns from {csv_path}")
    except Exception as e:
        logger.error(f"Error reading campaigns from {csv_path}: {e}")
    return campaigns

def load_availability(csv_path: str,
                      teachers: Dict[str, Teacher] = None,
                      students: Dict[str, Student] = None,
                      timeslots: Dict[str, TimeSlot] = None):
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_id = row["timeslot_id"]
                if ts_id not in timeslots:
                    continue

                if "teacher_id" in row and row["teacher_id"]:
                    t_id = row["teacher_id"]
                    if t_id in teachers:
                        teachers[t_id].available_timeslots.append(timeslots[ts_id])
                elif "student_id" in row and row["student_id"]:
                    s_id = row["student_id"]
                    if s_id in students:
                        students[s_id].available_timeslots.append(timeslots[ts_id])
    except Exception as e:
        logger.error(f"Error reading availability from {csv_path}: {e}")

def load_constraint_weights(csv_path: str) -> Dict[str, float]:
    weights = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                k = row["key"]
                v = float(row["value"])
                weights[k] = v
        logger.info(f"Loaded constraint weights: {weights}")
    except Exception as e:
        logger.error(f"Error reading constraint_weights from {csv_path}: {e}")
    return weights

def load_regular_classes(csv_path: str,
                         subjects_dict: Dict[str, Subject]) -> Dict[str, RegularClass]:
    """
    regular_classes.csv:
      regular_class_id,teacher_id,subject_id,timeslot_id,enrolled_student_ids
    subject_id -> Subject
    """
    regs = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rc_id = row["regular_class_id"]
                t_id = row["teacher_id"]
                subj_id = row["subject_id"]
                ts_id = row["timeslot_id"]
                en_str = row["enrolled_student_ids"]
                if en_str:
                    eids = en_str.split("|")
                else:
                    eids = []

                if subj_id in subjects_dict:
                    subj_obj = subjects_dict[subj_id]
                else:
                    logger.warning(f"Subject {subj_id} not found in subject dict.")
                    continue

                rc = RegularClass(
                    regular_class_id=rc_id,
                    teacher_id=t_id,
                    subject=subj_obj,  # Subject オブジェクト
                    timeslot_id=ts_id,
                    enrolled_student_ids=eids
                )
                regs[rc_id] = rc
        logger.info(f"Loaded {len(regs)} regular classes from {csv_path}")
    except Exception as e:
        logger.error(f"Error reading regular_classes from {csv_path}: {e}")
    return regs
