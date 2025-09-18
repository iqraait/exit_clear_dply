from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HRRegisterViewSet, DepartmentViewSet,EmployeeViewSet,QuestionViewSet, EmployeeQuestionResponseViewSet,DepartmentEmployeeCommentViewSet

router = DefaultRouter()
router.register("hr", HRRegisterViewSet, basename="hr")
router.register("departments", DepartmentViewSet, basename="departments")
router.register("employees", EmployeeViewSet, basename="employees")
router.register(r"questions", QuestionViewSet, basename="question")
router.register(r"responses", EmployeeQuestionResponseViewSet, basename="response")
router.register(r"department-comments", DepartmentEmployeeCommentViewSet, basename="department-comment")


urlpatterns = [
    path("", include(router.urls)),
]

    