# main.py

import logging
import sys
import csv
import os

from config import (
    LOG_LEVEL, 
    SUBJECTS_CSV,           # NEW
    TEACHERS_CSV,
    STUDENTS_CSV,
    STUDENT_REQUIREMENTS_CSV,
    TIMESLOTS_CSV,
    TEACHER_AVAILABILITY_CSV,
    STUDENT_AVAILABILITY_CSV,
    REGULAR_CLASSES_CSV,
    CONSTRAINT_WEIGHTS_CSV,
    CAMPAIGN_CSV,
    OUTPUT_DIR
)

from reader import (
    load_subjects,         # NEW
    load_teachers, 
    load_students,
    load_student_requirements,
    load_timeslots, 
    load_campaigns,
    load_availability, 
    load_constraint_weights, 
    load_regular_classes
)
from solver_cp_sat import solve_shifts


def setup_logging():
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def export_shifts_by_teacher(shifts, output_path):
    """
    教師ごとにまとめたCSV (1行1シフト)。
    subjectは Subjectクラスなので subject.subject_id と subject.subject_name を出力。
    """
    def sort_key(shift):
        return (shift.teacher.teacher_name, shift.timeslot.date, shift.timeslot.period_index)

    sorted_shifts = sorted(shifts, key=sort_key)

    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "teacher_id",
            "teacher_name",
            "timeslot_id",
            "date",
            "period_index",
            "period_label",
            "subject_id",
            "subject_name",
            "assigned_student_ids",
            "assigned_student_names"
        ])
        for sh in sorted_shifts:
            t_id = sh.teacher.teacher_id
            t_name = sh.teacher.teacher_name
            ts_id = sh.timeslot.timeslot_id
            date_str = sh.timeslot.date
            p_idx = sh.timeslot.period_index
            p_label = sh.timeslot.period_label if sh.timeslot.period_label else ""
            subj_id = sh.subject.subject_id
            subj_name = sh.subject.subject_name

            s_ids = [st.student_id for st in sh.assigned_students]
            s_names = [st.student_name for st in sh.assigned_students]

            writer.writerow([
                t_id,
                t_name,
                ts_id,
                date_str,
                p_idx,
                p_label,
                subj_id,
                subj_name,
                "|".join(s_ids),
                "|".join(s_names)
            ])

    logging.info(f"Teacher-based schedule exported to {output_path}")


def export_shifts_by_student(shifts, output_path):
    """
    生徒ごとにまとめたCSV (1行=シフト×1生徒)。
    subjectは Subjectクラスなので subject.subject_id と subject.subject_name を出力。
    """
    records = []
    for sh in shifts:
        for st in sh.assigned_students:
            records.append({
                "student_id": st.student_id,
                "student_name": st.student_name,
                "timeslot_id": sh.timeslot.timeslot_id,
                "date": sh.timeslot.date,
                "period_index": sh.timeslot.period_index,
                "period_label": sh.timeslot.period_label if sh.timeslot.period_label else "",
                "subject_id": sh.subject.subject_id,
                "subject_name": sh.subject.subject_name,
                "teacher_id": sh.teacher.teacher_id,
                "teacher_name": sh.teacher.teacher_name
            })

    records.sort(key=lambda r: (r["student_name"], r["date"], r["period_index"]))

    dir_path = os.path.dirname(output_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "student_id",
            "student_name",
            "timeslot_id",
            "date",
            "period_index",
            "period_label",
            "subject_id",
            "subject_name",
            "teacher_id",
            "teacher_name"
        ])
        for rec in records:
            writer.writerow([
                rec["student_id"],
                rec["student_name"],
                rec["timeslot_id"],
                rec["date"],
                rec["period_index"],
                rec["period_label"],
                rec["subject_id"],
                rec["subject_name"],
                rec["teacher_id"],
                rec["teacher_name"]
            ])

    logging.info(f"Student-based schedule exported to {output_path}")

def export_shortage_csv(shortage_result, students, subjects, output_path):
    """
    不足コマをCSVに出力 (1行=1つの(生徒,科目)で不足がある場合)
    表形式: student_id, student_name, subject_id, subject_name, shortage_count
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "student_id",
            "student_name",
            "subject_id",
            "subject_name",
            "shortage_count"
        ])
        for (s_id, subj_id), shortage_val in shortage_result.items():
            if shortage_val > 0:
                s_name = students[s_id].student_name
                sbj_name = subjects[subj_id].subject_name if subj_id in subjects else subj_id
                writer.writerow([s_id, s_name, subj_id, sbj_name, shortage_val])

    logging.info(f"Shortage info exported to {output_path}")


def main():
    setup_logging()

    logging.info("Loading data...")

    # 1) Subjects (必須: ソルバーがSubjectクラスを使用)
    subjects = load_subjects(SUBJECTS_CSV)

    # 2) Teachers (subjectを使うので subjectsを渡す)
    teachers = load_teachers(TEACHERS_CSV, subjects)

    # 3) Students
    students = load_students(STUDENTS_CSV)
    
    reqs_dict = load_student_requirements(STUDENT_REQUIREMENTS_CSV)
    # これを students[s_id].requirements に代入
    for s_id, rmap in reqs_dict.items():
        if s_id in students:
            students[s_id].requirements = rmap
        else:
            # CSV上に存在しない student_id ならログ
            logging.warning(f"student_id {s_id} in requirements not found in students list.")

    # 4) Timeslots
    timeslots = load_timeslots(TIMESLOTS_CSV)

    # 5) Campaign
    campaigns = load_campaigns(CAMPAIGN_CSV)

    # 6) Availability (Teacher / Student)
    load_availability(TEACHER_AVAILABILITY_CSV, teachers=teachers, timeslots=timeslots)
    load_availability(STUDENT_AVAILABILITY_CSV, students=students, timeslots=timeslots)

    # 7) Constraint Weights
    constraint_weights = load_constraint_weights(CONSTRAINT_WEIGHTS_CSV)

    # 8) Regular classes (subjectを使う)
    regular_classes = load_regular_classes(REGULAR_CLASSES_CSV, subjects)

    # Solve
    campaign_id = "CAM1"
    if campaign_id not in campaigns:
        logging.error(f"Campaign {campaign_id} not found.")
        sys.exit(1)

    result_shifts, shortage_dict = solve_shifts(
        teachers=teachers,
        students=students,
        timeslots=timeslots,
        campaigns=campaigns,
        regular_classes=regular_classes,
        subjects=subjects,       # ソルバーにSubject辞書を渡す
        campaign_id=campaign_id,
        constraint_weights=constraint_weights
    )

    if not result_shifts and not shortage_dict:
        logging.warning("No shifts assigned or no feasible solution.")
        return

    # 出力ファイル
    teacher_csv_path = os.path.join(OUTPUT_DIR, "teacher_schedules.csv")
    student_csv_path = os.path.join(OUTPUT_DIR, "student_schedules.csv")
    shortage_csv_path = os.path.join(OUTPUT_DIR, "shortage.csv")

    # 教師ごとCSV
    export_shifts_by_teacher(result_shifts, teacher_csv_path)

    # 生徒ごとCSV
    export_shifts_by_student(result_shifts, student_csv_path)

    # 3) 不足コマCSV (表形式)
    export_shortage_csv(shortage_dict, students, subjects, shortage_csv_path)

if __name__ == "__main__":
    main()
