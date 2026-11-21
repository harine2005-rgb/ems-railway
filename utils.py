import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .models import Attendance, LeaveRequest

TWO_PLACES = Decimal('0.01')


def weekdays_between(start, end):
    """Number of Monday-Friday days from start to end (inclusive)."""

    if end < start:
        return 0

    total = (end - start).days + 1

    return sum(
        1 for i in range(total)
        if (start + timedelta(days=i)).weekday() < 5
    )


def month_bounds(month):
    """'2026-11' -> (date(2026, 11, 1), date(2026, 11, 30))"""

    year, number = map(int, month.split('-'))

    return (
        date(year, number, 1),
        date(year, number, calendar.monthrange(year, number)[1])
    )


def mark_leave_attendance(leave):
    """When a leave is approved, mark those working days as 'Leave'."""

    current = leave.start_date
    end = min(leave.end_date, leave.start_date + timedelta(days=365))

    while current <= end:

        if current.weekday() < 5:

            record, created = Attendance.objects.get_or_create(
                employee=leave.employee,
                date=current,
                defaults={'status': 'Leave'}
            )

            # Never overwrite a day the employee actually worked
            if not created and not record.check_in and record.status != 'Leave':
                record.status = 'Leave'
                record.save(update_fields=['status'])

        current += timedelta(days=1)


def calculate_payroll(employee, month):
    """
    Salary rule:
      per-day pay = monthly salary / working days (Mon-Fri)
      deduction   = per-day pay x (absent days + approved unpaid-leave days)
      net pay     = salary - deduction
    """

    first, last = month_bounds(month)

    working_days = weekdays_between(first, last)

    records = Attendance.objects.filter(
        employee=employee,
        date__range=(first, last)
    )

    present = records.filter(status='Present').count()
    absent = records.filter(status='Absent').count()
    leave = records.filter(status='Leave').count()

    unpaid = 0

    unpaid_leaves = LeaveRequest.objects.filter(
        employee=employee,
        status='Approved',
        leave_type='Unpaid',
        start_date__lte=last,
        end_date__gte=first
    )

    for item in unpaid_leaves:
        unpaid += weekdays_between(
            max(item.start_date, first),
            min(item.end_date, last)
        )

    base = Decimal(employee.salary)

    per_day = base / working_days if working_days else Decimal('0')

    deduction = (per_day * (absent + unpaid)).quantize(TWO_PLACES, ROUND_HALF_UP)
    deduction = min(deduction, base)

    return {
        'base_salary': base,
        'working_days': working_days,
        'present_days': present,
        'absent_days': absent,
        'leave_days': leave,
        'unpaid_leave_days': unpaid,
        'deduction': deduction,
        'net_pay': (base - deduction).quantize(TWO_PLACES),
    }