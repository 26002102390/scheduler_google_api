# config.py (例)

import logging
import os

LOG_LEVEL = logging.INFO

DATA_DIR = "./api_data"
OUTPUT_DIR = "output"

SUBJECTS_CSV = os.path.join(DATA_DIR, "subjects.csv")
TEACHERS_CSV = os.path.join(DATA_DIR, "teachers.csv")
STUDENTS_CSV = os.path.join(DATA_DIR, "students.csv")
STUDENT_REQUIREMENTS_CSV = os.path.join(DATA_DIR, "student_requirements.csv")
TIMESLOTS_CSV = os.path.join(DATA_DIR, "timeslots.csv")
TEACHER_AVAILABILITY_CSV = os.path.join(DATA_DIR, "teacher_availability.csv")
STUDENT_AVAILABILITY_CSV = os.path.join(DATA_DIR, "student_availability.csv")
REGULAR_CLASSES_CSV = os.path.join(DATA_DIR, "regular_classes.csv")
CONSTRAINT_WEIGHTS_CSV = os.path.join(DATA_DIR, "constraint_weights.csv")
CAMPAIGN_CSV = os.path.join(DATA_DIR, "campaign.csv")
