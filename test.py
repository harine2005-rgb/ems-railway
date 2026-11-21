from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Attendance, Employee, LeaveRequest, Payroll
from .utils import weekdays_between


def next_weekday(start):
    while start.weekday() >= 5:
        start += timedelta(days=1)
    return start


class BaseCase(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', password='admin123')
        self.hr = User.objects.create_user('hruser', password='hrpass123')
        self.hr.groups.add(Group.objects.create(name='HR'))

        self.user_a = User.objects.create_user('amy', password='amypass1')
        self.user_b = User.objects.create_user('bob', password='bobpass1')

        self.emp_a = self.make_employee('Amy', 'amy@x.com', self.user_a)
        self.emp_b = self.make_employee('Bob', 'bob@x.com', self.user_b)

    def make_employee(self, name, email, user=None, salary='22000'):
        return Employee.objects.create(
            name=name, email=email, phone='9999999999', department='IT',
            designation='Dev', salary=Decimal(salary),
            joining_date=date(2025, 1, 1), user=user
        )

    def as_user(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')


class LoginAndRoleTests(BaseCase):

    def login(self, username, password):
        self.client.credentials()
        return self.client.post('/api/login/', {'username': username, 'password': password}, format='json')

    def test_roles_returned(self):
        self.assertEqual(self.login('admin', 'admin123').data['role'], 'Admin')
        self.assertEqual(self.login('hruser', 'hrpass123').data['role'], 'HR')
        response = self.login('amy', 'amypass1')
        self.assertEqual(response.data['role'], 'Employee')
        self.assertEqual(response.data['employee_id'], self.emp_a.id)

    def test_bad_password_and_no_role(self):
        self.assertEqual(self.login('admin', 'wrong').status_code, 401)
        User.objects.create_user('ghost', password='ghostpw1')
        self.assertEqual(self.login('ghost', 'ghostpw1').status_code, 403)

    def test_stale_token_does_not_block_login(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token invalidtoken')
        response = self.client.post('/api/login/', {'username': 'admin', 'password': 'admin123'}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_employee_sees_only_own_data(self):
        self.as_user(self.user_a)
        rows = self.client.get('/api/employees/').data
        self.assertEqual([r['name'] for r in rows], ['Amy'])

    def test_employee_cannot_write_employees(self):
        self.as_user(self.user_a)
        self.assertEqual(self.client.post('/api/employees/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/employees/{self.emp_b.id}/').status_code, 403)

    def test_hr_can_manage_employees_but_not_users(self):
        self.as_user(self.hr)
        self.assertEqual(len(self.client.get('/api/employees/').data), 2)
        self.assertEqual(self.client.get('/api/users/').status_code, 403)

    def test_no_token_is_rejected(self):
        self.client.credentials()
        self.assertEqual(self.client.get('/api/employees/').status_code, 401)

    def test_delete_employee_removes_login(self):
        self.as_user(self.admin)
        self.client.delete(f'/api/employees/{self.emp_a.id}/')
        self.assertFalse(User.objects.filter(username='amy').exists())


class UserManagementTests(BaseCase):

    def test_admin_creates_hr_and_employee_logins(self):
        self.as_user(self.admin)
        emp = self.make_employee('Cara', 'cara@x.com')

        response = self.client.post('/api/users/', {'username': 'hr2', 'password': 'secret12', 'role': 'HR'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], 'HR')

        response = self.client.post('/api/users/', {
            'username': 'cara', 'password': 'secret12', 'role': 'Employee', 'employee': emp.id
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['role'], 'Employee')

    def test_validation(self):
        self.as_user(self.admin)
        self.assertEqual(self.client.post('/api/users/', {'username': 'amy', 'password': 'secret12', 'role': 'HR'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/users/', {'username': 'z1', 'password': 'secret12', 'role': 'Employee'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/users/', {
            'username': 'z2', 'password': 'secret12', 'role': 'Employee', 'employee': self.emp_a.id
        }, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/users/', {'username': 'z3', 'password': '123', 'role': 'HR'}, format='json').status_code, 400)

    def test_cannot_delete_admin(self):
        self.as_user(self.admin)
        self.assertEqual(self.client.delete(f'/api/users/{self.admin.id}/').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/users/{self.user_b.id}/').status_code, 204)


class AttendanceTests(BaseCase):

    def test_check_in_and_out(self):
        self.as_user(self.user_a)
        response = self.client.post('/api/attendance/check-in/', {}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(response.data['check_in'])
        self.assertEqual(self.client.post('/api/attendance/check-in/', {}, format='json').status_code, 400)

        response = self.client.post('/api/attendance/check-out/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data['check_out'])
        self.assertEqual(self.client.post('/api/attendance/check-out/', {}, format='json').status_code, 400)

    def test_check_out_needs_check_in(self):
        self.as_user(self.user_a)
        self.assertEqual(self.client.post('/api/attendance/check-out/', {}, format='json').status_code, 400)

    def test_employee_sees_only_own_attendance_and_cannot_edit(self):
        today = timezone.localdate()
        Attendance.objects.create(employee=self.emp_a, date=today, status='Present')
        record_b = Attendance.objects.create(employee=self.emp_b, date=today, status='Present')

        self.as_user(self.user_a)
        self.assertEqual(len(self.client.get('/api/attendance/').data), 1)
        self.assertEqual(self.client.patch(f'/api/attendance/{record_b.id}/', {'status': 'Absent'}, format='json').status_code, 403)

    def test_hr_can_edit_attendance_times(self):
        record = Attendance.objects.create(employee=self.emp_a, date=timezone.localdate(), status='Present')
        self.as_user(self.hr)
        response = self.client.patch(f'/api/attendance/{record.id}/', {
            'status': 'Present', 'check_in': '09:30:00', 'check_out': '18:00:00'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['check_in'], '09:30:00')

    def test_duplicate_attendance_rejected(self):
        self.as_user(self.hr)
        body = {'employee': self.emp_a.id, 'date': '2026-11-02', 'status': 'Present'}
        self.assertEqual(self.client.post('/api/attendance/', body, format='json').status_code, 201)
        self.assertEqual(self.client.post('/api/attendance/', body, format='json').status_code, 400)


class LeaveTests(BaseCase):

    def apply(self, start, end, leave_type='Casual'):
        return self.client.post('/api/leaves/', {
            'leave_type': leave_type, 'start_date': str(start), 'end_date': str(end), 'reason': 'trip'
        }, format='json')

    def test_apply_approve_marks_attendance(self):
        start = next_weekday(date.today() + timedelta(days=3))
        end = start + timedelta(days=2)

        self.as_user(self.user_a)
        response = self.apply(start, end)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'Pending')
        leave_id = response.data['id']

        self.assertEqual(self.client.post(f'/api/leaves/{leave_id}/approve/').status_code, 403)

        self.as_user(self.hr)
        self.assertEqual(self.client.post(f'/api/leaves/{leave_id}/approve/', {'remarks': 'ok'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/leaves/{leave_id}/reject/').status_code, 400)

        expected = weekdays_between(start, end)
        self.assertEqual(Attendance.objects.filter(employee=self.emp_a, status='Leave').count(), expected)

    def test_overlap_and_bad_dates(self):
        start = next_weekday(date.today() + timedelta(days=10))
        self.as_user(self.user_a)
        self.assertEqual(self.apply(start, start).status_code, 201)
        self.assertEqual(self.apply(start, start + timedelta(days=1)).status_code, 400)
        self.assertEqual(self.apply(start + timedelta(days=5), start + timedelta(days=2)).status_code, 400)

    def test_employee_sees_and_cancels_only_own(self):
        start = next_weekday(date.today() + timedelta(days=20))
        self.as_user(self.user_b)
        other = self.apply(start, start).data['id']

        self.as_user(self.user_a)
        mine = self.apply(start, start).data['id']
        self.assertEqual(len(self.client.get('/api/leaves/').data), 1)
        self.assertEqual(self.client.delete(f'/api/leaves/{other}/').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/leaves/{mine}/').status_code, 204)

    def test_cannot_cancel_after_review(self):
        start = next_weekday(date.today() + timedelta(days=30))
        self.as_user(self.user_a)
        leave_id = self.apply(start, start).data['id']
        self.as_user(self.hr)
        self.client.post(f'/api/leaves/{leave_id}/reject/')
        self.as_user(self.user_a)
        self.assertEqual(self.client.delete(f'/api/leaves/{leave_id}/').status_code, 400)

    def test_approval_does_not_overwrite_worked_day(self):
        start = next_weekday(date.today() + timedelta(days=3))
        Attendance.objects.create(employee=self.emp_a, date=start, status='Present', check_in='09:00:00')
        leave = LeaveRequest.objects.create(employee=self.emp_a, leave_type='Casual', start_date=start, end_date=start)
        self.as_user(self.hr)
        self.client.post(f'/api/leaves/{leave.id}/approve/')
        self.assertEqual(Attendance.objects.get(employee=self.emp_a, date=start).status, 'Present')


class PayrollTests(BaseCase):

    MONTH = '2026-10'

    def test_generate_and_deduct(self):
        first, last = date(2026, 10, 1), date(2026, 10, 31)
        working = weekdays_between(first, last)

        Attendance.objects.create(employee=self.emp_a, date=date(2026, 10, 1), status='Absent')
        Attendance.objects.create(employee=self.emp_a, date=date(2026, 10, 2), status='Absent')
        Attendance.objects.create(employee=self.emp_a, date=date(2026, 10, 5), status='Present')
        Attendance.objects.create(employee=self.emp_a, date=date(2026, 10, 6), status='Leave')

        self.as_user(self.hr)
        response = self.client.post('/api/payroll/generate/', {'month': self.MONTH}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)

        slip = Payroll.objects.get(employee=self.emp_a, month=self.MONTH)
        per_day = Decimal('22000') / working
        expected = (per_day * 2).quantize(Decimal('0.01'))
        self.assertEqual(slip.working_days, working)
        self.assertEqual((slip.present_days, slip.absent_days, slip.leave_days), (1, 2, 1))
        self.assertEqual(slip.deduction, expected)
        self.assertEqual(slip.net_pay, Decimal('22000') - expected)

        clean = Payroll.objects.get(employee=self.emp_b, month=self.MONTH)
        self.assertEqual(clean.net_pay, Decimal('22000.00'))

    def test_unpaid_leave_is_deducted(self):
        LeaveRequest.objects.create(
            employee=self.emp_a, leave_type='Unpaid', status='Approved',
            start_date=date(2026, 10, 12), end_date=date(2026, 10, 13)
        )
        self.as_user(self.hr)
        self.client.post('/api/payroll/generate/', {'month': self.MONTH}, format='json')
        slip = Payroll.objects.get(employee=self.emp_a, month=self.MONTH)
        self.assertEqual(slip.unpaid_leave_days, 2)
        self.assertGreater(slip.deduction, 0)

    def test_regenerate_updates_instead_of_duplicating(self):
        self.as_user(self.hr)
        self.client.post('/api/payroll/generate/', {'month': self.MONTH}, format='json')
        self.client.post('/api/payroll/generate/', {'month': self.MONTH}, format='json')
        self.assertEqual(Payroll.objects.filter(month=self.MONTH).count(), 2)

    def test_validation(self):
        self.as_user(self.hr)
        self.assertEqual(self.client.post('/api/payroll/generate/', {'month': 'bad'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/payroll/generate/', {'month': '2099-01'}, format='json').status_code, 400)

    def test_employee_permissions(self):
        self.as_user(self.hr)
        self.client.post('/api/payroll/generate/', {'month': self.MONTH}, format='json')

        self.as_user(self.user_a)
        rows = self.client.get('/api/payroll/').data
        self.assertEqual([r['employee_name'] for r in rows], ['Amy'])
        self.assertEqual(self.client.post('/api/payroll/generate/', {'month': self.MONTH}, format='json').status_code, 403)

    def test_inactive_and_future_joiners_skipped(self):
        self.emp_b.status = 'Inactive'
        self.emp_b.save()
        self.make_employee('Late', 'late@x.com').joining_date = date(2027, 1, 1)
        late = Employee.objects.get(email='late@x.com')
        late.joining_date = date(2027, 1, 1)
        late.save()

        self.as_user(self.hr)
        response = self.client.post('/api/payroll/generate/', {'month': self.MONTH}, format='json')
        self.assertEqual(response.data['count'], 1)