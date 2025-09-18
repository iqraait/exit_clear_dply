from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from .models import Department,Employee,Question, EmployeeQuestionResponse, DepartmentEmployeeComment
from .serializers import HRRegisterSerializer, DepartmentSerializer,EmployeeSerializer,QuestionSerializer, EmployeeQuestionResponseSerializer, DepartmentEmployeeCommentSerializer,EmployeeCreateSerializer
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework import serializers # Import serializers for ValidationError


class HRRegisterViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = HRRegisterSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def login(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if user and hasattr(user, "hr_profile"):
            token, _ = Token.objects.get_or_create(user=user)
            return Response({"token": token.key, "role": "HR"})
        return Response({"error": "Invalid credentials"}, status=400)


class DepartmentViewSet(ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if not hasattr(request.user, "hr_profile"):
            return Response({"error": "Only HR can create departments"}, status=403)
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["post"], authentication_classes=[], permission_classes=[AllowAny])
    def set_password(self, request):
     email = request.data.get("email")
     password = request.data.get("password")

     try:
        dept = Department.objects.get(email=email)
        dept.password = password
        dept.save()
        return Response({"message": "Password set successfully"}, status=status.HTTP_200_OK)
     except Department.DoesNotExist:
        return Response({"error": "Department not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"], authentication_classes=[], permission_classes=[AllowAny])
    def login(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        try:
            dept = Department.objects.get(email=email, password=password)
            user, created = User.objects.get_or_create(username=f"dept_{dept.id}")
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
            "token": token.key,
            "role": "Department",
            "department": dept.name,
            "department_id": dept.id
        })
        except Department.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=400)


class EmployeeViewSet(ModelViewSet):
    queryset = Employee.objects.all().order_by("-created_at")
    serializer_class = EmployeeSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action in ["list", "retrieve", "responses"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        dept_id = self.request.query_params.get("department")
        if dept_id:
            queryset = queryset.filter(assigned_departments__id=dept_id)
        return queryset
    
    def perform_create(self, serializer):
        employee = serializer.save()
        employee_department_name = employee.employee_department

        for dept in employee.assigned_departments.all():
            # Get regular questions for the assigned department
            regular_questions = dept.questions.filter(is_concerned_question=False)
            for q in regular_questions:
                EmployeeQuestionResponse.objects.get_or_create(
                    employee=employee, department=dept, question=q
                )
            
            # If exit staff's department is the same as the assigned department,
            # also add "concerned department" questions for this department.
            if employee_department_name == dept.name:
                concerned_questions = dept.questions.filter(is_concerned_question=True)
                for q in concerned_questions:
                    EmployeeQuestionResponse.objects.get_or_create(
                        employee=employee, department=dept, question=q
                    )

            # Create an empty comment entry for each assigned department
            DepartmentEmployeeComment.objects.get_or_create(
                employee=employee, department=dept, defaults={'comment_text': '', 'department_head_id': ''}
            )
        employee.update_status()

    @action(detail=False, methods=["get"])
    def summary(self, request):
        total = Employee.objects.count()
        pending = Employee.objects.filter(status="pending").count()
        inprogress = Employee.objects.filter(status="inprogress").count()
        done = Employee.objects.filter(status="done").count()
        return Response({
            "total": total,
            "pending": pending,
            "inprogress": inprogress,
            "done": done
        })
    
    @action(detail=True, methods=["get"])
    def responses(self, request, pk=None):
       employee = self.get_object()
       data = []
       all_done = True
       any_done = False

       for dept in employee.assigned_departments.all():
        dept_data = {"department_id": dept.id, "department": dept.name, "questions": []}
        
        # Determine which questions to fetch for this department
        # This logic mirrors the perform_create to ensure consistency
        questions_for_this_dept = Question.objects.none()
        
        # Always add regular questions for the assigned department
        questions_for_this_dept |= dept.questions.filter(is_concerned_question=False)
        
        # If employee's department matches the current assigned department, add concerned questions
        if employee.employee_department == dept.name:
            questions_for_this_dept |= dept.questions.filter(is_concerned_question=True)

        responses = EmployeeQuestionResponse.objects.filter(
            employee=employee, department=dept, question__in=questions_for_this_dept
        ).select_related("question").order_by('question__is_concerned_question', 'question__id') # Order for consistent display

        dept_done = True
        any_answered = False
        for resp in responses:
            dept_data["questions"].append({
                "id": resp.question.id,
                "text": resp.question.text,
                "is_checked": resp.is_checked,
                "is_concerned_question": resp.question.is_concerned_question, # NEW: Add this field
            })
            if resp.is_checked:
                any_answered = True
            else:
                dept_done = False

        # Department status logic
        if dept_done and responses.exists():
            dept_status = "done"
        elif any_answered:
            dept_status = "inprogress"
        else:
            dept_status = "pending"

        dept_data["status"] = dept_status

        # Fetch department specific comment and Department Head ID
        dept_comment_obj = DepartmentEmployeeComment.objects.filter(employee=employee, department=dept).first()
        dept_data["comment"] = dept_comment_obj.comment_text if dept_comment_obj else ""
        dept_data["department_head_id"] = dept_comment_obj.department_head_id if dept_comment_obj else "" # NEW: Add this field

        data.append(dept_data)

        # track overall
        if dept_status == "done":
            any_done = True
        else:
            all_done = False

       if all_done and data:
        overall_status = "done"
       elif any_done:
        overall_status = "inprogress"
       else:
        overall_status = "pending"

       return Response({
        "employee": employee.employee_name,
        "overall_status": overall_status,
        "employee_department": employee.employee_department,
        "departments": data,
    })

    @action(detail=False, methods=["get"])
    def department_summary(self, request):
        dept_id = request.query_params.get("department")
        if not dept_id:
            return Response({"error": "Department id required"}, status=400)

        employees = Employee.objects.filter(assigned_departments=dept_id)
        total = employees.count()
        done = 0

        for emp in employees:
            # Re-evaluate the questions for each employee based on their department
            questions_for_this_dept = Question.objects.none()
            assigned_dept_instance = Department.objects.get(id=dept_id)
            
            questions_for_this_dept |= assigned_dept_instance.questions.filter(is_concerned_question=False)
            if emp.employee_department == assigned_dept_instance.name:
                questions_for_this_dept |= assigned_dept_instance.questions.filter(is_concerned_question=True)

            responses = EmployeeQuestionResponse.objects.filter(
                employee=emp, department_id=dept_id, question__in=questions_for_this_dept
            )
            if responses.exists() and all(r.is_checked for r in responses):
                done += 1

        pending = total - done
        return Response({"total": total, "done": done, "pending": pending})

    # MODIFIED: Override get_queryset for employee creation to filter assignable departments
    def get_serializer_class(self):
        if self.action == 'create':
            return EmployeeCreateSerializer # We'll define this new serializer below
        return self.serializer_class

class QuestionViewSet(ModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        question = serializer.save()
        # Find all employees currently assigned to this department
        employees_assigned_to_this_dept = Employee.objects.filter(assigned_departments=question.department)

        for emp in employees_assigned_to_this_dept:
            # Only create a response if it's a regular question OR
            # if it's a concerned question AND the employee's department matches
            if not question.is_concerned_question or (question.is_concerned_question and emp.employee_department == question.department.name):
                EmployeeQuestionResponse.objects.get_or_create(
                    employee=emp, department=question.department, question=question
                )
                # Ensure comment entry exists for this new department-employee pairing
                DepartmentEmployeeComment.objects.get_or_create(
                    employee=emp, department=question.department, defaults={'comment_text': '', 'department_head_id': ''}
                )
        # Update status for all affected employees
        for emp in employees_assigned_to_this_dept:
            emp.update_status()


    @action(detail=False, methods=["get"])
    def for_employee(self, request):
        dept_id = request.query_params.get("department")
        emp_id = request.query_params.get("employee")
        if not dept_id or not emp_id:
            return Response({"error": "department and employee required"}, status=400)

        employee = Employee.objects.get(id=emp_id)
        department = Department.objects.get(id=dept_id)

        # Filter questions based on the new logic
        questions_to_display = Question.objects.none()
        questions_to_display |= department.questions.filter(is_concerned_question=False) # Always add regular questions

        if employee.employee_department == department.name:
            questions_to_display |= department.questions.filter(is_concerned_question=True) # Add concerned questions if matching

        results = []
        for q in questions_to_display.order_by('is_concerned_question', 'id'): # Order for consistent display
            resp, _ = EmployeeQuestionResponse.objects.get_or_create(
                employee=employee,
                department=department,
                question=q
            )
            results.append({
                "id": q.id,
                "text": q.text,
                "response_id": resp.id,
                "is_checked": resp.is_checked,
                "is_concerned_question": q.is_concerned_question, # NEW: Include this
            })
        
        # Get the department's comment and head ID for this employee
        dept_comment_obj = DepartmentEmployeeComment.objects.filter(employee=employee, department=department).first()
        comment_data = {
            "comment_text": dept_comment_obj.comment_text if dept_comment_obj else "",
            "department_head_id": dept_comment_obj.department_head_id if dept_comment_obj else "",
            "comment_id": dept_comment_obj.id if dept_comment_obj else None,
        }

        return Response({"questions": results, "department_comment_data": comment_data})


class EmployeeQuestionResponseViewSet(ModelViewSet):
    queryset = EmployeeQuestionResponse.objects.all()
    serializer_class = EmployeeQuestionResponseSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        emp_id = self.request.query_params.get("employee")
        dept_id = self.request.query_params.get("department")
        if emp_id:
            qs = qs.filter(employee_id=emp_id)
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        return qs
    
    def perform_update(self, serializer):
        instance = serializer.save()
        instance.employee.update_status()


class DepartmentEmployeeCommentViewSet(ModelViewSet):
    queryset = DepartmentEmployeeComment.objects.all()
    serializer_class = DepartmentEmployeeCommentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get('employee')
        department_id = self.request.query_params.get('department')
        
        if hasattr(self.request.user, 'hr_profile'):
            pass
        elif self.request.user.username.startswith('dept_'):
            logged_in_dept_id = self.request.user.username.split('_')[1]
            qs = qs.filter(department_id=logged_in_dept_id)

        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if department_id:
            qs = qs.filter(department_id=department_id)
        return qs

    def perform_create(self, serializer):
        employee_id = self.request.data.get('employee')
        department_id = self.request.data.get('department')
        comment_text = self.request.data.get('comment_text')
        department_head_id = self.request.data.get('department_head_id', '') # NEW: Get department_head_id

        if not employee_id or not department_id:
            raise serializers.ValidationError({"detail": "Employee and Department IDs are required."})
        
        if not self.request.user.username.startswith('dept_'):
            raise serializers.ValidationError({"detail": "Only department users can create comments."})
        
        logged_in_dept_id = int(self.request.user.username.split('_')[1])
        if logged_in_dept_id != int(department_id):
            raise serializers.ValidationError({"detail": "You can only add comments for your own department."})

        employee = Employee.objects.filter(id=employee_id, assigned_departments__id=department_id).first()
        if not employee:
            raise serializers.ValidationError({"detail": "Department is not assigned to this employee."})
            
        comment_instance, created = DepartmentEmployeeComment.objects.get_or_create(
            employee_id=employee_id,
            department_id=department_id,
            defaults={'comment_text': comment_text, 'department_head_id': department_head_id} # NEW: Set department_head_id
        )
        if not created:
            comment_instance.comment_text = comment_text
            comment_instance.department_head_id = department_head_id # NEW: Update department_head_id
            comment_instance.save()
            
        serializer.instance = comment_instance

    def perform_update(self, serializer):
        comment_instance = self.get_object()
        
        if not self.request.user.username.startswith('dept_'):
            raise serializers.ValidationError({"detail": "Only department users can update comments."})
        
        logged_in_dept_id = int(self.request.user.username.split('_')[1])
        if logged_in_dept_id != comment_instance.department.id:
            raise serializers.ValidationError({"detail": "You can only update comments for your own department."})

        # Allow updating department_head_id here as well
        serializer.save(department_head_id=self.request.data.get('department_head_id', comment_instance.department_head_id))

























