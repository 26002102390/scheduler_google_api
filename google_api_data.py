import gspread
from google.oauth2.service_account import Credentials

# ① ダウンロードしたJSONのファイルパス
SERVICE_ACCOUNT_FILE = "/Users/cdl/Desktop/triple-water-451506-t4-df3fab7dcfb4.json"

# ② スコープの設定（読み書き両方の権限を付与）
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# ③ 認証情報の取得
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# ④ Googleスプレッドシートに接続
client = gspread.authorize(creds)

# ⑤ スプレッドシートを開く
SPREADSHEET_URL_teacher = "https://docs.google.com/spreadsheets/d/1xKQcSv2R3KhkD3oSbymHrW8YR21CvlphIyFoUu4Ji94/edit"
SPREADSHEET_URL_student = "https://docs.google.com/spreadsheets/d/1Pggs62VJPSQTQhMW2YxiYcWqzju3T0uBo7g3hreVAiI/edit"
SPREADSHEET_ID_teacher = SPREADSHEET_URL_teacher.split('/')[5]
SPREADSHEET_ID_student = SPREADSHEET_URL_student.split('/')[5]

sheet_teacher = client.open_by_key(SPREADSHEET_ID_teacher).sheet1
sheet_student = client.open_by_key(SPREADSHEET_ID_student).sheet1

# ⑥ データを取得して整形
all_values_teacher = sheet_teacher.get_all_values()
all_values_student = sheet_student.get_all_values()

headers_teacher = all_values_teacher[0]
data_teacher = all_values_teacher[1:]
headers_student = all_values_student[0]
data_student = all_values_student[1:]

def parse_periods(period_str):
    """時限文字列をパースして辞書形式に変換"""
    periods = {2: False, 3: False, 4: False, 5: False, 6: False}
    if not period_str:
        return periods
    
    # "2限, 3限, 4限" → [2, 3, 4]
    available = [int(p.strip().replace('限', '')) for p in period_str.split(',') if p.strip()]
    
    for p in available:
        if p in periods:
            periods[p] = True
    
    return periods



# 名前をキーとして，他のデータに関する辞書を値とする辞書を作成
teachers_dict = {}
# print(headers_teacher)
for row in data_teacher:
    name = row[1]
    teachers_dict[name] = {
        headers_teacher[i]: row[i] for i in range(len(headers_teacher)) if i != 1
    }
# print(teachers_dict)

students_dict = {}
for row in data_student:
    name = row[1]
    students_dict[name] = {
        headers_student[i]: row[i] for i in range(len(headers_student)) if i != 1
    }
# print(students_dict)

# print(students_dict)
# print(headers_student)
# print(data_student)
print(teachers_dict)
# print(headers_teacher)
# print(data_teacher)


# ------------------------------------------------------------
# timeslots.csvデータの生成
# ------------------------------------------------------------
# timeslotを作成
timeslot = []
for j in headers_teacher:
    if j.startswith("シフト"):
        # jを[でスライス
        j = j.split("[")[1].split("]")[0]
        # print(j)
        j = j.split("/")
        #2025-08-01 このような形式で，jを整形
        # 月と日を2桁の形式に整形
        month = j[0].zfill(2)  # 1桁の場合は0埋めして2桁に
        day = j[1].split("（")[0].zfill(2)  # 1桁の場合は0埋めして2桁に
        j = f"2025-{month}-{day}"
        # print(j)
        timeslot.append(j)


def generate_timeslots(dates):
    """タイムスロットデータを生成する関数"""
    timeslots = []
    slot_id = 1
    
    # ヘッダー
    headers = ['timeslot_id', 'date', 'period_index', 'campaign_id', 'period_label']
    timeslots.append(headers)
    
    # 各日付について2〜6限までのタイムスロットを生成
    for date in sorted(set(dates)):  # 重複を除去してソート
        for period in range(2, 7):  # 2限から6限まで
            row = [
                f'TS{slot_id}',  # timeslot_id
                date,            # date
                str(period),     # period_index
                'CAM1',         # campaign_id
                f'{period}限'    # period_label
            ]
            timeslots.append(row)
            slot_id += 1
    
    return timeslots

# timeslotデータの生成
unique_dates = list(set(timeslot))  # 重複を除去
timeslot_data = generate_timeslots(unique_dates)

# CSVファイルとして保存
import csv
with open('api_data/timeslots.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(timeslot_data)

print("Timeslots generated successfully!")


# ------------------------------------------------------------
# teachers.csvデータの生成
# ------------------------------------------------------------
def parse_teachable_subjects(subjects_str):
    """指導可能科目の文字列からsubject_idのリストを抽出する"""
    # 科目名とsubject_idの対応マップ
    subject_mapping = {
        "国語（小学生）": "ES_Japanese",
        "算数（小学生）": "ES_Math",
        "理科（小学生）": "ES_Science",
        "社会（小学生）": "ES_Social",
        "英語（小学生）": "ES_English",
        
        "国語（中学生）": "MS_Japanese",
        "数学（中学生）": "MS_Math",
        "理科（中学生）": "MS_Science",
        "社会（中学生）": "MS_Social",
        "英語（中学生）": "MS_English",
        
        "国語（高校生）": "HS_Japanese",
        "数学ⅠA（高校生）": "HS_Math2B",  # 注: ⅠAからⅡBまでを含む
        "数学ⅡB（高校生）": "HS_Math2B",
        "数学ⅢC（高校生）": "HS_Math3C",
        "英語（高校生）": "HS_English",
        "物理基礎（高校生）": "HS_PhysicsBasic",
        "物理（高校生）": "HS_Physics",
        "化学基礎（高校生）": "HS_ChemistryBasic",
        "化学（高校生）": "HS_Chemistry",
        "生物基礎（高校生）": "HS_BiologyBasic",
        "生物（高校生）": "HS_Biology",
        "地学基礎（高校生）": "HS_GeologyBasic",
        "地学（高校生）": "HS_Geology",
        "世界史（高校生）": "HS_WorldHistory",
        "日本史（高校生）": "HS_JapaneseHistory",
        "地理（高校生）": "HS_Geography",
        "倫理（高校生）": "HS_Ethics",
        "政経（高校生）": "HS_PoliticsEconomy"
    }
    
    # 入力文字列を科目リストに分割
    subjects_list = [s.strip() for s in subjects_str.split(',')]
    
    # 対応するsubject_idを抽出
    subject_ids = []
    for subject in subjects_list:
        if subject in subject_mapping:
            subject_ids.append(subject_mapping[subject])
    
    return subject_ids

teachers_data = {}
for i in teachers_dict:
    teacher_name = i
    teachable_subjects = parse_teachable_subjects(teachers_dict[i]["指導可能科目"])
    min_continuous = teachers_dict[i]["最低限出勤コマ数"]
    teachers_data[teacher_name] = teachable_subjects, min_continuous

# print(teachers_data)

def generate_teachers(teachers_data):
    """タイムスロットデータを生成する関数"""
    teachers = []
    T_id = 1
    
    # ヘッダー
    headers = ["teacher_id","teacher_name","desired_shift_count","min_classes","teachable_subjects"]
    teachers.append(headers)
    
    for i in teachers_data:
        row = [
            f'T{T_id}',  # "teacher_id"
            i,            # "teacher_name"
            20,     # "desired_shift_count"
            teachers_data[i][1],         # "min_classes"
            "|".join(teachers_data[i][0]) # "teachable_subjects"
        ]
        teachers.append(row)
        T_id += 1
    
    return teachers

# teachersデータの生成
teachers_data = generate_teachers(teachers_data)

# CSVファイルとして保存
import csv
with open('api_data/teachers.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(teachers_data)

print("teachers.csv generated successfully!")


# ------------------------------------------------------------
# teacher_availability.csvデータの生成
# ------------------------------------------------------------
teacher_availability = {}
for i in teachers_dict:
    teacher_name = i
    teacher_availability[teacher_name] = {}
    for j in headers_teacher:
        if j.startswith("シフト"):
            # シフトの時限を取得
            available_periods = teachers_dict[teacher_name][j]
            j = j.split("[")[1].split("]")[0]
            j = j.split("/")
            j = f"2025-{j[0].zfill(2)}-{j[1].split('（')[0].zfill(2)}"
            teacher_availability[teacher_name][j] = available_periods
# print(teacher_availability)

def generate_teacher_availability_csv(teacher_availability, teachers_data, timeslot_data):
    """教師の空き時間データをCSV形式に変換する関数"""
    availability_csv = []
    
    # ヘッダー
    headers = ['teacher_id', 'teacher_name', 'timeslot_id', 'date', 'period_label']
    availability_csv.append(headers)
    
    # timeslot_dataからtimeslot_idを取得するための辞書を作成
    timeslot_dict = {}
    for row in timeslot_data[1:]:  # ヘッダーをスキップ
        key = (row[1], row[4])  # (date, period_label)をキーとする
        timeslot_dict[key] = row[0]  # timeslot_idを値とする
    
    # 各教師の利用可能時間を処理
    for teacher_name, availability in teacher_availability.items():
        # 教師IDを取得
        teacher_id = next(row[0] for row in teachers_data[1:] if row[1] == teacher_name)
        
        for date, periods in availability.items():
            # カンマで区切られた時限を分割
            if periods:  # 空でない場合のみ処理
                period_list = [p.strip() for p in periods.split(',')]
                for period in period_list:
                    period_label = f"{period}"
                    # timeslot_idを取得
                    timeslot_id = timeslot_dict.get((date, period_label))
                    if timeslot_id:
                        row = [
                            teacher_id,
                            teacher_name,
                            timeslot_id,
                            date,
                            period_label
                        ]
                        availability_csv.append(row)
    
    return availability_csv

# CSVデータを生成
teacher_availability_csv = generate_teacher_availability_csv(teacher_availability, teachers_data, timeslot_data)

# CSVファイルとして保存
import csv
with open('api_data/teacher_availability.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(teacher_availability_csv)

print("Teacher availability CSV generated successfully!")



# ------------------------------------------------------------
# students.csvデータの生成
# ------------------------------------------------------------
def generate_students_csv(students_dict):
    """生徒データをCSV形式に変換する関数"""
    students = []
    
    # ヘッダー
    headers = ['student_id', 'student_name', 'grade', 'gap_preference']
    students.append(headers)
    
    # 生徒IDのカウンター
    student_id = 1
    
    for student_name, info in students_dict.items():
        # 学年（grade）の判定
        grade_category = info['所属を選んでください']
        if grade_category == '小学生':
            grade = 'Elementary'
            grade_number = info['学年(elementary)'].split('年')[0]
        elif grade_category == '中学生':
            grade = 'Middle'
            grade_number = info['学年(middle)'].split('年')[0]
        else:  # 高校生
            grade = 'High'
            grade_number = info['学年(high)'].split('年')[0]
        grade_info = grade + grade_number
        # 空きコマの設定
        gap_preference = 'NoGapPreferred' if info['空きコマに関する質問'] == '空きコマは避けたい' else 'GapAllowed'
        
        # 行データの作成
        row = [
            f'S{student_id}',  # student_id
            student_name,      # student_name
            grade_info,            # grade
            gap_preference    # gap_preference
        ]
        students.append(row)
        student_id += 1
    
    return students

# CSVデータを生成
students_csv = generate_students_csv(students_dict)

# CSVファイルとして保存
import csv
with open('api_data/students.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(students_csv)

print("Students CSV generated successfully!")


# ------------------------------------------------------------
# student_requirements.csvデータの生成
# ------------------------------------------------------------
def generate_student_requirements_csv(students_dict):
    """生徒の受講希望科目データをCSV形式に変換する関数"""
    requirements = []
    
    # ヘッダー
    headers = ['student_id', 'student_name', 'subject_id', 'required_count']
    requirements.append(headers)
    
    # 科目名とsubject_idの対応マップ
    subject_mapping = {
        '小学生：受講希望科目 （表を右にスクロールできます） [英語]': 'ES_English',
        '小学生：受講希望科目 （表を右にスクロールできます） [算数]': 'ES_Math',
        '小学生：受講希望科目 （表を右にスクロールできます） [国語]': 'ES_Japanese',
        '小学生：受講希望科目 （表を右にスクロールできます） [理科]': 'ES_Science',
        '小学生：受講希望科目 （表を右にスクロールできます） [社会]': 'ES_Social',
        
        '中学生：受講希望科目 （表を右にスクロールできます） [英語]': 'MS_English',
        '中学生：受講希望科目 （表を右にスクロールできます） [数学]': 'MS_Math',
        '中学生：受講希望科目 （表を右にスクロールできます） [国語]': 'MS_Japanese',
        '中学生：受講希望科目 （表を右にスクロールできます） [理科]': 'MS_Science',
        '中学生：受講希望科目 （表を右にスクロールできます） [社会]': 'MS_Social',
        
        '高校生：受講希望科目 （表を右にスクロールできます） [英語]': 'HS_English',
        '高校生：受講希望科目 （表を右にスクロールできます） [数学ⅠA]': 'HS_Math2B',
        '高校生：受講希望科目 （表を右にスクロールできます） [数学ⅡB]': 'HS_Math2B',
        '高校生：受講希望科目 （表を右にスクロールできます） [数学ⅢC]': 'HS_Math3C',
        '高校生：受講希望科目 （表を右にスクロールできます） [国語]': 'HS_Japanese',
        '高校生：受講希望科目 （表を右にスクロールできます） [化学基礎]': 'HS_ChemistryBasic',
        '高校生：受講希望科目 （表を右にスクロールできます） [化学]': 'HS_Chemistry',
        '高校生：受講希望科目 （表を右にスクロールできます） [物理基礎]': 'HS_PhysicsBasic',
        '高校生：受講希望科目 （表を右にスクロールできます） [物理]': 'HS_Physics',
        '高校生：受講希望科目 （表を右にスクロールできます） [生物基礎]': 'HS_BiologyBasic',
        '高校生：受講希望科目 （表を右にスクロールできます） [生物]': 'HS_Biology',
        '高校生：受講希望科目 （表を右にスクロールできます） [地学基礎]': 'HS_GeologyBasic',
        '高校生：受講希望科目 （表を右にスクロールできます） [地学]': 'HS_Geology',
        '高校生：受講希望科目 （表を右にスクロールできます） [地理]': 'HS_Geography',
        '高校生：受講希望科目 （表を右にスクロールできます） [日本史]': 'HS_JapaneseHistory',
        '高校生：受講希望科目 （表を右にスクロールできます） [世界史]': 'HS_WorldHistory',
        '高校生：受講希望科目 （表を右にスクロールできます） [倫理]': 'HS_Ethics',
        '高校生：受講希望科目 （表を右にスクロールできます） [政経]': 'HS_PoliticsEconomy'
    }
    
    student_id = 1
    for student_name, info in students_dict.items():
        # 各科目について処理
        for subject_key, subject_id in subject_mapping.items():
            if subject_key in info and info[subject_key]:
                # コマ数を抽出（"3コマ" → 3）
                required_count = int(info[subject_key].replace('コマ', ''))
                if required_count > 0:
                    row = [
                        f'S{student_id}',  # student_id
                        student_name,      # student_name
                        subject_id,        # subject_id
                        required_count     # required_count
                    ]
                    requirements.append(row)
        student_id += 1
    
    return requirements

# CSVデータを生成
student_requirements_csv = generate_student_requirements_csv(students_dict)

# CSVファイルとして保存
import csv
with open('api_data/student_requirements.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(student_requirements_csv)

print("Student requirements CSV generated successfully!")


# ------------------------------------------------------------
# student_availability.csvデータの生成
# ------------------------------------------------------------
def generate_student_availability_csv(students_dict, timeslot_data):
    """生徒の利用可能時間データをCSV形式に変換する関数"""
    availability = []
    
    # ヘッダー
    headers = ['student_id', 'student_name', 'timeslot_id', 'date', 'period_label']
    availability.append(headers)
    
    # timeslot_dataからtimeslot_idを取得するための辞書を作成
    timeslot_dict = {}
    for row in timeslot_data[1:]:  # ヘッダーをスキップ
        key = (row[1], row[4])  # (date, period_label)をキーとする
        timeslot_dict[key] = row[0]  # timeslot_idを値とする
    
    student_id = 1
    for student_name, info in students_dict.items():
        # 各日付の希望時限を処理
        for date_key in info:
            if date_key.startswith('希望授業枠'):
                if info[date_key]:  # 空でない場合のみ処理
                    # 日付を抽出 [8/1] → 2025-08-01
                    date_str = date_key.split('[')[1].split(']')[0]
                    month, day = date_str.split('/')
                    formatted_date = f"2025-{month.zfill(2)}-{day.zfill(2)}"
                    
                    # 時限リストを処理
                    periods = [p.strip() for p in info[date_key].split(',')]
                    for period in periods:
                        period_label = f"{period}"
                        # timeslot_idを取得
                        timeslot_id = timeslot_dict.get((formatted_date, period_label))
                        if timeslot_id:
                            row = [
                                f'S{student_id}',
                                student_name,
                                timeslot_id,
                                formatted_date,
                                period_label
                            ]
                            availability.append(row)
        student_id += 1
    
    return availability

# CSVデータを生成
student_availability_csv = generate_student_availability_csv(students_dict, timeslot_data)

# CSVファイルとして保存
import csv
with open('api_data/student_availability.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(student_availability_csv)

print("Student availability CSV generated successfully!")


# ------------------------------------------------------------
# regular_classes.csvデータの生成
# ------------------------------------------------------------
def generate_regular_classes_csv(teachers_dict):
    """通常授業データをCSV形式に変換する関数"""
    regular_classes = []
    
    # ヘッダー
    headers = ['regular_class_id', 'teacher_id', 'teacher_name', 'subject_id', 'subject_name', 'timeslot_id', 'enrolled_student_ids']
    regular_classes.append(headers)
    
    # 科目名とsubject_idの対応マップ
    subject_mapping = {
        "英語（小学生）": ("ES_English", "英語"),
        "算数（小学生）": ("ES_Math", "算数"),
        "国語（小学生）": ("ES_Japanese", "国語"),
        "理科（小学生）": ("ES_Science", "理科"),
        "社会（小学生）": ("ES_Social", "社会"),
        
        "英語（中学生）": ("MS_English", "英語"),
        "数学（中学生）": ("MS_Math", "数学"),
        "国語（中学生）": ("MS_Japanese", "国語"),
        "理科（中学生）": ("MS_Science", "理科"),
        "社会（中学生）": ("MS_Social", "社会"),
        
        "英語（高校生）": ("HS_English", "英語"),
        "数学ⅠA（高校生）": ("HS_Math2B", "数学ⅠA"),
        "数学ⅡB（高校生）": ("HS_Math2B", "数学ⅡB"),
        "数学ⅢC（高校生）": ("HS_Math3C", "数学ⅢC"),
        "国語（高校生）": ("HS_Japanese", "国語"),
        # ... 他の科目も同様に追加
    }
    
    class_id = 1
    for teacher_name, info in teachers_dict.items():
        # 担当授業の情報を処理
        for i in range(1, 4):  # 授業1から授業3まで処理
            student_name = info.get(f'担当生徒名{i}')
            subject = info.get(f'授業{i}')
            day = info.get(f'授業日{i}')
            period = info.get(f'授業時間{i}')
            
            if student_name and subject and day and period:
                # subject_idとsubject_nameを取得
                subject_info = subject_mapping.get(subject)
                if subject_info:
                    subject_id, subject_name = subject_info
                    
                    row = [
                        f'RC{class_id}',          # regular_class_id
                        f'T{class_id}',           # teacher_id（仮のID）
                        teacher_name,             # teacher_name
                        subject_id,               # subject_id
                        subject_name,             # subject_name
                        f'TS{class_id}',          # timeslot_id（仮のID）
                        f'S{class_id}'            # enrolled_student_ids（仮のID）
                    ]
                    regular_classes.append(row)
                    class_id += 1
    
    return regular_classes

# CSVデータを生成
regular_classes_csv = generate_regular_classes_csv(teachers_dict)

# CSVファイルとして保存
import csv
with open('api_data/regular_classes.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(regular_classes_csv)

print("Regular classes CSV generated successfully!")


