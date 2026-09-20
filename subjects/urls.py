from rest_framework.routers import DefaultRouter

from .views import SkillViewSet, SubjectViewSet

app_name = "subjects"

router = DefaultRouter()
router.register("subjects", SubjectViewSet, basename="subject")
router.register("skills", SkillViewSet, basename="skill")

urlpatterns = router.urls
