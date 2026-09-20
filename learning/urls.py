from rest_framework.routers import DefaultRouter

from .views import (
    DiagnosticViewSet, ProgressRecordViewSet, StudyActivityViewSet, StudyPlanViewSet,
    TeacherFeedbackViewSet,
)

app_name = "learning"

router = DefaultRouter()
router.register("diagnostics", DiagnosticViewSet, basename="diagnostic")
router.register("study-plans", StudyPlanViewSet, basename="study-plan")
router.register("activities", StudyActivityViewSet, basename="activity")
router.register("progress", ProgressRecordViewSet, basename="progress")
router.register("teacher-feedback", TeacherFeedbackViewSet, basename="teacher-feedback")

urlpatterns = router.urls
