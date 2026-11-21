"""
tools.py - the CGPA Guider's tools, now living on the MCP server.

Same rules as Assignment 2: the agent never does arithmetic itself, and the
type hints + docstrings are what the model reads (FastMCP turns them into the
tool description / JSON schema, just like @tool did).

One deliberate change: bad input now RAISES ValueError instead of returning an
"Error: ..." string. Over MCP each tool has a declared return type (float/str);
a function that sometimes returns a string where a float was promised breaks
that schema. A raised ValueError becomes a proper MCP error result
(isError=True) which the agent relays to the student.
"""

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# 5.1 - PUCIT grade bands (marks lower-bound, grade points), checked high to low
# ---------------------------------------------------------------------------
_GRADE_BANDS = [
    (85, 4.0),   # A
    (80, 3.7),   # A-
    (75, 3.3),   # B+
    (70, 3.0),   # B
    (65, 2.7),   # B-
    (61, 2.3),   # C+
    (58, 2.0),   # C
    (55, 1.7),   # C-
    (50, 1.0),   # D
    (0, 0.0),    # F
]

# ---------------------------------------------------------------------------
# 5.2 - Scheme of studies. Each row: (course_code, course_name, credit_hours)
# ---------------------------------------------------------------------------
COURSES: dict[int, list[tuple[str, str, float]]] = {
    1: [("MS-251", "Probability & Statistics", 3.0),
        ("GE-160", "Applications of ICT", 3.0),
        ("GE-169", "Applied Physics", 3.0),
        ("GE-167", "Discrete Structures", 3.0),
        ("HQ-001", "Quran Translation - I", 0.5),
        ("GE-190", "Functional English", 3.0)],
    2: [("CC-112", "Programming Fundamentals", 3.0),
        ("CC-112-L", "Programming Fundamentals Lab", 1.0),
        ("CC-110", "Digital Logic Design", 2.0),
        ("CC-110-L", "Digital Logic Design Lab", 1.0),
        ("MS-252", "Linear Algebra", 3.0),
        ("GE-191", "Expository Writing", 3.0),
        ("GE-163", "Islamic Studies", 2.0),
        ("HQ-002", "Quran Translation - II", 0.5)],
    3: [("CC-211", "Object Oriented Programming", 3.0),
        ("CC-211-L", "Object Oriented Programming Lab", 1.0),
        ("CC-215", "Database Systems", 3.0),
        ("CC-215-L", "Database Systems Lab", 1.0),
        ("CC-210", "Computer Organization & Assembly Language", 3.0),
        ("GE-162", "Calculus & Analytical Geometry", 3.0),
        ("GE-192", "Introduction to Management", 2.0),
        ("HQ-003", "Quran Translation - III", 0.5)],
    4: [("CC-213", "Data Structures", 3.0),
        ("CC-213-L", "Data Structures Lab", 1.0),
        ("CC-312", "Information Security", 3.0),
        ("CC-214", "Computer Networks", 3.0),
        ("CC-212", "Software Engineering", 3.0),
        ("DC-220", "Advanced Database Management Systems", 3.0),
        ("HQ-004", "Quran Translation - IV", 0.5)],
    5: [("CC-313", "Analysis of Algorithms", 3.0),
        ("CC-310", "Artificial Intelligence", 3.0),
        ("DC-320", "Theory of Automata and Formal Languages", 3.0),
        ("DC-321", "Human Computer Interaction", 3.0),
        ("DC-322", "Computer Architecture", 3.0),
        ("EC-330", "Web Technologies / Elective", 3.0),
        ("HQ-005", "Quran Translation - V", 0.5)],
    6: [("CC-311", "Operating Systems", 3.0),
        ("EC-333", "Mobile Application Development / Elective", 3.0),
        ("EC-324", "Software Construction & Development / Elective", 3.0),
        ("EC-335", "Machine Learning / Elective", 3.0),
        ("EC-334", "Game Design and Development / Elective", 3.0),
        ("MS-253", "Multivariable Calculus", 3.0),
        ("HQ-006", "Quran Translation - VI", 0.5)],
    7: [("CC-411", "Final Year Project - I", 2.0),
        ("DC-328", "Parallel & Distributed Computing", 3.0),
        ("EC-345", "Computer Vision / Elective", 3.0),
        ("EC-425", "Software Quality Engineering / Elective", 3.0),
        ("MS-254", "Technical and Business Writing", 3.0),
        ("GE-263", "Entrepreneurship", 2.0),
        ("GE-262", "Professional Practices", 2.0),
        ("HQ-007", "Quran Translation - VII", 0.5)],
    8: [("CC-412", "Final Year Project - II", 4.0),
        ("DC-421", "Compiler Construction", 3.0),
        ("UE-272", "Introduction to Marketing", 3.0),
        ("GE-168", "Ideology and Constitution of Pakistan", 2.0),
        ("GE-363", "Civics and Community Engagement", 2.0),
        ("HQ-008", "Quran Translation - VIII", 0.5)],
}

# Non-credit, pass/fail - deliberately excluded from every GPA/CGPA calculation.
MD_COURSES = {"MD-001", "MD-002"}



def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def marks_to_grade_points(marks: float) -> float:
    """
    Convert a single numeric mark (0-100) into a PUCIT grade point.

    Use this whenever the student gives raw marks (e.g. "I got 78 in AI")
    and you need the grade point before it can go into
    calculate_semester_gpa. Call it once per course - never guess a grade
    point yourself.
    """
    if not _is_number(marks):
        raise ValueError("marks must be a number")
    if marks < 0 or marks > 100:
        raise ValueError("marks must be between 0 and 100")
    for lower_bound, points in _GRADE_BANDS:
        if marks >= lower_bound:
            return points
    return 0.0


def calculate_semester_gpa(grade_points: list[float], credit_hours: list[float]) -> float:
    """
    Calculate one semester's credit-weighted GPA from a list of grade
    points and the matching list of credit hours.

    Use this once you have a grade point (via marks_to_grade_points) for
    every course the student took in a semester, plus each course's
    credit hours. Both lists must be the same length and in the same
    course order. Never average the grade points by hand - this tool
    weights by credit hours.
    """
    if len(grade_points) != len(credit_hours):
        raise ValueError("grade_points and credit_hours must be the same length")
    if len(grade_points) == 0:
        raise ValueError("at least one course is required")
    if any(ch <= 0 for ch in credit_hours):
        raise ValueError("credit hours must be positive")
    if any(gp < 0 or gp > 4.0 for gp in grade_points):
        raise ValueError("grade points must be between 0.0 and 4.0")
    total_ch = sum(credit_hours)
    weighted = sum(gp * ch for gp, ch in zip(grade_points, credit_hours))
    return round(weighted / total_ch, 3)


def calculate_new_cgpa(
    current_cgpa: float,
    completed_credit_hours: float,
    semester_gpa: float,
    semester_credit_hours: float,
) -> float:
    """
    Project the CGPA after folding in one more semester's GPA.

    Use this when the student already knows their current CGPA and total
    completed credit hours, and wants to know where a semester GPA
    (actual or hypothetical) would leave their CGPA.
    """
    if completed_credit_hours < 0:
        raise ValueError("completed_credit_hours must be non-negative")
    if semester_credit_hours <= 0:
        raise ValueError("semester_credit_hours must be positive")
    if not (0.0 <= current_cgpa <= 4.0) or not (0.0 <= semester_gpa <= 4.0):
        raise ValueError("CGPA and GPA values must be between 0.0 and 4.0")
    numerator = current_cgpa * completed_credit_hours + semester_gpa * semester_credit_hours
    denominator = completed_credit_hours + semester_credit_hours
    return round(numerator / denominator, 3)


def required_gpa_for_target(
    target_cgpa: float,
    current_cgpa: float,
    completed_credit_hours: float,
    remaining_credit_hours: float,
) -> float:
    """
    Calculate the GPA needed over the remaining credit hours to reach a
    target CGPA.

    Use this whenever the student names a CGPA they want to end up with.
    The result can legitimately come out above 4.0 - that means the
    target is impossible over that many remaining hours. Report that
    plainly rather than rounding it down. To find a horizon that actually
    works, get a larger hour total from get_credit_hours (e.g. semesters
    [5], then [5, 6], then [5, 6, 7]) and re-run this tool with it.
    """
    if remaining_credit_hours <= 0:
        raise ValueError("remaining_credit_hours must be positive")
    if completed_credit_hours < 0:
        raise ValueError("completed_credit_hours must be non-negative")
    if not (0.0 <= current_cgpa <= 4.0) or not (0.0 <= target_cgpa <= 4.0):
        raise ValueError("CGPA values must be between 0.0 and 4.0")
    numerator = (
        target_cgpa * (completed_credit_hours + remaining_credit_hours)
        - current_cgpa * completed_credit_hours
    )
    return round(numerator / remaining_credit_hours, 3)


def get_semester_courses(semester: int) -> str:
    """
    Look up the official courses and credit hours for one semester of the
    PUCIT BS(CS) scheme of studies.

    Use this when the student doesn't remember, or hasn't stated, which
    courses/credit hours a given semester carries, or to confirm a credit
    hour figure before calling another tool.
    """
    if not isinstance(semester, int) or semester < 1 or semester > 8:
        raise ValueError("semester must be between 1 and 8")
    lines = [f"Semester {semester}:"]
    total = 0.0
    for code, name, ch in COURSES[semester]:
        tag = " (non-credit, pass/fail)" if code in MD_COURSES else ""
        lines.append(f"  {code} - {name} ({ch} credit hours){tag}")
        total += ch
    lines.append(f"Total: {total} credit hours")
    return "\n".join(lines)


def get_credit_hours(semesters: list[int]) -> float:
    """
    Total the graded credit hours of the given semesters, e.g. [5, 6] -> 37.0.

    Use this to size a planning horizon: the semester(s) the student is in or
    about to start, plus later ones when a target needs a GPA above 4.0 over
    a shorter window. Math Deficiency courses are excluded, as always.
    """
    if not semesters:
        raise ValueError("give at least one semester")
    total = 0.0
    for sem in semesters:
        if not isinstance(sem, int) or isinstance(sem, bool) or sem < 1 or sem > 8:
            raise ValueError("every semester must be an integer between 1 and 8")
        total += sum(ch for code, _n, ch in COURSES[sem] if code not in MD_COURSES)
    return total


def get_remaining_credit_hours(current_semester: int) -> float:
    """
    Total the graded credit hours in every semester AFTER current_semester,
    up to semester 8 (Math Deficiency courses are excluded, as always).

    It does NOT include current_semester itself. Use it to find out how many
    credit hours a student still has left to finish the degree.
    """
    if not isinstance(current_semester, int) or current_semester < 1 or current_semester > 8:
        raise ValueError("current_semester must be between 1 and 8")
    total = 0.0
    for sem in range(current_semester + 1, 9):
        for code, _name, ch in COURSES.get(sem, []):
            if code not in MD_COURSES:
                total += ch
    return total


# Reports go in ONE fixed folder on the server. The filename is sanitised so a
# caller can never write outside it (no "../", no absolute paths): this server
# is public on the internet, so the model's arguments are untrusted input.
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports"))


def save_report(filename: str, content: str) -> str:
    """
    Save a text summary - a semester GPA, a projected CGPA, or a plan for
    reaching a target - to a .txt file and confirm it was saved.

    Only call this when the student has explicitly asked you to save
    something, and only after you've produced a real result. Never call
    this after a clarifying question or a bare grade lookup.
    """
    if not filename or not filename.strip():
        raise ValueError("filename cannot be empty")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename.strip().replace("\\", "/")).name)
    name = name.lstrip(".") or "report"
    if not name.endswith(".txt"):
        name += ".txt"
    if len(content) > 20_000:
        raise ValueError("report is too long (max 20,000 characters)")
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / name).write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"could not save file ({exc})") from exc
    return f"Saved report to {REPORTS_DIR / name}"
