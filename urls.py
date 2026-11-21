from django.urls import path
from rest_framework.routers import DefaultRouter

from .auth_views import LoginView, LogoutView
from .views import (
    AttendanceViewSet, EmployeeViewSet, LeaveViewSet,
    PayrollViewSet, UserViewSet
)


router = DefaultRouter()

router.register('employees', EmployeeViewSet, basename='employee')
router.register('attendance', AttendanceViewSet, basename='attendance')
router.register('leaves', LeaveViewSet, basename='leave')
router.register('payroll', PayrollViewSet, basename='payroll')
router.register('users', UserViewSet, basename='users')


urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
] + router.urls