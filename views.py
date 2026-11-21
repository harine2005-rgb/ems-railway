import re

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Attendance, Employee, LeaveRequest, Payroll
from .permissions import HasRole, IsAdminRole, IsStaffRole, get_role
from .serializers import (
    AttendanceSerializer, EmployeeSerializer,
    LeaveRequestSerializer, PayrollSerializer
)
from .utils import calculate_payroll, mark_leave_attendance, month_bounds


def own_employee(user):
    """The Employee record linked to this login, or None."""
    return getattr(user, 'employee_profile', None)


def only_own_rows(queryset, user):
    """Employees see only their own rows. Admin and HR see everything."""
    if get_role(user) == 'Employee':
        return queryset.filter(employee__user=user)
    return queryset


def error(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'message': message}, status=code)


# ===================================
# EMPLOYEES
# ===================================

class EmployeeViewSet(viewsets.ModelViewSet):

    serializer_class = EmployeeSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [HasRole()]
        return [IsStaffRole()]

    def get_queryset(self):
        queryset = Employee.objects.all().order_by('id')

        if get_role(self.request.user) == 'Employee':
            queryset = queryset.filter(user=self.request.user)

        return queryset

    def perform_destroy(self, instance):
        login = instance.user

        with transaction.atomic():
            instance.delete()

            # Deleting an employee also removes their login (never an admin)
            if login and not (login.is_staff or login.is_superuser):
                login.delete()


# ===================================
# ATTENDANCE
# ===================================

class AttendanceViewSet(viewsets.ModelViewSet):

    serializer_class = AttendanceSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'check_in', 'check_out'):
            return [HasRole()]
        return [IsStaffRole()]

    def get_queryset(self):
        queryset = Attendance.objects.select_related('employee').order_by('-date', '-id')
        return only_own_rows(queryset, self.request.user)

    @action(detail=False, methods=['post'], url_path='check-in')
    def check_in(self, request):
        employee = own_employee(request.user)

        if employee is None:
            return error('Only employees can check in.')

        now = timezone.localtime().time().replace(microsecond=0)

        record, created = Attendance.objects.get_or_create(
            employee=employee,
            date=timezone.localdate(),
            defaults={'status': 'Present', 'check_in': now}
        )

        if not created:
            if record.status == 'Leave':
                return error('You are on approved leave today.')

            if record.check_in:
                return error('You have already checked in today.')

            record.status = 'Present'
            record.check_in = now
            record.save()

        return Response(
            AttendanceSerializer(record).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], url_path='check-out')
    def check_out(self, request):
        employee = own_employee(request.user)

        if employee is None:
            return error('Only employees can check out.')

        record = Attendance.objects.filter(
            employee=employee, date=timezone.localdate()
        ).first()

        if record is None or not record.check_in:
            return error('You have not checked in today.')

        if record.check_out:
            return error('You have already checked out today.')

        record.check_out = timezone.localtime().time().replace(microsecond=0)
        record.save()

        return Response(AttendanceSerializer(record).data)


# ===================================
# LEAVE
# ===================================

class LeaveViewSet(viewsets.ModelViewSet):

    serializer_class = LeaveRequestSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('approve', 'reject'):
            return [IsStaffRole()]
        return [HasRole()]

    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related('employee')
        return only_own_rows(queryset, self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['employee'] = own_employee(self.request.user)
        return context

    def create(self, request, *args, **kwargs):
        if own_employee(request.user) is None:
            return error('Only employees can apply for leave.')
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(employee=own_employee(self.request.user))

    def destroy(self, request, *args, **kwargs):
        leave = self.get_object()

        if leave.status != 'Pending':
            return error('Only pending requests can be cancelled.')

        leave.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def review(self, request, new_status):
        leave = self.get_object()

        if leave.status != 'Pending':
            return error(f'This request is already {leave.status.lower()}.')

        with transaction.atomic():
            leave.status = new_status
            leave.remarks = str(request.data.get('remarks', '') or '')[:200]
            leave.reviewed_by = request.user
            leave.reviewed_at = timezone.now()
            leave.save()

            if new_status == 'Approved':
                mark_leave_attendance(leave)

        return Response(self.get_serializer(leave).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self.review(request, 'Approved')

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self.review(request, 'Rejected')


# ===================================
# PAYROLL
# ===================================

class PayrollViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = PayrollSerializer

    def get_permissions(self):
        if self.action == 'generate':
            return [IsStaffRole()]
        return [HasRole()]

    def get_queryset(self):
        queryset = Payroll.objects.select_related('employee').order_by('-month', 'employee__name')
        queryset = only_own_rows(queryset, self.request.user)

        month = self.request.query_params.get('month')
        if month:
            queryset = queryset.filter(month=month)

        return queryset

    @action(detail=False, methods=['post'])
    def generate(self, request):
        month = str(request.data.get('month', ''))

        if not re.fullmatch(r'(19|20)\d{2}-(0[1-9]|1[0-2])', month):
            return error('Month must look like 2026-10.')

        if month > timezone.localdate().strftime('%Y-%m'):
            return error('Payroll cannot be generated for a future month.')

        _, last_day = month_bounds(month)

        employees = Employee.objects.filter(status='Active', joining_date__lte=last_day)
        count = 0

        with transaction.atomic():
            for employee in employees:
                Payroll.objects.update_or_create(
                    employee=employee,
                    month=month,
                    defaults=calculate_payroll(employee, month)
                )
                count += 1

        return Response({
            'message': f'Payroll generated for {count} employee(s) for {month}.',
            'count': count
        })


# ===================================
# USERS AND ROLES (Admin only)
# ===================================

class UserViewSet(viewsets.ViewSet):

    permission_classes = [IsAdminRole]

    def user_data(self, user):
        employee = own_employee(user)

        return {
            'id': user.id,
            'username': user.username,
            'role': get_role(user) or 'None',
            'employee': employee.id if employee else None,
            'employee_name': employee.name if employee else None,
        }

    def list(self, request):
        users = User.objects.all().order_by('id')
        return Response([self.user_data(user) for user in users])

    def create(self, request):
        username = str(request.data.get('username') or '').strip()
        password = str(request.data.get('password') or '')
        role = request.data.get('role')
        employee_id = request.data.get('employee')

        if not username:
            return error('Username is required.')

        if User.objects.filter(username__iexact=username).exists():
            return error('This username is already taken.')

        if len(password) < 6:
            return error('Password must be at least 6 characters.')

        if role not in ('HR', 'Employee'):
            return error('Role must be HR or Employee.')

        employee = None

        if role == 'Employee' and not employee_id:
            return error('Choose the employee this login belongs to.')

        if employee_id:
            try:
                employee = Employee.objects.filter(pk=int(employee_id)).first()
            except (TypeError, ValueError):
                employee = None

            if employee is None:
                return error('Employee not found.')

            if employee.user_id is not None:
                return error('This employee already has a login.')

        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password)

            if role == 'HR':
                group, _ = Group.objects.get_or_create(name='HR')
                user.groups.add(group)

            if employee:
                employee.user = user
                employee.save(update_fields=['user'])

        return Response(self.user_data(user), status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        try:
            user = User.objects.filter(pk=int(pk)).first()
        except (TypeError, ValueError):
            user = None

        if user is None:
            return error('User not found.', status.HTTP_404_NOT_FOUND)

        if user.is_staff or user.is_superuser:
            return error('Admin accounts cannot be deleted here.')

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)