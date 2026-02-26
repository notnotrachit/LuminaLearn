from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from datetime import datetime, date
import json
import logging
import csv
import io

# PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.platypus import KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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


# ─────────────────────────────────────────────────────────────────────────────
# ATTENDANCE REPORTS & EXPORT  (Closes #15)
# ─────────────────────────────────────────────────────────────────────────────

STELLAR_EXPLORER_BASE = "https://stellar.expert/explorer/testnet/tx"


def _build_attendance_queryset(request):
    """
    Parse common filter params (course_id, student_id, date_from, date_to)
    from GET and return a filtered Attendance queryset plus context extras.
    """
    qs = Attendance.objects.select_related(
        'student', 'lecture', 'lecture__course', 'session'
    ).order_by('-timestamp')

    courses = Course.objects.all()
    students = User.objects.filter(is_student=True).order_by('username')

    # Role-based scoping
    if request.user.is_student:
        qs = qs.filter(student=request.user)
        students = User.objects.filter(pk=request.user.pk)
    elif request.user.is_teacher:
        qs = qs.filter(lecture__course__teacher=request.user)
        courses = courses.filter(teacher=request.user)

    # Apply GET filters
    course_id = request.GET.get('course_id')
    student_id = request.GET.get('student_id')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if course_id:
        qs = qs.filter(lecture__course_id=course_id)
    if student_id and not request.user.is_student:
        qs = qs.filter(student_id=student_id)
    if date_from:
        try:
            qs = qs.filter(lecture__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(lecture__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    filters = {
        'course_id': course_id or '',
        'student_id': student_id or '',
        'date_from': date_from or '',
        'date_to': date_to or '',
    }

    return qs, courses, students, filters


@login_required
def reports_dashboard(request):
    """
    Main reports & analytics dashboard.
    Shows summary stats, attendance trend chart data and a blockchain
    verification table. Provides links to CSV and PDF exports.
    """
    qs, courses, students, filters = _build_attendance_queryset(request)

    total_records = qs.count()
    verified_records = qs.filter(blockchain_verified=True).count()
    unverified_records = total_records - verified_records
    verification_pct = int(verified_records / max(total_records, 1) * 100)

    # Trend: attendance counts per day (last 30 records or filtered period)
    trend_data = (
        qs.values('lecture__date')
          .annotate(count=Count('id'))
          .order_by('lecture__date')
    )
    chart_labels = json.dumps([str(r['lecture__date']) for r in trend_data])
    chart_values = json.dumps([r['count'] for r in trend_data])

    # Top courses by attendance
    top_courses = (
        qs.values('lecture__course__name', 'lecture__course__code')
          .annotate(count=Count('id'))
          .order_by('-count')[:5]
    )

    # Recent blockchain-verified records (for table preview)
    recent_verified = qs.filter(blockchain_verified=True)[:20]
    recent_all = qs[:20]

    # Add explorer URLs
    for att in recent_verified:
        att.explorer_url = (
            f"{STELLAR_EXPLORER_BASE}/{att.transaction_hash}"
            if att.transaction_hash else None
        )
    for att in recent_all:
        att.explorer_url = (
            f"{STELLAR_EXPLORER_BASE}/{att.transaction_hash}"
            if att.transaction_hash else None
        )

    return render(request, 'attendance/reports_dashboard.html', {
        'courses': courses,
        'students': students,
        'filters': filters,
        'total_records': total_records,
        'verified_records': verified_records,
        'unverified_records': unverified_records,
        'verification_pct': verification_pct,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
        'top_courses': top_courses,
        'recent_verified': recent_verified,
        'recent_all': recent_all,
    })


@login_required
def export_csv(request):
    """
    Export attendance records as a UTF-8 CSV file.
    Respects the same filters as reports_dashboard.
    """
    qs, _, _, filters = _build_attendance_queryset(request)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="luminalearn_attendance.csv"'
    # BOM for Excel UTF-8 compatibility
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'Student Username', 'Student Name',
        'Course Code', 'Course Name',
        'Lecture Title', 'Lecture Date',
        'Attendance Time',
        'Blockchain Verified', 'Transaction Hash',
        'Stellar Explorer URL',
    ])

    for att in qs.iterator():
        tx_hash = att.transaction_hash or ''
        explorer_url = f"{STELLAR_EXPLORER_BASE}/{tx_hash}" if tx_hash else ''
        writer.writerow([
            att.student.username,
            att.student.get_full_name() or att.student.username,
            att.lecture.course.code,
            att.lecture.course.name,
            att.lecture.title,
            att.lecture.date,
            att.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Yes' if att.blockchain_verified else 'No',
            tx_hash,
            explorer_url,
        ])

    return response


@login_required
def export_pdf(request):
    """
    Generate and download a PDF attendance report using ReportLab.
    Includes summary statistics, per-course breakdown and a
    Stellar blockchain verification section with tx hashes.
    """
    qs, courses_qs, _, filters = _build_attendance_queryset(request)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=22,
        textColor=colors.HexColor('#4f46e5'),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=20,
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor('#4338ca'),
        spaceBefore=14,
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#374151'),
        wordWrap='CJK',
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
    )

    elements = []

    # ── Title block ──────────────────────────────────────────────────────────
    elements.append(Paragraph('LuminaLearn — Attendance Report', title_style))
    generated_at = timezone.now().strftime('%d %b %Y, %H:%M UTC')
    subtitle_text = f'Generated: {generated_at}'
    if filters.get('date_from') or filters.get('date_to'):
        subtitle_text += f" | Period: {filters.get('date_from', '—')} → {filters.get('date_to', '—')}"
    elements.append(Paragraph(subtitle_text, subtitle_style))
    elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#e5e7eb')))
    elements.append(Spacer(1, 0.3 * cm))

    # ── Summary statistics ───────────────────────────────────────────────────
    total = qs.count()
    verified = qs.filter(blockchain_verified=True).count()
    unverified = total - verified
    pct = int(verified / max(total, 1) * 100)

    stats_data = [
        ['Total Records', 'Blockchain Verified', 'Unverified', 'Verification Rate'],
        [str(total), str(verified), str(unverified), f'{pct}%'],
    ]
    stats_table = Table(stats_data, colWidths=[6 * cm] * 4)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWHEIGHT', (0, 0), (-1, 0), 20),
        ('ROWHEIGHT', (0, 1), (-1, 1), 24),
        ('FONTSIZE', (0, 1), (-1, 1), 14),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (0, 1), colors.HexColor('#111827')),
        ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor('#059669')),
        ('TEXTCOLOR', (2, 1), (2, 1), colors.HexColor('#dc2626')),
        ('TEXTCOLOR', (3, 1), (3, 1), colors.HexColor('#4f46e5')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 0.4 * cm))

    # ── Per-course breakdown ─────────────────────────────────────────────────
    elements.append(Paragraph('Attendance by Course', section_style))
    course_stats = (
        qs.values('lecture__course__code', 'lecture__course__name')
          .annotate(
              total=Count('id'),
              verified_count=Count('id', filter=Q(blockchain_verified=True)),
          )
          .order_by('-total')
    )
    if course_stats:
        course_data = [['Course Code', 'Course Name', 'Total', 'Verified', 'Rate']]
        for row in course_stats:
            rate = int(row['verified_count'] / max(row['total'], 1) * 100)
            course_data.append([
                row['lecture__course__code'],
                row['lecture__course__name'],
                str(row['total']),
                str(row['verified_count']),
                f"{rate}%",
            ])
        col_widths = [3.5 * cm, 9 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]
        course_table = Table(course_data, colWidths=col_widths, repeatRows=1)
        course_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#818cf8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f3ff')]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 16),
        ]))
        elements.append(course_table)
    else:
        elements.append(Paragraph('No course data available for this filter.', styles['Normal']))

    elements.append(Spacer(1, 0.4 * cm))

    # ── Detailed attendance log ──────────────────────────────────────────────
    elements.append(Paragraph('Detailed Attendance Log', section_style))
    detail_data = [[
        'Student', 'Course', 'Lecture', 'Date', 'Time', 'Verified', 'TX Hash (first 16)',
    ]]
    for att in qs[:200]:  # cap at 200 rows for PDF size
        tx_short = (att.transaction_hash[:16] + '...') if att.transaction_hash else '-'
        verified_mark = 'Yes' if att.blockchain_verified else 'No'
        detail_data.append([
            Paragraph(att.student.username, cell_style),
            Paragraph(att.lecture.course.code, cell_style),
            Paragraph(att.lecture.title[:30], cell_style),
            str(att.lecture.date),
            att.timestamp.strftime('%H:%M'),
            verified_mark,
            Paragraph(tx_short, small_style),
        ])

    col_widths_d = [4 * cm, 3 * cm, 5.5 * cm, 2.5 * cm, 1.8 * cm, 2 * cm, 4.2 * cm]
    detail_table = Table(detail_data, colWidths=col_widths_d, repeatRows=1)
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (5, 0), (5, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eff6ff')]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#dbeafe')),
        ('ROWHEIGHT', (0, 0), (-1, -1), 14),
        ('TEXTCOLOR', (5, 1), (5, -1), colors.HexColor('#059669')),
    ]))
    elements.append(detail_table)

    # ── Blockchain verification section ──────────────────────────────────────
    blockchain_qs = qs.filter(blockchain_verified=True, transaction_hash__isnull=False)
    if blockchain_qs.exists():
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph('Stellar Blockchain Verification', section_style))
        elements.append(Paragraph(
            f'The following {blockchain_qs.count()} attendance records are verifiably recorded '
            f'on the Stellar Testnet blockchain. Each transaction hash can be independently '
            f'verified at: {STELLAR_EXPLORER_BASE}/{{tx_hash}}',
            ParagraphStyle('BlockchainNote', parent=styles['Normal'], fontSize=8,
                           textColor=colors.HexColor('#374151'), spaceAfter=8),
        ))
        bc_data = [['Student', 'Course', 'Lecture Date', 'Transaction Hash', 'Stellar Explorer URL']]
        for att in blockchain_qs[:100]:
            explorer_url = f"{STELLAR_EXPLORER_BASE}/{att.transaction_hash}"
            bc_data.append([
                att.student.username,
                att.lecture.course.code,
                str(att.lecture.date),
                Paragraph(att.transaction_hash or '—', small_style),
                Paragraph(explorer_url, small_style),
            ])
        bc_col_widths = [3.5 * cm, 2.5 * cm, 2.5 * cm, 8 * cm, 10 * cm]
        bc_table = Table(bc_data, colWidths=bc_col_widths, repeatRows=1)
        bc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecfdf5')]),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1fae5')),
            ('ROWHEIGHT', (0, 0), (-1, -1), 14),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(bc_table)

    # ── Footer ───────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e5e7eb')))
    elements.append(Paragraph(
        f'LuminaLearn — Blockchain-Based Attendance System | '
        f'Stellar Testnet | Report generated {generated_at}',
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7,
                       textColor=colors.HexColor('#9ca3af'), alignment=TA_CENTER),
    ))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="luminalearn_attendance_report.pdf"'
    return response


@login_required
def attendance_analytics_api(request):
    """
    JSON API endpoint for Chart.js attendance analytics data.
    Returns trend data, course distribution and verification stats.
    """
    qs, _, _, _ = _build_attendance_queryset(request)

    # Daily trend
    trend = (
        qs.values('lecture__date')
          .annotate(total=Count('id'), verified=Count('id', filter=Q(blockchain_verified=True)))
          .order_by('lecture__date')
    )
    trend_labels = [str(r['lecture__date']) for r in trend]
    trend_total = [r['total'] for r in trend]
    trend_verified = [r['verified'] for r in trend]

    # Course distribution
    course_dist = (
        qs.values('lecture__course__name')
          .annotate(count=Count('id'))
          .order_by('-count')[:8]
    )
    course_labels = [r['lecture__course__name'] for r in course_dist]
    course_counts = [r['count'] for r in course_dist]

    # Overall verification pie
    total = qs.count()
    verified_count = qs.filter(blockchain_verified=True).count()

    return JsonResponse({
        'trend': {
            'labels': trend_labels,
            'total': trend_total,
            'verified': trend_verified,
        },
        'courses': {
            'labels': course_labels,
            'counts': course_counts,
        },
        'verification': {
            'verified': verified_count,
            'unverified': total - verified_count,
        },
    })
