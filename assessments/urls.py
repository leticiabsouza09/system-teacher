from rest_framework.routers import DefaultRouter

from .views import AssessmentQuestionViewSet, AssessmentViewSet

app_name = "assessments"

router = DefaultRouter()
router.register("assessments", AssessmentViewSet, basename="assessment")
router.register("assessment-questions", AssessmentQuestionViewSet, basename="assessment-question")

urlpatterns = router.urls
