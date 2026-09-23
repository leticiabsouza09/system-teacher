from rest_framework.routers import DefaultRouter

from .views import ClassroomViewSet

router = DefaultRouter()
router.register("classrooms", ClassroomViewSet, basename="classroom")

urlpatterns = router.urls
