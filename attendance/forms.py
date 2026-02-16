from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Course, Lecture, Enrollment

class AdminSignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True
        if commit:
            user.save()
        return user

class TeacherSignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_teacher = True
        if commit:
            user.save()
        return user

class StudentSignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_student = True
        if commit:
            user.save()
        return user

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ('name', 'code')

class LectureForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    
    class Meta:
        model = Lecture
        fields = ('title', 'date', 'start_time', 'end_time')

class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ('student', 'roll_number')
    
    def __init__(self, *args, **kwargs):
        super(EnrollmentForm, self).__init__(*args, **kwargs)
        self.fields['student'].queryset = User.objects.filter(is_student=True)

class AttendanceSessionForm(forms.Form):
    duration_minutes = forms.IntegerField(min_value=1, max_value=120, initial=15, 
                                        help_text='How long should the attendance session be open (in minutes)?')

class QRAttendanceForm(forms.Form):
    lecture_id = forms.CharField(widget=forms.HiddenInput())
    nonce = forms.CharField(widget=forms.HiddenInput())
    
class ManualAttendanceForm(forms.Form):
    students = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    def __init__(self, course, *args, **kwargs):
        super(ManualAttendanceForm, self).__init__(*args, **kwargs)
        self.fields['students'].queryset = User.objects.filter(
            enrollments__course=course,
            is_student=True
        )

class CourseEnrollmentForm(forms.Form):
    enrollment_code = forms.CharField(
        max_length=12,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter course enrollment code',
            'class': 'form-control',
            'style': 'text-transform: uppercase;'
        }),
        help_text='Enter the 8-character code provided by your teacher'
    )
    roll_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your roll number',
            'class': 'form-control'
        }),
        help_text='Enter your student roll number'
    )
    
    def clean_enrollment_code(self):
        code = self.cleaned_data['enrollment_code'].upper().strip()
        return code 