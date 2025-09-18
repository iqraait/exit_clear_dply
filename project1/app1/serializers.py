from rest_framework import serializers
from django.contrib.auth.models import User
from .models import HRProfile, Department,Employee,Question, EmployeeQuestionResponse, DepartmentEmployeeComment


class HRRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            is_staff=True  # HR is considered staff
        )
        HRProfile.objects.create(user=user)
        return user


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "email", "password", "is_assigned_department", "created_at"] # NEW: Added is_assigned_department
        extra_kwargs = {
            "password": {"write_only": True}
        }

# NEW: Serializer for DepartmentEmployeeComment
class DepartmentEmployeeCommentSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = DepartmentEmployeeComment
        fields = ["id", "employee", "department", "department_name", "comment_text", "department_head_id", "created_at", "updated_at"]
        read_only_fields = []


class EmployeeSerializer(serializers.ModelSerializer):
    assigned_departments = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), many=True
    )
    department_comments = DepartmentEmployeeCommentSerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_name",
            "employee_id",
            "employee_department",
            "designation",
            "status",
            "progress",
            "last_work_date",
            "type_of_separation",
            "assigned_departments",
            "created_at",
            "department_comments",
        ]
  
# NEW: EmployeeCreateSerializer to filter assigned_departments queryset
class EmployeeCreateSerializer(serializers.ModelSerializer):
    assigned_departments = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_assigned_department=True), # Filter to only show assignable departments
        many=True,
        required=False # Allow no departments to be assigned initially
    )
    department_comments = DepartmentEmployeeCommentSerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_name",
            "employee_id",
            "employee_department",
            "designation",
            "status",
            "progress",
            "last_work_date",
            "type_of_separation",
            "assigned_departments",
            "created_at",
            "department_comments",
        ]


class QuestionSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Question
        fields = ["id", "department", "department_name", "text", "is_concerned_question"] # NEW: Added is_concerned_question


class EmployeeQuestionResponseSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text", read_only=True)

    class Meta:
        model = EmployeeQuestionResponse
        fields = ["id", "employee", "department", "question", "question_text", "is_checked"]