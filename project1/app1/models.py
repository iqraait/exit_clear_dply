from django.db import models
from django.contrib.auth.models import User

class HRProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="hr_profile")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"HR - {self.user.username}"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128, blank=True, null=True)  # Department sets later
    created_at = models.DateTimeField(auto_now_add=True)
    is_assigned_department = models.BooleanField(default=False) # NEW: Added field

    def __str__(self):
        return self.name
    

class Employee(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("inprogress", "In Progress"),
        ("done", "Done"),
    ]
    SEPARATION_CHOICES = [
        ("resignation", "Resignation"),
        ("termination", "Termination"),
        ("retirement", "Retirement"),
        ("other", "Other"),
    ]

    employee_name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50, unique=True)
    employee_department = models.CharField(max_length=100, blank=True, null=True)
    designation = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    progress = models.IntegerField(default=0)  # % progress
    last_work_date = models.DateField()
    type_of_separation = models.CharField(max_length=20, choices=SEPARATION_CHOICES)
    assigned_departments = models.ManyToManyField(Department, related_name="employees")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.employee_name
    
    def update_status(self):
        """Update HR global status based on department responses"""
        depts = self.assigned_departments.all()
        done_depts = []
        for dept in depts:
            # check if all questions of this dept are answered
            responses = self.responses.filter(department=dept)
            if responses.exists() and responses.filter(is_checked=False).count() == 0:
                done_depts.append(dept.id)

        if not done_depts:
            self.status = "pending"
        elif len(done_depts) < depts.count():
            self.status = "inprogress"
        else:
            self.status = "done"

        self.save()
    

class Question(models.Model):
    department = models.ForeignKey(
        "Department", on_delete=models.CASCADE, related_name="questions"
    )
    text = models.TextField()
    # NEW: Field to differentiate regular questions from concerned department questions
    is_concerned_question = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.department.name} {'(Concerned)' if self.is_concerned_question else ''}: {self.text[:50]}"


class EmployeeQuestionResponse(models.Model):
    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="responses"
    )
    department = models.ForeignKey(
        "Department", on_delete=models.CASCADE, related_name="responses"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    is_checked = models.BooleanField(default=False)

    class Meta:
        unique_together = ("employee", "department", "question")


class DepartmentEmployeeComment(models.Model):
    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="department_comments"
    )
    department = models.ForeignKey(
        "Department", on_delete=models.CASCADE, related_name="employee_comments"
    )
    comment_text = models.TextField(blank=True, null=True)
    # NEW: Field for Department Head ID
    department_head_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("employee", "department") # Each department can only add one comment per employee

    def __str__(self):
        return f"Comment from {self.department.name} for {self.employee.employee_name}"