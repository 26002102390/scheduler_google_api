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
                 constraint_weights: Dict[str, float]):
    """
    ソルバー本体。可読性を意識し、セクションごとにコメントを付与。
      1) 変数定義
      2) ハード制約 (Constraints)
      3) ソフト制約 (Objective function)
      4) Solve & Build result
    """

    model = cp_model.CpModel()

    # --------------------------------------
    # 0) ターゲット timeslot 抽出
    # --------------------------------------
    target_timeslots = [ts for ts in timeslots.values() if ts.campaign_id == campaign_id]
    if not target_timeslots:
        logger.warning(f"No timeslots for campaign_id={campaign_id}")
        return [], {}

    # --------------------------------------
    # 1) 変数定義
    # --------------------------------------
    # 1-1) x[t_id, s_id, subj_id, ts_id] = 授業割当 (Binary)
    teacher_time_conflict = defaultdict(bool)
    regular_class_continuity_info = set()
    for rc_id, rc_obj in regular_classes.items():
        sbj_id = rc_obj.subject.subject_id
        teacher_time_conflict[(rc_obj.teacher_id, rc_obj.timeslot_id)] = True
        for st_id in rc_obj.enrolled_student_ids:
            regular_class_continuity_info.add((st_id, rc_obj.teacher_id, sbj_id))

    # teacher_subject_pairs
    teacher_subject_pairs = []
    for t_id, t_obj in teachers.items():
        for sbj_obj in t_obj.teachable_subjects:
            teacher_subject_pairs.append((t_id, sbj_obj.subject_id))

    # student_subject_pairs
    student_subject_pairs = []
    for s_id, s_obj in students.items():
        for sbj_id, req_num in s_obj.requirements.items():
            if req_num > 0:
                student_subject_pairs.append((s_id, sbj_id))

    x = {}
    for ts in target_timeslots:
        ts_id = ts.timeslot_id
        for (t_id, subj_id) in teacher_subject_pairs:
            # レギュラー授業と衝突？
            if teacher_time_conflict[(t_id, ts_id)]:
                continue
            if ts not in teachers[t_id].available_timeslots:
                continue
            for (s_id, stud_subj) in student_subject_pairs:
                if stud_subj == subj_id:
                    if ts in students[s_id].available_timeslots:
                        var_name = f"x_{t_id}_{s_id}_{subj_id}_{ts_id}"
                        x[(t_id, s_id, subj_id, ts_id)] = model.NewBoolVar(var_name)

    # 1-2) 教師出勤フラグ present[t_id]
    teacher_present = {}
    for t_id in teachers.keys():
        teacher_present[t_id] = model.NewBoolVar(f"present_{t_id}")

    # 1-3) 教師が持つコマ数 sum_x[t_id]
    bigM = 2 * len(target_timeslots) + 1
    sum_x_t = {}
    for t_id in teachers.keys():
        sum_x_t[t_id] = model.NewIntVar(0, bigM, f"sumTeacher_{t_id}")

    # 1-4) 生徒の不足コマ shortage[s_id, subj_id]
    # sum_x + shortage = req_num, shortage >= 0
    shortage = {}
    shortagePenalty = 1000  # 大きめ
    for s_id, s_obj in students.items():
        for sbj_id, req_num in s_obj.requirements.items():
            if req_num > 0:
                short_var = model.NewIntVar(0, req_num, f"short_{s_id}_{sbj_id}")
                shortage[(s_id, sbj_id)] = short_var

    # --------------------------------------
    # 2) ハード制約 (Constraints)
    # --------------------------------------

    # 2-1) 教師出勤フラグとの連動
    # sum_x_t[t_id] = sum of x[t_id, *]
    for t_id in teachers.keys():
        relevant_vars = []
        for (tt, ss, sbj, ts_id) in x.keys():
            if tt == t_id:
                relevant_vars.append(x[(tt, ss, sbj, ts_id)])
        model.Add(sum_x_t[t_id] == sum(relevant_vars))
        # 出勤 => sum_x_t[t_id] >=1
        model.Add(sum_x_t[t_id] >= 1).OnlyEnforceIf(teacher_present[t_id])
        model.Add(sum_x_t[t_id] == 0).OnlyEnforceIf(teacher_present[t_id].Not())
        # 出勤なら最低コマ数
        model.Add(sum_x_t[t_id] >= teachers[t_id].min_classes).OnlyEnforceIf(teacher_present[t_id])

    # 2-2) 同一Timeslotで生徒重複NG
    for ts in target_timeslots:
        ts_id = ts.timeslot_id
        for s_id in students.keys():
            relevant_vars = []
            for (t_, s_, sbj_, tslot) in x.keys():
                if s_ == s_id and tslot == ts_id:
                    relevant_vars.append(x[(t_, s_, sbj_, tslot)])
            model.Add(sum(relevant_vars) <= 1)

    # 2-3) 同一Timeslotで教師は最大2名
    for ts in target_timeslots:
        ts_id = ts.timeslot_id
        for t_id in teachers.keys():
            relevant_vars = []
            for (tt, ss, sbj, tslot) in x.keys():
                if tt == t_id and tslot == ts_id:
                    relevant_vars.append(x[(tt, ss, sbj, tslot)])
            model.Add(sum(relevant_vars) <= 2)

    # 2-4) 生徒の不足コマ => sum_x + shortage = req_num
    for s_id, s_obj in students.items():
        for sbj_id, req_num in s_obj.requirements.items():
            if req_num > 0:
                relevant_vars = []
                for (tt, ss, sbj, ts_id) in x.keys():
                    if ss == s_id and sbj == sbj_id:
                        relevant_vars.append(x[(tt, ss, sbj, ts_id)])
                short_var = shortage[(s_id, sbj_id)]
                model.Add(sum(relevant_vars) + short_var == req_num)

    # --------------------------------------
    # 3) ソフト制約 (Objective function)
    # --------------------------------------
    obj_terms = []

    maxTwoStudentsBonus = constraint_weights.get("maxTwoStudentsBonus", 0)
    sameGradeSameSubjectBonus = constraint_weights.get("sameGradeBonus", 0)
    regularClassContinuityBonus = constraint_weights.get("regularClassContinuityBonus", 0)
    teacherGapPenalty = constraint_weights.get("teacherGapPenalty", 0)
    studentGapPenalty = constraint_weights.get("studentGapPenalty", 0)
    singleStudentPenalty = constraint_weights.get("singleStudentPenalty", 0)
    shortagePenalty = constraint_weights.get("shortagePenalty", 0)
    
    # 3-1) 生徒不足コマペナルティ
    for (s_id, sbj_id), short_var in shortage.items():
        # shortageが1増えるたびにマイナス
        obj_terms.append(short_var * (-shortagePenalty))

    # 3-2) 同一Teacher-Timeslotで 2対1 vs 1対1
    # cvar[t_id,ts_id] => # of assigned students(0..2)
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

        # 2名 → ボーナス
        if maxTwoStudentsBonus > 0:
            b_two = model.NewBoolVar(f"is_two_{t_id}_{ts_id}")
            model.Add(cvar == 2).OnlyEnforceIf(b_two)
            model.Add(cvar != 2).OnlyEnforceIf(b_two.Not())
            obj_terms.append(b_two * maxTwoStudentsBonus)

        # 1名 → ペナルティ
        if singleStudentPenalty > 0:
            b_one = model.NewBoolVar(f"is_one_{t_id}_{ts_id}")
            model.Add(cvar == 1).OnlyEnforceIf(b_one)
            model.Add(cvar != 1).OnlyEnforceIf(b_one.Not())
            obj_terms.append(b_one * (-singleStudentPenalty))

    # 3-3) 同学年 + 同一科目 2名 同時
    if sameGradeSameSubjectBonus > 0:
        for ts in target_timeslots:
            ts_id = ts.timeslot_id
            for t_id in teachers.keys():
                # subjectごとに調べる
                # ある timeslot, teacher, subject で2人の学生が割り当てられているかどうか
                # nested loops over students
                s_ids = list(students.keys())
                for i in range(len(s_ids)):
                    for j in range(i+1, len(s_ids)):
                        s1 = s_ids[i]
                        s2 = s_ids[j]
                        # 同学年？
                        if students[s1].grade != students[s2].grade:
                            continue
                        # subjectごと
                        # simpler approach: look up if x[t_id,s1,subj,ts_id], x[t_id,s2,subj,ts_id] exist
                        # do a pass over all possible subj in x
                        # or we gather subjs for (t_id,ts_id)
                        subjs_for_that_ts = set([sbj for (tt, ss, sbj, tslot) in x.keys()
                                                 if tt==t_id and tslot==ts_id])
                        for subj_id in subjs_for_that_ts:
                            if (t_id, s1, subj_id, ts_id) in x and (t_id, s2, subj_id, ts_id) in x:
                                pair_var = model.NewBoolVar(f"sameGradeSubj_{t_id}_{ts_id}_{subj_id}_{s1}_{s2}")
                                x_s1 = x[(t_id, s1, subj_id, ts_id)]
                                x_s2 = x[(t_id, s2, subj_id, ts_id)]
                                sum_pair = model.NewIntVar(0, 2, f"sumPair_{t_id}_{subj_id}_{s1}_{s2}_{ts_id}")
                                model.Add(sum_pair == x_s1 + x_s2)
                                model.Add(sum_pair == 2).OnlyEnforceIf(pair_var)
                                model.Add(sum_pair != 2).OnlyEnforceIf(pair_var.Not())
                                obj_terms.append(pair_var * sameGradeSameSubjectBonus)

    # 3-4) レギュラー continuity ボーナス
    if regularClassContinuityBonus > 0:
        for (t_id, s_id, subj_id, ts_id), var in x.items():
            if (s_id, t_id, subj_id) in regular_class_continuity_info:
                obj_terms.append(var * regularClassContinuityBonus)

    # 3-5) ギャップペナルティ
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

    # solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        logger.info(f"Solution found. ObjVal={solver.ObjectiveValue()}")
        # build shift
        shifts = build_shift_objects(solver, x, teachers, students, timeslots, subjects)
        # gather shortage
        shortage_result = {}
        for (s_id, sbj_id), short_var in shortage.items():
            shortage_result[(s_id, sbj_id)] = solver.Value(short_var)
        return shifts, shortage_result
    else:
        logger.warning("No feasible solution found.")
        return [], {}

def build_shift_objects(solver: cp_model.CpSolver,
                        x_vars,
                        teachers: Dict[str, Teacher],
                        students: Dict[str, Student],
                        timeslots: Dict[str, TimeSlot],
                        subjects: Dict[str, Subject]) -> List[Shift]:
    # x=1 のみShift作成
    from collections import defaultdict
    assignment_dict = defaultdict(list)
    for (t_id, s_id, sbj_id, ts_id), var in x_vars.items():
        if solver.Value(var) == 1:
            assignment_dict[(t_id, sbj_id, ts_id)].append(s_id)

    shifts = []
    shift_counter = 1
    for (t_id, sbj_id, ts_id), s_list in assignment_dict.items():
        shift_id = f"Shift_{shift_counter}"
        shift_counter += 1

        teacher_obj = teachers[t_id]
        ts_obj = timeslots[ts_id]
        subj_obj = subjects[sbj_id]
        assigned_students = [students[sid] for sid in s_list]

        shifts.append(Shift(
            shift_id=shift_id,
            timeslot=ts_obj,
            teacher=teacher_obj,
            subject=subj_obj,
            assigned_students=assigned_students
        ))

    return shifts
