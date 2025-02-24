# solver_cp_sat.py

import logging
from typing import Dict, List
from collections import defaultdict
from ortools.sat.python import cp_model
from models import Teacher, Student, TimeSlot, Campaign, RegularClass, Shift, Subject

logger = logging.getLogger(__name__)

def solve_shifts(teachers: Dict[str, Teacher],
                 students: Dict[str, Student],
                 timeslots: Dict[str, TimeSlot],
                 campaigns: Dict[str, Campaign],
                 regular_classes: Dict[str, RegularClass],
                 subjects: Dict[str, Subject],
                 campaign_id: str,
                 constraint_weights: Dict[str, float]) -> List[Shift]:
    model = cp_model.CpModel()

    target_timeslots = [ts for ts in timeslots.values() if ts.campaign_id == campaign_id]
    if not target_timeslots:
        logger.warning(f"No timeslots for campaign_id={campaign_id}")
        return []

    # teacher_subject_pairs
    teacher_subject_pairs = []
    for t_id, t_obj in teachers.items():
        for subj_obj in t_obj.teachable_subjects:
            teacher_subject_pairs.append((t_id, subj_obj.subject_id))

    # student_subject_pairs
    student_subject_pairs = []
    for s_id, s_obj in students.items():
        for subj_id, req_num in s_obj.requirements.items():
            if req_num > 0:
                student_subject_pairs.append((s_id, subj_id))

    # regular class conflict
    teacher_time_conflict = defaultdict(bool)
    regular_class_continuity_info = set()

    for rc_id, rc_obj in regular_classes.items():
        subj_id = rc_obj.subject.subject_id
        teacher_time_conflict[(rc_obj.teacher_id, rc_obj.timeslot_id)] = True
        for st_id in rc_obj.enrolled_student_ids:
            regular_class_continuity_info.add((st_id, rc_obj.teacher_id, subj_id))

    x = {}
    for ts in target_timeslots:
        ts_id = ts.timeslot_id
        for (t_id, subj_id) in teacher_subject_pairs:
            if teacher_time_conflict[(t_id, ts_id)]:
                continue
            if ts not in teachers[t_id].available_timeslots:
                continue
            for (s_id, s_subj) in student_subject_pairs:
                if s_subj == subj_id:
                    if ts in students[s_id].available_timeslots:
                        var_name = f"x_{t_id}_{s_id}_{subj_id}_{ts_id}"
                        x[(t_id, s_id, subj_id, ts_id)] = model.NewBoolVar(var_name)

    # ハード制約
    # (1) 生徒の必要コマ数
    for s_id, s_obj in students.items():
        for subj_id, req_num in s_obj.requirements.items():
            if req_num > 0:
                # x[t, s_id, subj_id, timeslot] の合計 == req_num
                relevant_vars = []
                for (tt, ss, sbj, tslot) in x.keys():
                    if ss == s_id and sbj == subj_id:
                        relevant_vars.append(x[(tt, ss, sbj, tslot)])
                model.Add(sum(relevant_vars) == req_num)

    # (2) 同一Timeslotで生徒重複NG
    for ts in target_timeslots:
        ts_id = ts.timeslot_id
        for s_id in students.keys():
            relevant_vars = []
            for (t_, s_, sbj_, tslot) in x.keys():
                if s_ == s_id and tslot == ts_id:
                    relevant_vars.append(x[(t_, s_, sbj_, tslot)])
            model.Add(sum(relevant_vars) <= 1)

    # (3) 同一Timeslotで教師は最大2名
    for ts in target_timeslots:
        ts_id = ts.timeslot_id
        for t_id in teachers.keys():
            relevant_vars = []
            for (tt, ss, sbj, tslot) in x.keys():
                if tt == t_id and tslot == ts_id:
                    relevant_vars.append(x[(tt, ss, sbj, tslot)])
            model.Add(sum(relevant_vars) <= 2)

    # (4) 教師の最低コマ数(日ごと)
    timeslots_by_date = defaultdict(list)
    for ts in target_timeslots:
        timeslots_by_date[ts.date].append(ts)

    for t_id, t_obj in teachers.items():
        for date, ts_list in timeslots_by_date.items():
            relevant_vars = []
            for ts_obj in ts_list:
                ts_id = ts_obj.timeslot_id
                for (tt, ss, sbj, tslot) in x.keys():
                    if tt == t_id and tslot == ts_id:
                        relevant_vars.append(x[(tt, ss, sbj, tslot)])
            if relevant_vars:
                model.Add(sum(relevant_vars) >= t_obj.min_classes)

    # ソフト制約
    obj_terms = []
    maxTwoStudentsBonus = constraint_weights.get("maxTwoStudentsBonus", 0)
    sameGradeBonus = constraint_weights.get("sameGradeBonus", 0)
    regularClassContinuityBonus = constraint_weights.get("regularClassContinuityBonus", 0)
    teacherGapPenalty = constraint_weights.get("teacherGapPenalty", 0)
    studentGapPenalty = constraint_weights.get("studentGapPenalty", 0)
    singleStudentPenalty = constraint_weights.get("singleStudentPenalty", 0)

    # (a) 2対1 vs 1対1
    teacher_ts_count = {}
    for ts in target_timeslots:
        ts_id = ts.timeslot_id
        for t_id in teachers.keys():
            cvar = model.NewIntVar(0, 2, f"count_{t_id}_{ts_id}")
            teacher_ts_count[(t_id, ts_id)] = cvar

    for (t_id, ts_id), cvar in teacher_ts_count.items():
        relevant_vars = []
        for (tt, ss, sbj, tslot) in x.keys():
            if tt == t_id and tslot == ts_id:
                relevant_vars.append(x[(tt, ss, sbj, tslot)])
        model.Add(cvar == sum(relevant_vars))

        # 2名ボーナス
        b_two = model.NewBoolVar(f"is_two_{t_id}_{ts_id}")
        model.Add(cvar == 2).OnlyEnforceIf(b_two)
        model.Add(cvar != 2).OnlyEnforceIf(b_two.Not())
        if maxTwoStudentsBonus > 0:
            obj_terms.append(b_two * maxTwoStudentsBonus)

        # 1名ペナルティ
        b_one = model.NewBoolVar(f"is_one_{t_id}_{ts_id}")
        model.Add(cvar == 1).OnlyEnforceIf(b_one)
        model.Add(cvar != 1).OnlyEnforceIf(b_one.Not())
        if singleStudentPenalty > 0:
            obj_terms.append(b_one * (-singleStudentPenalty))

    # (b) 同じ学年2名ボーナス
    for ts in target_timeslots:
        ts_id = ts.timeslot_id
        for t_id in teachers.keys():
            s_ids = list(students.keys())
            for i in range(len(s_ids)):
                for j in range(i+1, len(s_ids)):
                    s1 = s_ids[i]
                    s2 = s_ids[j]
                    if students[s1].grade != students[s2].grade:
                        continue
                    pair_var = model.NewBoolVar(f"sameGrade_{t_id}_{s1}_{s2}_{ts_id}")
                    x_s1 = []
                    x_s2 = []
                    for (tt, ss, sbj, tslot) in x.keys():
                        if tt == t_id and tslot == ts_id:
                            if ss == s1:
                                x_s1.append(x[(tt, ss, sbj, tslot)])
                            if ss == s2:
                                x_s2.append(x[(tt, ss, sbj, tslot)])
                    sum_pair = model.NewIntVar(0, 2, f"sumPair_{t_id}_{s1}_{s2}_{ts_id}")
                    model.Add(sum_pair == sum(x_s1) + sum(x_s2))
                    model.Add(sum_pair == 2).OnlyEnforceIf(pair_var)
                    model.Add(sum_pair != 2).OnlyEnforceIf(pair_var.Not())
                    if sameGradeBonus > 0:
                        obj_terms.append(pair_var * sameGradeBonus)

    # (c) レギュラー授業との一貫性
    for (t_id, s_id, subj_id, ts_id), var in x.items():
        if (s_id, t_id, subj_id) in regular_class_continuity_info:
            obj_terms.append(var * regularClassContinuityBonus)

    # (d) ギャップペナルティ
    # ---------- teacher gap -----------
    # teacher_timeslots_by_date
    teacher_timeslots_by_date = defaultdict(list)
    for ts in target_timeslots:
        for t_id, t_obj in teachers.items():
            if ts in t_obj.available_timeslots:
                teacher_timeslots_by_date[(t_id, ts.date)].append(ts)

    # teacher_assigned
    teacher_assigned = {}
    for (t_id, date), ts_list in teacher_timeslots_by_date.items():
        for ts_obj in ts_list:
            ts_id = ts_obj.timeslot_id
            key = (t_id, ts_id)
            if key not in teacher_assigned:
                teacher_assigned[key] = model.NewBoolVar(f"teacher_assigned_{t_id}_{ts_id}")

    # assigned=1 if any x[t, s, subj, ts]==1
    for (t_id, ts_id), assigned_var in teacher_assigned.items():
        relevant_x = []
        for (tt, ss, sbj, tslot) in x.keys():
            if tt == t_id and tslot == ts_id:
                relevant_x.append(x[(tt, ss, sbj, tslot)])
        if relevant_x:
            model.Add(sum(relevant_x) >= 1).OnlyEnforceIf(assigned_var)
            model.Add(sum(relevant_x) == 0).OnlyEnforceIf(assigned_var.Not())
        else:
            model.Add(assigned_var == 0)

    if teacherGapPenalty > 0:
        for (t_id, date), ts_list in teacher_timeslots_by_date.items():
            ts_list.sort(key=lambda ts: ts.period_index)
            for i in range(len(ts_list) - 1):
                tsA = ts_list[i]
                tsB = ts_list[i+1]
                a_var = teacher_assigned[(t_id, tsA.timeslot_id)]
                b_var = teacher_assigned[(t_id, tsB.timeslot_id)]
                gap_var = model.NewBoolVar(f"t_gap_{t_id}_{tsA.timeslot_id}_{tsB.timeslot_id}")
                model.Add(a_var != b_var).OnlyEnforceIf(gap_var)
                model.Add(a_var == b_var).OnlyEnforceIf(gap_var.Not())
                obj_terms.append(gap_var * (-teacherGapPenalty))

    # ---------- student gap -----------
    student_timeslots_by_date = defaultdict(list)
    for ts in target_timeslots:
        for s_id, s_obj in students.items():
            if ts in s_obj.available_timeslots:
                student_timeslots_by_date[(s_id, ts.date)].append(ts)

    # student_assigned
    student_assigned = {}
    for (s_id, date), ts_list in student_timeslots_by_date.items():
        for ts_obj in ts_list:
            ts_id = ts_obj.timeslot_id
            key = (s_id, ts_id)
            if key not in student_assigned:
                student_assigned[key] = model.NewBoolVar(f"stud_assigned_{s_id}_{ts_id}")

    # assigned=1 if sum_x >=1
    for (s_id, ts_id), assigned_var in student_assigned.items():
        relevant_x = []
        for (tt, ss, sbj, tslot) in x.keys():
            if ss == s_id and tslot == ts_id:
                relevant_x.append(x[(tt, ss, sbj, tslot)])
        if relevant_x:
            model.Add(sum(relevant_x) >= 1).OnlyEnforceIf(assigned_var)
            model.Add(sum(relevant_x) == 0).OnlyEnforceIf(assigned_var.Not())
        else:
            model.Add(assigned_var == 0)

    if studentGapPenalty > 0:
        for (s_id, date), ts_list in student_timeslots_by_date.items():
            ts_list.sort(key=lambda ts: ts.period_index)
            penalty_factor = 2 if students[s_id].gap_preference == "NoGapPreferred" else 1
            for i in range(len(ts_list) - 1):
                tsA = ts_list[i]
                tsB = ts_list[i+1]
                a_var = student_assigned[(s_id, tsA.timeslot_id)]
                b_var = student_assigned[(s_id, tsB.timeslot_id)]
                gap_var = model.NewBoolVar(f"s_gap_{s_id}_{tsA.timeslot_id}_{tsB.timeslot_id}")
                model.Add(a_var != b_var).OnlyEnforceIf(gap_var)
                model.Add(a_var == b_var).OnlyEnforceIf(gap_var.Not())
                obj_terms.append(gap_var * (-studentGapPenalty * penalty_factor))

    # objective
    model.Maximize(sum(obj_terms))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logger.info(f"Solution found. Objective = {solver.ObjectiveValue()}")
        return build_shift_objects(solver, x, teachers, students, timeslots, subjects)
    else:
        logger.warning("No feasible solution found.")
        return []

def build_shift_objects(solver: cp_model.CpSolver,
                        x_vars,
                        teachers: Dict[str, Teacher],
                        students: Dict[str, Student],
                        timeslots: Dict[str, TimeSlot],
                        subjects: Dict[str, Subject]) -> List[Shift]:
    from collections import defaultdict
    assignment_dict = defaultdict(list)
    for (t_id, s_id, subj_id, ts_id), var in x_vars.items():
        if solver.Value(var) == 1:
            assignment_dict[(t_id, subj_id, ts_id)].append(s_id)

    shifts = []
    shift_counter = 1
    for (t_id, subj_id, ts_id), s_list in assignment_dict.items():
        shift_id = f"Shift_{shift_counter}"
        shift_counter += 1

        teacher_obj = teachers[t_id]
        ts_obj = timeslots[ts_id]
        subject_obj = subjects[subj_id]
        assigned_students = [students[sid] for sid in s_list]

        new_shift = Shift(
            shift_id=shift_id,
            timeslot=ts_obj,
            teacher=teacher_obj,
            subject=subject_obj,
            assigned_students=assigned_students
        )
        shifts.append(new_shift)
    return shifts
