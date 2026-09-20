from rest_framework.routers import DefaultRouter

from .views import StudentViewSet

app_name = "students"

router = DefaultRouter()
router.register("students", StudentViewSet, basename="student")

urlpatterns = router.urls
