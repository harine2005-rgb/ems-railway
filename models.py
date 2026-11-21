from django.contrib.auth.models import User
from django.db import models


class Employee(models.Model):

    STATUS_CHOICES = [('Active', 'Active'), ('Inactive', 'Inactive')]

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    department = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    joining_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')

    # The login this employee uses (optional). permissions.get_role()
    # looks for this through the name "employee_profile".
    user = models.OneToOneField(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='employee_profile'
    )

    def __str__(self):
        return self.name


class Attendance(models.Model):

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='attendance_records'
    )
    date = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=[('Present', 'Present'), ('Absent', 'Absent'), ('Leave', 'Leave')],
        default='Present'
    )
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.status}"


class LeaveRequest(models.Model):

    TYPE_CHOICES = [
        ('Casual', 'Casual'), ('Sick', 'Sick'),
        ('Paid', 'Paid'), ('Unpaid', 'Unpaid'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected'),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='leave_requests'
    )
    leave_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='Casual')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    remarks = models.CharField(max_length=200, blank=True)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f"{self.employee.name} {self.start_date} to {self.end_date} ({self.status})"


class Payroll(models.Model):

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='payslips'
    )
    month = models.CharField(max_length=7)          # "2026-10"
    base_salary = models.DecimalField(max_digits=10, decimal_places=2)
    working_days = models.PositiveSmallIntegerField(default=0)
    present_days = models.PositiveSmallIntegerField(default=0)
    absent_days = models.PositiveSmallIntegerField(default=0)
    leave_days = models.PositiveSmallIntegerField(default=0)
    unpaid_leave_days = models.PositiveSmallIntegerField(default=0)
    deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'month')

    def __str__(self):
        return f"{self.employee.name} - {self.month}"