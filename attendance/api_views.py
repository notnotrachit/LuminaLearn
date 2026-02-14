from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from .models import User, Course, Lecture, Enrollment, AttendanceSession, Attendance
from .serializers import (
    UserSerializer, CourseSerializer, LectureSerializer, EnrollmentSerializer,
    AttendanceSessionSerializer, AttendanceSerializer, QRAttendanceSerializer,
    AttendanceMarkSerializer
)
from .stellar_helper import StellarHelper
from .qr_utils import verify_qr_data


class CustomAuthToken(ObtainAuthToken):
    """Custom authentication token view with user data"""
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'user_type': self._get_user_type(user)
        })
        
    def _get_user_type(self, user):
        if user.is_admin:
            return 'admin'
        elif user.is_teacher:
            return 'teacher'
        elif user.is_student:
            return 'student'
        return 'unknown'


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for User model - Read only for security"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user details"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def teachers(self, request):
        """Get list of teachers"""
        teachers = User.objects.filter(is_teacher=True)
        serializer = self.get_serializer(teachers, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def students(self, request):
        """Get list of students"""
        students = User.objects.filter(is_student=True)
        serializer = self.get_serializer(students, many=True)
        return Response(serializer.data)


class CourseViewSet(viewsets.ModelViewSet):
    """ViewSet for Course model"""
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter courses based on user role"""
        user = self.request.user
        if user.is_admin:
            return Course.objects.all()
        elif user.is_teacher:
            return Course.objects.filter(teacher=user)
        elif user.is_student:
            # Return courses the student is enrolled in
            return Course.objects.filter(enrollments__student=user)
        return Course.objects.none()
    
    def perform_create(self, serializer):
        """Set the teacher to current user when creating a course"""
        if not self.request.user.is_teacher and not self.request.user.is_admin:
            raise PermissionError("Only teachers can create courses")
        serializer.save(teacher=self.request.user)
    
    @action(detail=True, methods=['get'])
    def lectures(self, request, pk=None):
        """Get lectures for a specific course"""
        course = self.get_object()
        lectures = course.lectures.all().order_by('-date', '-start_time')
        serializer = LectureSerializer(lectures, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def enrollments(self, request, pk=None):
        """Get enrollments for a specific course"""
        course = self.get_object()
        enrollments = course.enrollments.all()
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)


class LectureViewSet(viewsets.ModelViewSet):
    """ViewSet for Lecture model"""
    queryset = Lecture.objects.all()
    serializer_class = LectureSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter lectures based on user role"""
        user = self.request.user
        if user.is_admin:
            return Lecture.objects.all()
        elif user.is_teacher:
            return Lecture.objects.filter(course__teacher=user)
        elif user.is_student:
            return Lecture.objects.filter(course__enrollments__student=user)
        return Lecture.objects.none()
    
    def perform_create(self, serializer):
        """Create lecture with blockchain integration"""
        user = self.request.user
        if not user.is_teacher and not user.is_admin:
            raise PermissionError("Only teachers can create lectures")
            
        lecture = serializer.save()
        
        # Create lecture on blockchain
        try:
            blockchain_response = StellarHelper.create_lecture(
                user.stellar_seed,
                lecture.id,
                lecture.title,
                str(lecture.date)
            )
            
            if 'error' not in blockchain_response:
                lecture.blockchain_lecture_id = str(lecture.id)
                lecture.save()
        except Exception as e:
            # Continue even if blockchain fails
            pass
    
    @action(detail=True, methods=['post'])
    def start_session(self, request, pk=None):
        """Start an attendance session for a lecture"""
        lecture = self.get_object()
        user = request.user
        
        if not user.is_teacher and not user.is_admin:
            return Response(
                {'error': 'Only teachers can start attendance sessions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if user != lecture.course.teacher and not user.is_admin:
            return Response(
                {'error': 'You can only start sessions for your own lectures'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if there's already an active session
        if lecture.sessions.filter(is_active=True).exists():
            return Response(
                {'error': 'There is already an active session for this lecture'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get end time from request or default to 1 hour from now
        end_time_str = request.data.get('end_time')
        if end_time_str:
            try:
                end_time = timezone.datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            except ValueError:
                return Response(
                    {'error': 'Invalid end_time format. Use ISO format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            end_time = timezone.now() + timezone.timedelta(hours=1)
        
        # Start attendance on blockchain
        try:
            blockchain_response = StellarHelper.start_attendance(
                user.stellar_seed,
                lecture.id,
                int(end_time.timestamp())
            )
            
            nonce = blockchain_response.get('nonce', StellarHelper.generate_nonce())
            blockchain_verified = 'error' not in blockchain_response
        except Exception as e:
            nonce = StellarHelper.generate_nonce()
            blockchain_verified = False
        
        # Create attendance session
        session = AttendanceSession.objects.create(
            lecture=lecture,
            end_time=end_time,
            nonce=nonce,
            blockchain_verified=blockchain_verified
        )
        
        serializer = AttendanceSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def attendances(self, request, pk=None):
        """Get attendances for a specific lecture"""
        lecture = self.get_object()
        attendances = lecture.attendances.all()
        serializer = AttendanceSerializer(attendances, many=True)
        return Response(serializer.data)


class AttendanceSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for AttendanceSession model"""
    queryset = AttendanceSession.objects.all()
    serializer_class = AttendanceSessionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter sessions based on user role"""
        user = self.request.user
        if user.is_admin:
            return AttendanceSession.objects.all()
        elif user.is_teacher:
            return AttendanceSession.objects.filter(lecture__course__teacher=user)
        elif user.is_student:
            return AttendanceSession.objects.filter(lecture__course__enrollments__student=user)
        return AttendanceSession.objects.none()
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close an attendance session"""
        session = self.get_object()
        user = request.user
        
        if not user.is_teacher and not user.is_admin:
            return Response(
                {'error': 'Only teachers can close attendance sessions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if user != session.lecture.course.teacher and not user.is_admin:
            return Response(
                {'error': 'You can only close sessions for your own lectures'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session.is_active = False
        session.end_time = timezone.now()
        session.save()
        
        # Close session on blockchain if it was verified
        if session.blockchain_verified:
            try:
                StellarHelper.close_attendance_session(
                    user.stellar_seed,
                    session.lecture.id
                )
            except Exception as e:
                # Continue even if blockchain update fails
                pass
        
        serializer = self.get_serializer(session)
        return Response(serializer.data)


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Attendance model"""
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter attendances based on user role"""
        user = self.request.user
        if user.is_admin:
            return Attendance.objects.all()
        elif user.is_teacher:
            return Attendance.objects.filter(lecture__course__teacher=user)
        elif user.is_student:
            return Attendance.objects.filter(student=user)
        return Attendance.objects.none()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_attendance_qr(request):
    """Mark attendance using QR code scan"""
    if not request.user.is_student:
        return Response(
            {'error': 'Only students can mark attendance'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = QRAttendanceSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    qr_data = serializer.validated_data['qr_data']
    
    # Verify QR data
    data = verify_qr_data(qr_data)
    if not data:
        return Response(
            {'error': 'Invalid QR code or expired'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    lecture_id = data['lecture_id']
    nonce = data['nonce']
    
    try:
        # Get lecture and active session
        lecture = get_object_or_404(Lecture, pk=lecture_id)
        session = AttendanceSession.objects.filter(
            lecture=lecture,
            nonce=nonce,
            is_active=True
        ).first()
        
        if not session:
            return Response(
                {'error': 'No active attendance session for this lecture'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already marked
        if Attendance.objects.filter(lecture=lecture, student=request.user).exists():
            return Response(
                {'error': 'You have already marked attendance for this lecture'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if student is enrolled
        if not Enrollment.objects.filter(course=lecture.course, student=request.user).exists():
            return Response(
                {'error': 'You are not enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark attendance on blockchain
        try:
            blockchain_response = StellarHelper.mark_attendance(
                request.user.stellar_seed,
                lecture.id,
                nonce
            )
            blockchain_verified = 'error' not in blockchain_response
            transaction_hash = blockchain_response.get('hash', '')
        except Exception as e:
            blockchain_verified = False
            transaction_hash = ''
        
        # Create attendance record
        attendance = Attendance.objects.create(
            student=request.user,
            lecture=lecture,
            session=session,
            blockchain_verified=blockchain_verified,
            transaction_hash=transaction_hash
        )
        
        serializer = AttendanceSerializer(attendance)
        return Response({
            'success': True,
            'message': 'Attendance marked successfully' + (' and recorded on blockchain!' if blockchain_verified else ''),
            'attendance': serializer.data,
            'blockchain_verified': blockchain_verified
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_attendance_manual(request):
    """Mark attendance manually by teacher"""
    user = request.user
    
    if not user.is_teacher and not user.is_admin:
        return Response(
            {'error': 'Only teachers can manually mark attendance'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = AttendanceMarkSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    lecture_id = serializer.validated_data['lecture_id']
    student_id = serializer.validated_data.get('student_id')
    
    try:
        lecture = get_object_or_404(Lecture, pk=lecture_id)
        
        # Permission check
        if user != lecture.course.teacher and not user.is_admin:
            return Response(
                {'error': 'You can only mark attendance for your own lectures'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if student_id:
            student = get_object_or_404(User, pk=student_id)
        else:
            # If no student_id provided, use current user (for student self-marking)
            if user.is_student:
                student = user
            else:
                return Response(
                    {'error': 'Student ID required for manual marking'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if student is enrolled
        if not Enrollment.objects.filter(course=lecture.course, student=student).exists():
            return Response(
                {'error': 'Student is not enrolled in this course'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already marked
        if Attendance.objects.filter(lecture=lecture, student=student).exists():
            return Response(
                {'error': 'Attendance already marked for this lecture'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create attendance record (manual marking doesn't use blockchain)
        attendance = Attendance.objects.create(
            student=student,
            lecture=lecture,
            blockchain_verified=False
        )
        
        serializer = AttendanceSerializer(attendance)
        return Response({
            'success': True,
            'message': 'Attendance marked manually',
            'attendance': serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def blockchain_status(request):
    """Get blockchain connection status"""
    try:
        # This would need to be implemented in StellarHelper
        status_info = {
            'connected': True,
            'network': 'testnet' if hasattr(StellarHelper, 'STELLAR_TESTNET') else 'unknown',
            'horizon_url': 'https://horizon-testnet.stellar.org',
            'contract_id': getattr(StellarHelper, 'CONTRACT_ID', 'Not configured')
        }
        return Response(status_info)
    except Exception as e:
        return Response({
            'connected': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_stats(request):
    """Get API statistics"""
    if not request.user.is_admin:
        return Response(
            {'error': 'Admin access required'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    stats = {
        'total_courses': Course.objects.count(),
        'total_lectures': Lecture.objects.count(),
        'total_attendances': Attendance.objects.count(),
        'active_sessions': AttendanceSession.objects.filter(is_active=True).count(),
        'blockchain_verified_attendances': Attendance.objects.filter(blockchain_verified=True).count(),
        'total_students': User.objects.filter(is_student=True).count(),
        'total_teachers': User.objects.filter(is_teacher=True).count(),
    }
    
    return Response(stats)