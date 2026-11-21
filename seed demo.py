"""
Fills the database with sample employees and attendance so every page,
chart and report has data to show.

Run it from the backend folder (the one with manage.py):

    python seed_demo.py            add the sample data (safe to run again)
    python seed_demo.py --clear    remove ONLY the sample data again

Sample employees use emails ending in @demo.example, so your real
employees are never touched.
"""

import os
import random
import sys
from datetime import timedelta
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import timezone  # noqa: E402

from employees.models import Attendance, Employee  # noqa: E402

DEMO_DOMAIN = "@demo.example"

# name, department, designation, monthly salary, days since joining, status
PEOPLE = [
    ("Aarav Sharma",    "IT",        "Senior Developer",     85000, 1450, "Active"),
    ("Priya Nair",      "IT",        "Frontend Developer",   62000,  820, "Active"),
    ("Rohan Gupta",     "IT",        "DevOps Engineer",      74000,  610, "Active"),
    ("Sneha Reddy",     "IT",        "QA Engineer",          48000,  300, "Active"),
    ("Karthik Iyer",    "IT",        "Software Intern",      18000,   12, "Active"),
    ("Meera Pillai",    "HR",        "HR Manager",           70000, 1700, "Active"),
    ("Vikram Singh",    "HR",        "Recruiter",            42000,  540, "Active"),
    ("Ananya Das",      "HR",        "HR Executive",         36000,  210, "Active"),
    ("Rahul Verma",     "Finance",   "Accountant",           52000,  900, "Active"),
    ("Divya Menon",     "Finance",   "Financial Analyst",    66000,  480, "Active"),
    ("Arjun Patel",     "Finance",   "Finance Manager",      90000, 2100, "Active"),
    ("Kavya Joshi",     "Marketing", "Marketing Lead",       72000, 1100, "Active"),
    ("Nikhil Rao",      "Marketing", "Content Strategist",   45000,  390, "Active"),
    ("Isha Kapoor",     "Marketing", "SEO Specialist",       40000,  250, "Active"),
    ("Siddharth Jain",  "Marketing", "Graphic Designer",     38000,    9, "Active"),
    ("Pooja Bhat",      "Sales",     "Sales Manager",        80000, 1600, "Active"),
    ("Manoj Kumar",     "Sales",     "Sales Executive",      35000,  700, "Active"),
    ("Lakshmi Narayan", "Sales",     "Account Manager",      55000,  430, "Active"),
    ("Deepak Chawla",   "Sales",     "Business Developer",   47000,  330, "Inactive"),
    ("Tanvi Desai",     "IT",        "Data Analyst",         58000,  760, "Inactive"),
]

# Present is most common, as in a real office
STATUS_WEIGHTS = [("Present", 86), ("Absent", 7), ("Leave", 7)]
DAYS_OF_ATTENDANCE = 30


def clear():
    deleted, _ = Employee.objects.filter(email__endswith=DEMO_DOMAIN).delete()
    print(f"Removed {deleted} sample records (employees and their attendance).")


def seed():
    random.seed(42)                      # same data every time
    today = timezone.localdate()

    created_employees = 0
    created_records = 0

    for index, (name, department, designation, salary, days_ago, status) in enumerate(PEOPLE):

        email = name.lower().replace(" ", ".") + DEMO_DOMAIN

        employee, created = Employee.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "phone": f"9{random.randint(100000000, 999999999)}",
                "department": department,
                "designation": designation,
                "salary": Decimal(salary),
                "joining_date": today - timedelta(days=days_ago),
                "status": status,
            },
        )

        created_employees += int(created)

        if status != "Active":
            continue

        for back in range(DAYS_OF_ATTENDANCE):
            day = today - timedelta(days=back)

            if day.weekday() >= 5 or day < employee.joining_date:
                continue

            choice = random.choices(
                [item[0] for item in STATUS_WEIGHTS],
                weights=[item[1] for item in STATUS_WEIGHTS],
            )[0]

            _, made = Attendance.objects.get_or_create(
                employee=employee, date=day, defaults={"status": choice}
            )

            created_records += int(made)

    print(f"Added {created_employees} sample employees and {created_records} attendance records.")
    print(f"Total employees now: {Employee.objects.count()}")


if __name__ == "__main__":
    if "--clear" in sys.argv:
        clear()
    else:
        seed()