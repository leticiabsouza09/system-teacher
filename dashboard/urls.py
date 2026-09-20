from django.urls import path

from .views import StudentDashboardView, SystemMetricsView, TeacherDashboardView

app_name = "dashboard"

urlpatterns = [
    path("dashboard/student/", StudentDashboardView.as_view(), name="student-dashboard"),
    path("dashboard/teacher/", TeacherDashboardView.as_view(), name="teacher-dashboard"),
    path("dashboard/metrics/", SystemMetricsView.as_view(), name="system-metrics"),
]
