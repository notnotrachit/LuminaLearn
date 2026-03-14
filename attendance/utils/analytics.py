"""
Analytics Utility for LuminaLearn Attendance System
Provides attendance statistics and analytics functions
"""

from django.db.models import Count, Q, Avg
from datetime import datetime, timedelta


def get_course_attendance_stats(course):
    """
    Get comprehensive attendance statistics for a course
    
    Args:
        course: Course object
        
    Returns:
        dict: Dictionary containing various statistics
    """
    lectures = course.lectures.all()
    enrollments = course.enrollments.all()
    
    total_lectures = lectures.count()
    total_students = enrollments.count()
    
    if total_lectures == 0 or total_students == 0:
        return {
            'total_lectures': total_lectures,
            'total_students': total_students,
            'total_possible_attendances': 0,
            'total_attendances': 0,
            'overall_attendance_rate': 0,
            'blockchain_verified_rate': 0,
            'average_attendance_per_lecture': 0,
            'lectures_with_stats': []
        }
    
    total_possible_attendances = total_lectures * total_students
    
    # Get all attendances for this course
    from attendance.models import Attendance
    attendances = Attendance.objects.filter(lecture__course=course)
    total_attendances = attendances.count()
    
    # Calculate overall attendance rate
    overall_attendance_rate = (total_attendances / total_possible_attendances * 100) if total_possible_attendances > 0 else 0
    
    # Calculate blockchain verification rate
    blockchain_verified_count = attendances.filter(blockchain_verified=True).count()
    blockchain_verified_rate = (blockchain_verified_count / total_attendances * 100) if total_attendances > 0 else 0
    
    # Calculate average attendance per lecture
    average_attendance_per_lecture = total_attendances / total_lectures if total_lectures > 0 else 0
    
    # Get per-lecture statistics
    lectures_with_stats = []
    for lecture in lectures.order_by('-date', '-start_time'):
        lecture_attendances = attendances.filter(lecture=lecture).count()
        lecture_rate = (lecture_attendances / total_students * 100) if total_students > 0 else 0
        
        lectures_with_stats.append({
            'lecture': lecture,
            'attendance_count': lecture_attendances,
            'attendance_rate': lecture_rate,
            'date': lecture.date,
            'title': lecture.title
        })
    
    return {
        'total_lectures': total_lectures,
        'total_students': total_students,
        'total_possible_attendances': total_possible_attendances,
        'total_attendances': total_attendances,
        'overall_attendance_rate': round(overall_attendance_rate, 2),
        'blockchain_verified_rate': round(blockchain_verified_rate, 2),
        'average_attendance_per_lecture': round(average_attendance_per_lecture, 2),
        'lectures_with_stats': lectures_with_stats
    }


def get_student_attendance_stats(student):
    """
    Get attendance statistics for a student across all courses
    
    Args:
        student: User object (student)
        
    Returns:
        dict: Dictionary containing student statistics
    """
    from attendance.models import Attendance, Enrollment
    
    enrollments = student.enrollments.all()
    
    stats_by_course = []
    total_lectures_all = 0
    total_attended_all = 0
    
    for enrollment in enrollments:
        course = enrollment.course
        lectures = course.lectures.all()
        total_lectures = lectures.count()
        
        attended = student.attendances.filter(lecture__course=course).count()
        attendance_rate = (attended / total_lectures * 100) if total_lectures > 0 else 0
        
        total_lectures_all += total_lectures
        total_attended_all += attended
        
        stats_by_course.append({
            'course': course,
            'total_lectures': total_lectures,
            'attended': attended,
            'attendance_rate': round(attendance_rate, 2)
        })
    
    overall_rate = (total_attended_all / total_lectures_all * 100) if total_lectures_all > 0 else 0
    
    return {
        'total_courses': enrollments.count(),
        'total_lectures': total_lectures_all,
        'total_attended': total_attended_all,
        'overall_attendance_rate': round(overall_rate, 2),
        'courses': stats_by_course
    }


def get_lecture_attendance_stats(lecture):
    """
    Get attendance statistics for a specific lecture
    
    Args:
        lecture: Lecture object
        
    Returns:
        dict: Dictionary containing lecture statistics
    """
    from attendance.models import Attendance
    
    total_students = lecture.course.enrollments.count()
    attendances = Attendance.objects.filter(lecture=lecture)
    total_attended = attendances.count()
    
    attendance_rate = (total_attended / total_students * 100) if total_students > 0 else 0
    
    blockchain_verified = attendances.filter(blockchain_verified=True).count()
    blockchain_rate = (blockchain_verified / total_attended * 100) if total_attended > 0 else 0
    
    return {
        'total_students': total_students,
        'total_attended': total_attended,
        'total_absent': total_students - total_attended,
        'attendance_rate': round(attendance_rate, 2),
        'blockchain_verified_count': blockchain_verified,
        'blockchain_verified_rate': round(blockchain_rate, 2)
    }


def get_attendance_trends(course, days=30):
    """
    Get attendance trends over time for a course
    
    Args:
        course: Course object
        days: Number of days to analyze
        
    Returns:
        list: List of daily attendance data
    """
    from attendance.models import Attendance
    from django.utils import timezone
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    lectures = course.lectures.filter(
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    trends = []
    for lecture in lectures:
        attendances = Attendance.objects.filter(lecture=lecture).count()
        total_students = course.enrollments.count()
        rate = (attendances / total_students * 100) if total_students > 0 else 0
        
        trends.append({
            'date': lecture.date,
            'lecture_title': lecture.title,
            'attendance_count': attendances,
            'attendance_rate': round(rate, 2)
        })
    
    return trends


def get_low_attendance_students(course, threshold=75):
    """
    Get students with attendance below threshold
    
    Args:
        course: Course object
        threshold: Attendance percentage threshold (default 75%)
        
    Returns:
        list: List of students with low attendance
    """
    from attendance.models import Enrollment
    
    enrollments = course.enrollments.all()
    total_lectures = course.lectures.count()
    
    if total_lectures == 0:
        return []
    
    low_attendance_students = []
    
    for enrollment in enrollments:
        student = enrollment.student
        attended = student.attendances.filter(lecture__course=course).count()
        attendance_rate = (attended / total_lectures * 100) if total_lectures > 0 else 0
        
        if attendance_rate < threshold:
            low_attendance_students.append({
                'student': student,
                'roll_number': enrollment.roll_number,
                'attended': attended,
                'total_lectures': total_lectures,
                'attendance_rate': round(attendance_rate, 2)
            })
    
    # Sort by attendance rate (lowest first)
    low_attendance_students.sort(key=lambda x: x['attendance_rate'])
    
    return low_attendance_students
