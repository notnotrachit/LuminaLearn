from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db import transaction
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from datetime import datetime
import logging

from .models import User, Course, Lecture, Enrollment, AttendanceSession, Attendance
from .forms import (AdminSignUpForm, TeacherSignUpForm, StudentSignUpForm, 
                    CourseForm, LectureForm, EnrollmentForm, 
                    AttendanceSessionForm, QRAttendanceForm, ManualAttendanceForm)
from .stellar_helper import StellarHelper
from .qr_utils import generate_qr_code, verify_qr_data

# Authentication Views
class AdminSignUpView(CreateView):
    model = User
    form_class = AdminSignUpForm
    template_name = 'attendance/signup.html'
    
    def get_context_data(self, **kwargs):
        kwargs['user_type'] = 'admin'
        return super().get_context_data(**kwargs)
    
    def form_valid(self, form):
        user = form.save()
        # Create a blockchain wallet for the admin
        keypair = StellarHelper.create_keypair()
        user.stellar_public_key = keypair['public_key']
        user.stellar_seed = keypair['secret_seed']
        user.save()
        # Fund the account on testnet
        StellarHelper.fund_account(user.stellar_public_key)
        # Register user on the blockchain
        StellarHelper.register_teacher(user.stellar_seed)
        login(self.request, user)
        return redirect('dashboard')

@login_required
def teacher_signup(request):
    if not request.user.is_superuser:
        messages.error(request, "You don't have permission to create teacher accounts.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = TeacherSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Create a blockchain wallet for the teacher
            keypair = StellarHelper.create_keypair()
            user.stellar_public_key = keypair['public_key']
            user.stellar_seed = keypair['secret_seed']
            user.save()
            # Fund the account on testnet
            StellarHelper.fund_account(user.stellar_public_key)
            # Register teacher on the blockchain
            StellarHelper.register_teacher(user.stellar_seed)
            messages.success(request, f"Teacher account {user.username} created successfully!")
            return redirect('teacher_list')
    else:
        form = TeacherSignUpForm()
    
    return render(request, 'attendance/signup.html', {
        'form': form,
        'user_type': 'teacher'
    })

class StudentSignUpView(CreateView):
    model = User
    form_class = StudentSignUpForm
    template_name = 'attendance/signup.html'
    
    def get_context_data(self, **kwargs):
        kwargs['user_type'] = 'student'
        return super().get_context_data(**kwargs)
    
    def form_valid(self, form):
        user = form.save()
        # Create a blockchain wallet for the student
        keypair = StellarHelper.create_keypair()
        user.stellar_public_key = keypair['public_key']
        user.stellar_seed = keypair['secret_seed']
        user.save()
        # Fund the account on testnet
        StellarHelper.fund_account(user.stellar_public_key)
        # Register student on the blockchain
        StellarHelper.register_student(user.stellar_seed)
        login(self.request, user)
        return redirect('dashboard')

@login_required
def dashboard(request):
    if request.user.is_admin:
        courses = Course.objects.all()
        teacher_count = User.objects.filter(is_teacher=True).count()
        student_count = User.objects.filter(is_student=True).count()
        context = {
            'courses': courses,
            'teacher_count': teacher_count,
            'student_count': student_count
        }
        template = 'attendance/admin_dashboard.html'
    
    elif request.user.is_teacher:
        courses = Course.objects.filter(teacher=request.user)
        recent_lectures = Lecture.objects.filter(
            course__teacher=request.user
        ).order_by('-date', '-start_time')[:5]
        context = {
            'courses': courses,
            'recent_lectures': recent_lectures
        }
        template = 'attendance/teacher_dashboard.html'
    
    elif request.user.is_student:
        enrollments = Enrollment.objects.filter(student=request.user)
        recent_attendances = Attendance.objects.filter(
            student=request.user
        ).order_by('-timestamp')[:5]
        context = {
            'enrollments': enrollments,
            'recent_attendances': recent_attendances
        }
        template = 'attendance/student_dashboard.html'
    
    else:
        context = {}
        template = 'attendance/dashboard.html'
    
    return render(request, template, context)

# Course Management Views
@login_required
def course_list(request):
    if request.user.is_admin:
        courses = Course.objects.all()
    elif request.user.is_teacher:
        courses = Course.objects.filter(teacher=request.user)
    else:
        courses = Course.objects.filter(enrollments__student=request.user)
    
    return render(request, 'attendance/course_list.html', {'courses': courses})

@login_required
def course_detail(request, pk):
    course = get_object_or_404(Course, pk=pk)
    is_teacher = request.user.is_teacher and (request.user == course.teacher or request.user.is_admin)
    
    enrollments = Enrollment.objects.filter(course=course)
    lectures = Lecture.objects.filter(course=course).order_by('-date', '-start_time')
    
    # Check if the student is enrolled
    is_enrolled = False
    if request.user.is_student:
        is_enrolled = Enrollment.objects.filter(course=course, student=request.user).exists()
    
    # Handle enrollment form for teachers
    enrollment_form = None
    if is_teacher:
        if request.method == 'POST' and 'enrollment_form' in request.POST:
            enrollment_form = EnrollmentForm(request.POST)
            if enrollment_form.is_valid():
                enrollment = enrollment_form.save(commit=False)
                enrollment.course = course
                enrollment.save()
                messages.success(request, "Student added to the course successfully!")
                return redirect('course_detail', pk=course.pk)
        else:
            enrollment_form = EnrollmentForm()
    
    # Handle lecture form for teachers
    lecture_form = None
    if is_teacher:
        if request.method == 'POST' and 'lecture_form' in request.POST:
            lecture_form = LectureForm(request.POST)
            if lecture_form.is_valid():
                lecture = lecture_form.save(commit=False)
                lecture.course = course
                lecture.save()
                
                # Create lecture in blockchain
                # Calculate duration in minutes from start_time and end_time
                start_dt = datetime.combine(lecture.date, lecture.start_time)
                end_dt = datetime.combine(lecture.date, lecture.end_time)
                duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
                
                blockchain_response = StellarHelper.create_lecture(
                    request.user.stellar_seed,
                    lecture.id,
                    course.id,
                    lecture.title,
                    int(start_dt.timestamp()),
                    duration_minutes
                )
                
                # Update lecture with blockchain ID if successful
                if 'error' not in blockchain_response:
                    lecture.blockchain_lecture_id = str(lecture.id)
                    lecture.save()
                    messages.success(request, "Lecture created successfully and recorded on blockchain!")
                else:
                    messages.warning(request, f"Lecture created but blockchain recording failed: {blockchain_response.get('error', 'Unknown error')}")
                
                return redirect('course_detail', pk=course.pk)
        else:
            lecture_form = LectureForm()
    
    return render(request, 'attendance/course_detail.html', {
        'course': course,
        'enrollments': enrollments,
        'lectures': lectures,
        'is_teacher': is_teacher,
        'is_enrolled': is_enrolled,
        'enrollment_form': enrollment_form,
        'lecture_form': lecture_form
    })

@login_required
def create_course(request):
    if not (request.user.is_admin or request.user.is_teacher):
        messages.error(request, "You don't have permission to create courses.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = request.user
            course.save()
            messages.success(request, "Course created successfully!")
            return redirect('course_detail', pk=course.pk)
    else:
        form = CourseForm()
    
    return render(request, 'attendance/course_form.html', {'form': form})

# Lecture and Attendance Views
@login_required
def lecture_detail(request, pk):
    lecture = get_object_or_404(Lecture, pk=pk)
    course = lecture.course
    is_teacher = request.user.is_teacher and (request.user == course.teacher or request.user.is_admin)
    
    # Get attendance records
    attendances = Attendance.objects.filter(lecture=lecture)
    
    # Get active attendance session
    active_session = AttendanceSession.objects.filter(
        lecture=lecture, 
        is_active=True
    ).first()
    
    # Handle attendance session form for teachers
    session_form = None
    qr_code = None
    if is_teacher:
        if request.method == 'POST' and 'session_form' in request.POST:
            session_form = AttendanceSessionForm(request.POST)
            if session_form.is_valid():
                duration = session_form.cleaned_data['duration_minutes']
                
                # Create or update session
                if active_session:
                    # Update existing session
                    active_session.end_time = timezone.now() + timezone.timedelta(minutes=duration)
                    active_session.save()
                else:
                    # Create new session
                    end_time = timezone.now() + timezone.timedelta(minutes=duration)
                    
                    # Generate nonce
                    nonce = StellarHelper.generate_nonce()
                    
                    # Start attendance on blockchain
                    blockchain_response = StellarHelper.start_attendance(
                        request.user.stellar_seed,
                        lecture.id,
                        duration * 60  # Convert to seconds
                    )
                    
                    # If we get a nonce from the blockchain, use it instead
                    if 'error' not in blockchain_response and 'nonce' in blockchain_response:
                        nonce = blockchain_response['nonce']
                    
                    # Create session in database
                    active_session = AttendanceSession.objects.create(
                        lecture=lecture,
                        end_time=end_time,
                        nonce=nonce,
                        is_active=True,
                        blockchain_verified=True if 'error' not in blockchain_response else False
                    )
                    
                    if 'error' in blockchain_response:
                        messages.warning(request, f"Attendance session started but blockchain recording failed: {blockchain_response.get('error', 'Unknown error')}")
                    else:
                        messages.success(request, "Attendance session started and recorded on blockchain!")
                
                return redirect('lecture_detail', pk=lecture.pk)
        else:
            session_form = AttendanceSessionForm()
        
        # Generate QR code if session is active
        if active_session:
            qr_code = generate_qr_code(
                lecture.id,
                active_session.nonce,
                active_session.end_time
            )
    
    # Check if student has marked attendance
    student_attended = False
    if request.user.is_student:
        student_attended = Attendance.objects.filter(
            lecture=lecture, 
            student=request.user
        ).exists()
    
    return render(request, 'attendance/lecture_detail.html', {
        'lecture': lecture,
        'course': course,
        'attendances': attendances,
        'is_teacher': is_teacher,
        'active_session': active_session,
        'session_form': session_form,
        'qr_code': qr_code,
        'student_attended': student_attended
    })

@login_required
def scan_attendance(request):
    """View for students to scan QR code and mark attendance"""
    if not request.user.is_student:
        messages.error(request, "Only students can mark attendance.")
        return redirect('dashboard')
    
    return render(request, 'attendance/scan_attendance.html')

@login_required
def process_attendance(request):
    """Process the scanned QR code data"""
    if not request.user.is_student:
        return JsonResponse({'success': False, 'error': 'Only students can mark attendance'})
    
    if request.method == 'POST':
        try:
            # Get data from POST request
            qr_data = request.POST.get('qr_data')
            
            # Verify QR data
            data = verify_qr_data(qr_data)
            if not data:
                return JsonResponse({'success': False, 'error': 'Invalid QR code or expired'})
            
            lecture_id = data['lecture_id']
            nonce = data['nonce']
            
            # Get lecture and active session
            lecture = get_object_or_404(Lecture, pk=lecture_id)
            session = AttendanceSession.objects.filter(
                lecture=lecture,
                nonce=nonce,
                is_active=True
            ).first()
            
            if not session:
                return JsonResponse({'success': False, 'error': 'No active attendance session for this lecture'})
            
            # Check if already marked
            if Attendance.objects.filter(lecture=lecture, student=request.user).exists():
                return JsonResponse({'success': False, 'error': 'You have already marked attendance for this lecture'})
            
            # Check if student is enrolled in the course
            if not Enrollment.objects.filter(course=lecture.course, student=request.user).exists():
                return JsonResponse({'success': False, 'error': 'You are not enrolled in this course'})
            
            # Mark attendance on blockchain
            blockchain_response = StellarHelper.mark_attendance(
                request.user.stellar_seed,
                lecture.id,
                nonce
            )
            
            # Determine blockchain verification status
            blockchain_verified = 'error' not in blockchain_response
            
            # Create attendance record
            attendance = Attendance.objects.create(
                student=request.user,
                lecture=lecture,
                session=session,
                blockchain_verified=blockchain_verified
            )
            
            # If there's a transaction hash from blockchain, save it
            if blockchain_verified and 'hash' in blockchain_response:
                attendance.transaction_hash = blockchain_response['hash']
                attendance.save()
                
                response_message = 'Attendance marked successfully and recorded on blockchain!'
            else:
                response_message = 'Attendance marked successfully, but blockchain recording failed.'
                if 'error' in blockchain_response:
                    print(f"Blockchain error: {blockchain_response['error']}")
            
            return JsonResponse({
                'success': True, 
                'message': response_message,
                'course': lecture.course.name,
                'lecture': lecture.title,
                'blockchain_verified': blockchain_verified
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def close_attendance_session(request, session_id):
    """Close an active attendance session"""
    session = get_object_or_404(AttendanceSession, pk=session_id)
    lecture = session.lecture
    
    # Security check
    if not request.user.is_teacher or (request.user != lecture.course.teacher and not request.user.is_admin):
        messages.error(request, "You don't have permission to close this attendance session.")
        return redirect('lecture_detail', pk=lecture.pk)
    
    session.is_active = False
    session.end_time = timezone.now()
    session.save()
    
    # Close session on blockchain if it was verified
    if session.blockchain_verified:
        blockchain_response = StellarHelper.close_attendance_session(
            request.user.stellar_seed,
            lecture.id
        )
        
        if 'error' in blockchain_response:
            messages.warning(request, f"Attendance session closed but blockchain update failed: {blockchain_response.get('error', 'Unknown error')}")
        else:
            messages.success(request, "Attendance session closed and blockchain updated!")
    else:
        messages.success(request, "Attendance session closed successfully!")
    
    return redirect('lecture_detail', pk=lecture.pk)

@login_required
def manual_attendance(request, lecture_id):
    """Allow teachers to mark attendance manually"""
    lecture = get_object_or_404(Lecture, pk=lecture_id)
    course = lecture.course
    
    # Security check
    if not request.user.is_teacher or (request.user != course.teacher and not request.user.is_admin):
        messages.error(request, "You don't have permission to mark attendance for this lecture.")
        return redirect('lecture_detail', pk=lecture.pk)
    
    # Get enrolled students
    enrolled_students = User.objects.filter(
        enrollments__course=course,
        is_student=True
    )
    
    # Get students who already have attendance
    attended_students = User.objects.filter(
        attendances__lecture=lecture
    )
    
    # Initial form selection
    initial_students = attended_students.values_list('id', flat=True)
    
    if request.method == 'POST':
        form = ManualAttendanceForm(course, request.POST, initial={'students': initial_students})
        if form.is_valid():
            selected_students = form.cleaned_data['students']
            
            with transaction.atomic():
                # Remove attendance for deselected students
                Attendance.objects.filter(lecture=lecture).exclude(student__in=selected_students).delete()
                
                # Add attendance for newly selected students
                for student in selected_students:
                    if not Attendance.objects.filter(lecture=lecture, student=student).exists():
                        # Record attendance on blockchain
                        blockchain_response = StellarHelper.manual_attendance(
                            request.user.stellar_seed,
                            lecture.id,
                            student.stellar_public_key
                        )
                        
                        # Determine blockchain verification status
                        blockchain_verified = 'error' not in blockchain_response
                        
                        # Create attendance record
                        attendance = Attendance.objects.create(
                            student=student,
                            lecture=lecture,
                            blockchain_verified=blockchain_verified
                        )
                        
                        # If there's a transaction hash from blockchain, save it
                        if blockchain_verified and 'hash' in blockchain_response:
                            attendance.transaction_hash = blockchain_response['hash']
                            attendance.save()
            
            messages.success(request, "Attendance updated successfully!")
            return redirect('lecture_detail', pk=lecture.pk)
    else:
        form = ManualAttendanceForm(course, initial={'students': initial_students})
    
    return render(request, 'attendance/manual_attendance.html', {
        'form': form,
        'lecture': lecture,
        'course': course
    })

# User Management Views
@login_required
def teacher_list(request):
    if not request.user.is_superuser:
        messages.error(request, "You don't have permission to view teacher list.")
        return redirect('dashboard')
    
    teachers = User.objects.filter(is_teacher=True)
    return render(request, 'attendance/teacher_list.html', {'teachers': teachers})

@login_required
def student_list(request):
    if not (request.user.is_admin or request.user.is_teacher):
        messages.error(request, "You don't have permission to view student list.")
        return redirect('dashboard')
    
    if request.user.is_admin:
        students = User.objects.filter(is_student=True)
    else:  # Teacher
        teaching_courses = Course.objects.filter(teacher=request.user)
        students = User.objects.filter(
            enrollments__course__in=teaching_courses,
            is_student=True
        ).distinct()
    
    return render(request, 'attendance/student_list.html', {'students': students})

# Add this new view
@login_required
def check_blockchain_connection(request):
    """
    Check if the blockchain connection is working
    """
    if not request.user.is_staff and not request.user.is_teacher:
        messages.error(request, "You don't have permission to access this page")
        return redirect('dashboard')
    
    # Check the contract connection
    result = StellarHelper.verify_contract_connection()
    
    # Return JSON response or render a template based on the request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)
    
    return render(request, 'attendance/blockchain_status.html', {
        'result': result
    })

@login_required
def blockchain_statistics(request):
    """
    View to display blockchain-related statistics
    """
    if not (request.user.is_staff or request.user.is_teacher):
        messages.error(request, "You don't have permission to access this page")
        return redirect('dashboard')
        
    # Get statistics
    total_lectures = Lecture.objects.count()
    lectures_on_blockchain = Lecture.objects.filter(blockchain_lecture_id__isnull=False).count()
    
    total_attendance = Attendance.objects.count()
    blockchain_verified_attendance = Attendance.objects.filter(blockchain_verified=True).count()
    
    total_sessions = AttendanceSession.objects.count()
    blockchain_verified_sessions = AttendanceSession.objects.filter(blockchain_verified=True).count()
    
    # Recent blockchain transactions
    recent_attendances = Attendance.objects.filter(
        blockchain_verified=True
    ).order_by('-timestamp')[:10]
    
    return render(request, 'attendance/blockchain_statistics.html', {
        'total_lectures': total_lectures,
        'lectures_on_blockchain': lectures_on_blockchain,
        'total_attendance': total_attendance,
        'blockchain_verified_attendance': blockchain_verified_attendance,
        'total_sessions': total_sessions,
        'blockchain_verified_sessions': blockchain_verified_sessions,
        'recent_attendances': recent_attendances,
        'blockchain_percentage': int(blockchain_verified_attendance / max(total_attendance, 1) * 100)
    })


class RateLimitedPasswordResetView(PasswordResetView):
    """
    Password reset view with rate limiting to prevent abuse.
    Allows maximum 5 reset attempts per IP per hour.
    """
    template_name = 'attendance/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.txt'
    html_email_template_name = 'registration/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')
    
    # Rate limiting settings
    MAX_ATTEMPTS = 5  # Maximum attempts per hour
    RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
    
    def get_rate_limit_key(self):
        """Generate cache key for rate limiting based on IP address"""
        ip_address = self.get_client_ip()
        return f"password_reset_limit_{ip_address}"
    
    def get_client_ip(self):
        """Get client IP address from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
    def is_rate_limited(self):
        """Check if current IP is rate limited"""
        cache_key = self.get_rate_limit_key()
        current_attempts = cache.get(cache_key, 0)
        return current_attempts >= self.MAX_ATTEMPTS
    
    def increment_attempt(self):
        """Increment rate limit counter for current IP"""
        cache_key = self.get_rate_limit_key()
        current_attempts = cache.get(cache_key, 0)
        cache.set(cache_key, current_attempts + 1, self.RATE_LIMIT_WINDOW)
    
    def dispatch(self, request, *args, **kwargs):
        """Check rate limiting before processing request"""
        if self.is_rate_limited():
            messages.error(
                request, 
                f"Too many password reset attempts. Please try again in 1 hour."
            )
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Process valid form and increment rate limit counter"""
        self.increment_attempt()
        
        # Log the attempt for security monitoring
        logger = logging.getLogger(__name__)
        logger.info(f"Password reset attempt from IP {self.get_client_ip()}")
        
        # Add informational message
        messages.info(
            self.request,
            f"Password reset email sent if the account exists. "
            f"You have {max(0, self.MAX_ATTEMPTS - cache.get(self.get_rate_limit_key(), 0))} attempts remaining this hour."
        )
        
        return super().form_valid(form)
