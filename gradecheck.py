# Program to check marks on Canvas when given user IDs & course IDs
# Student IDs are stored in CSV file; Course IDs are hard-coded for now

# TODO: Courses classed into semesters based on when new courses are added
# TODO: Data file that holds courses and 
# TODO: File to cache students and compare with csv

import csv
import os
import time
import json
import operator
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from canvasapi import Canvas
import canvasapi

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates


API_URL = config["url"]
API_KEY = config["key"]
TWO_SEM_COURSES = config["two_sem"]
THIS_SEM_COURSES = config["this_sem"]

ALL_COURSES = TWO_SEM_COURSES + THIS_SEM_COURSES


class Student:
    """Class to hold info on a student"""
    def __init__(self, name, id):
        self.id = id
        self.name = name
        self.courses = []

    def __str__(self):
        return f"{self.name}: {self.display_average()}"

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.name}, {self.id})"

    def average(self):
        if self.courses:
            return round(sum([c.grade for c in self.courses]) / len(self.courses), 2)
        else:
            return None

    def display_average(self):
        if self.courses:
            return f"{self.average():.2f}%"
        else:
            return "ERROR"
    
    def print_info(self):
        if len(self.courses) > 0:
            print(f"{self.name}: {self.display_average()}")
            for c in self.courses:
                print(f"\t{c}")
        else:
            print("No info.")

    def add_course(self, id, name, current_score):
        self.courses.append(GCEnrollment(id, name, current_score))

    def to_dict_for_logging(self):
        return {"Name": self.name, "average": self.average(), "courses": [(c.name, c.grade) for c in self.courses]}


class GCEnrollment:
    """
    Class for student enrollment in a course.
    Named thus so not to interfere with Enrollment class in canvasapi.
    """
    def __init__(self, id, name, grade):
        self.id = id
        self.name = name
        self.grade = grade
    
    def __str__(self):
        return f"{self.name}: {self.grade}%"

    def __repr__(self):
        return f"{self.__class__.__qualname__}({self.id}, {self.name}, {self.grade})"


class StudentNotFoundError(Exception):
    """Exception to raise when a search query doesn't match a student"""
    pass


def get_students(filename) -> list[Student]:
    """Get list of students from csv file, sort alpha"""
    students = []
    with open(filename, 'r') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if row['Check'].lower().strip() == "yes":
                name = row['Student Name']
                id = int(row['Canvas ID'])
                students.append(Student(name, id))
            else:
                continue
    return sorted(students, key=operator.attrgetter('name'))


def read_empty_courses_from_json(filename):
    """Reads the json list of empty courses, returns List"""
    try:
        with open(filename, 'r') as f:
            empty_courses = json.load(f)
            return empty_courses
    except FileNotFoundError:
        return []


def write_empty_courses_to_json(filename, empties):
    """Overwrites the json file with the new list of empty courses"""
    with open(filename, 'w') as f:
        f.write(json.dumps(empties))


def search_student(students, query):
    """Returns a student if a single name is found."""
    results = [s for s in students if query.lower() in s.name.lower()]
    if not results:
        raise StudentNotFoundError
    elif len(results) > 1:
        narrow_results = [r for r in results if query.lower() in r.name.lower()[:len(query)]]
        if len(narrow_results) != 1:
            raise StudentNotFoundError
        else:
            results = narrow_results
    return results[0]


def load_json_history():
    try:
        with open("history.json", "r") as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {}
    finally:
        return history


def log_history_json(students: list[Student]):
    """Log all history from session to a JSON file."""
    date = datetime.today().strftime("%Y-%m-%d")
    new_data = {s.id: s.to_dict_for_logging() for s in students}
    old_file = load_json_history()
    old_file.update({date: new_data}) # Will overwrite if today is already logged
    new_json = json.dumps(old_file)
    with open("history.json", "w") as f:
        f.write(new_json)


def plot_student_grades(student):
    """Plot a single student's history."""
    history = load_json_history()

    # Filter the dates in case of a new student
    # Get x and y axes lists
    relevant_dates = {k: v for k, v in history.items() if str(student.id) in v}
    dates = [datetime.strptime(date, "%Y-%m-%d") for date in relevant_dates]
    averages = [date[str(student.id)]["average"] for date in relevant_dates.values()]
    courses_by_day = [date[str(student.id)]["courses"] for date in relevant_dates.values()]

    # Plot the average as well as the courses
    fig, ax = plt.subplots()
    ax.plot(dates, averages, linewidth=3.0, label="Average", linestyle="dashed", alpha=0.3)

    num_courses = len(courses_by_day[0])
    for i in range(num_courses):
        label = courses_by_day[0][i][0]
        y_values = [day[i][1] for day in courses_by_day]
        ax.plot(dates, y_values, label=label, linewidth=3.0)

    plt.legend()
    title_font = {"weight": "bold"}
    plt.title(f"Grades for {student.name}", fontdict=title_font)
    plt.xlabel("Date", fontdict=title_font)
    plt.ylabel("Grade %", fontdict=title_font)
    ax.set(xlim=(dates[0], dates[-1]), ylim=(0, 100), yticks=range(0,100, 5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.tight_layout()
    manager = plt.get_current_fig_manager()
    today_str = dates[-1].strftime("%Y-%m-%d")
    manager.set_window_title(f"{student.name} Grades History {today_str}")

    for label in ax.get_xticklabels(which='major'):
        label.set(rotation=30, horizontalalignment='right')
    
    plt.show()


def _get_course(id: int) -> dict:
    """Take a course id, return dict with name, id, and enrollments."""
    try:
        course = canvas.get_course(id)
    except canvasapi.exceptions.Unauthorized:
        print(f"Could not access course {id}: Unauthorized")
        quit()
    else:
        enrollments = course.get_enrollments(type='StudentEnrollment')
        for enroll in enrollments:
            pass # Because PaginatedList is lazy

        return {"name": course.name, "id": course.id, "enrollments": enrollments}


def get_all_enrollments(canvas: Canvas, course_ids: list[int], students: list[Student]) -> dict:
    """
    Get all courses with enrollments.
    Check for empty courses and log if necessary.
    Return dict with all enrollments mapped to user_ids.
    """
    # Get the courses
    with ThreadPoolExecutor(max_workers=32) as executor:
        courses = executor.map(_get_course, course_ids)

    # Initialize target data structures before looping through courses
    student_ids = [student.id for student in students]
    all_enrollments = {id: [] for id in student_ids}
    empty_courses = []
    
    # Loop through courses and filter them
    for course in courses:
        enrolls = 0
        for enrollment in course["enrollments"]:
            if enrollment.user_id in student_ids and enrollment.grades["current_score"] != None:
                enrollment.course_name = course["name"]
                all_enrollments[enrollment.user_id].append(enrollment)
                enrolls += 1
            elif enrollment.user_id in student_ids:
                enrolls += 1
        if not enrolls:
            empty_courses.append(course["id"])
    
    # If empty courses are found, it's likely a new term, so overwrite file
    if empty_courses:
        write_empty_courses_to_json('empty_courses.json', empty_courses)
        ## NEW TERM STUFF HERE 

    return all_enrollments


def append_enrollments(students: list[Student], enrollments):
    """Map the list of enrollments to the students."""
    for student in students:
        for e in enrollments[student.id]:
            student.add_course(e.course_id, e.course_name, e.grades["current_score"])


def main():
    with open("config.json", "r") as fp:
        global config
        config = json.load(fp)

    start_time = time.time()

    print("Grade Checker")

    # Make Canvas instance
    global canvas 
    canvas = Canvas(API_URL, API_KEY)

    os.chdir(Path(__file__).parent.absolute())

    # Get student and enrollment info
    students = get_students('students.csv')
    empty_courses = read_empty_courses_from_json('empty_courses.json')
    course_ids = [c for c in ALL_COURSES if c not in empty_courses]
    enrollments = get_all_enrollments(canvas, course_ids, students)

    # Append enrollment info to student objects
    append_enrollments(students, enrollments)

    # Print results to console and log overall avg to csv doc
    print("", end="\r")
    for s in students:
        print(f"{s.name:.<20.20}{s.display_average()} ({len(s.courses)} courses)")

    log_history_json(students)
    
    end_time = time.time()

    # Finish by giving user input
    while True:
        user_input = input("\nEnter student name for details: ")
        if user_input == 'q':
            break
        elif user_input == '/time':
            print(f"\nTotal time elapsed: {round(end_time - start_time, 1)}")
        elif user_input == '/courses':
            print(f"Number of courses: {len(course_ids)}")
        elif user_input.startswith("/graph"):
            words = user_input.split(" ")
            query = "".join(words[1:])
            print(query)
            try: 
                student = search_student(students, query)
                plot_student_grades(student)
            except StudentNotFoundError:
                print("Student not found.")
            
        elif user_input == '/reset':
            pass # delete history
        else:
            try:
                search_student(students, user_input).print_info()
            except StudentNotFoundError:
                print("Student not found.")


if __name__=='__main__':
    main()