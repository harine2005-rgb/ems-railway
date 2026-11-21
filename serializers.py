import re

from rest_framework import serializers

from .models import Attendance, Employee, LeaveRequest, Payroll
from .utils import weekdays_between


class EmployeeSerializer(serializers.ModelSerializer):

    has_login = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'name', 'email', 'phone', 'department', 'designation',
            'salary', 'joining_date', 'status', 'has_login'
        ]

    def get_has_login(self, obj):
        return obj.user_id is not None

    def validate_phone(self, value):
        if not re.fullmatch(r'\d{10}', value):
            raise serializers.ValidationError('Phone number must contain exactly 10 digits.')
        return value

    def validate_salary(self, value):
        if value <= 0:
            raise serializers.ValidationError('Salary must be greater than zero.')
        return value


class AttendanceSerializer(serializers.ModelSerializer):

    employee_name = serializers.CharField(source='employee.name', read_only=True)

    class Meta:
        model = Attendance
        fields = '__all__'

    def validate(self, attrs):
        check_in = attrs.get('check_in', getattr(self.instance, 'check_in', None))
        check_out = attrs.get('check_out', getattr(self.instance, 'check_out', None))

        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError('Check out time must be after check in time.')

        return attrs


class LeaveRequestSerializer(serializers.ModelSerializer):

    employee_name = serializers.CharField(source='employee.name', read_only=True)
    days = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_name', 'leave_type', 'start_date',
            'end_date', 'days', 'reason', 'status', 'remarks', 'created_at'
        ]
        read_only_fields = ['employee', 'status', 'remarks', 'created_at']

    def get_days(self, obj):
        return weekdays_between(obj.start_date, obj.end_date)

    def validate(self, attrs):
        start, end = attrs['start_date'], attrs['end_date']

        if end < start:
            raise serializers.ValidationError('The end date cannot be before the start date.')

        if (end - start).days > 365:
            raise serializers.ValidationError('A leave request cannot be longer than one year.')

        if weekdays_between(start, end) == 0:
            raise serializers.ValidationError('Leave must include at least one working day (Mon-Fri).')

        overlap = LeaveRequest.objects.filter(
            employee=self.context['employee'],
            status__in=['Pending', 'Approved'],
            start_date__lte=end,
            end_date__gte=start
        ).exists()

        if overlap:
            raise serializers.ValidationError(
                'You already have a pending or approved leave in these dates.'
            )

        return attrs


class PayrollSerializer(serializers.ModelSerializer):

    employee_name = serializers.CharField(source='employee.name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    employee_designation = serializers.CharField(source='employee.designation', read_only=True)
    employee_department = serializers.CharField(source='employee.department', read_only=True)

    class Meta:
        model = Payroll
        fields = '__all__'