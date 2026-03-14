"""
CSV Export Utility for LuminaLearn Attendance System
Enables exporting attendance data to CSV format for reporting and analysis
"""

import csv
from django.http import HttpResponse
from datetime import datetime


def export_attendance_to_csv(attendances, filename=None):
    """
    Export attendance records to CSV format
    
    Args:
        attendances: QuerySet of Attendance objects
        filename: Optional custom filename
        
    Returns:
        HttpResponse with CSV file
    """
    if filename is None:
        filename = f'attendance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Student Name',
        'Student Email',
        'Roll Number',
        'Course Code',
        'Course Name',
        'Lecture Title',
        'Lecture Date',
        'Attendance Time',
        'Blockchain Verified',
        'Transaction Hash'
    ])
    
    # Write data rows
    for attendance in attendances:
        # Get enrollment for roll number
        enrollment = attendance.student.enrollments.filter(
            course=attendance.lecture.course
        ).first()
        
        roll_number = enrollment.roll_number if enrollment else 'N/A'
        
        writer.writerow([
            attendance.student.get_full_name() or attendance.student.username,
            attendance.student.email,
            roll_number,
            attendance.lecture.course.code,
            attendance.lecture.course.name,
            attendance.lecture.title,
            attendance.lecture.date.strftime('%Y-%m-%d'),
            attendance.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Yes' if attendance.blockchain_verified else 'No',
            attendance.transaction_hash or 'N/A'
        ])
    
    return response


def export_course_attendance_summary(course, filename=None):
    """
    Export course attendance summary to CSV
    
    Args:
        course: Course object
        filename: Optional custom filename
        
    Returns:
        HttpResponse with CSV file
    """
    if filename is None:
        filename = f'course_summary_{course.code}_{datetime.now().strftime("%Y%m%d")}.csv'
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Get all lectures for the course
    lectures = course.lectures.all().order_by('date', 'start_time')
    enrollments = course.enrollments.all().select_related('student')
    
    # Write header
    header = ['Student Name', 'Roll Number', 'Email']
    for lecture in lectures:
        header.append(f"{lecture.title} ({lecture.date})")
    header.extend(['Total Present', 'Total Lectures', 'Attendance %'])
    
    writer.writerow(header)
    
    # Write data for each student
    for enrollment in enrollments:
        student = enrollment.student
        row = [
            student.get_full_name() or student.username,
            enrollment.roll_number,
            student.email
        ]
        
        present_count = 0
        for lecture in lectures:
            attended = student.attendances.filter(lecture=lecture).exists()
            row.append('P' if attended else 'A')
            if attended:
                present_count += 1
        
        total_lectures = lectures.count()
        attendance_percentage = (present_count / total_lectures * 100) if total_lectures > 0 else 0
        
        row.extend([
            present_count,
            total_lectures,
            f"{attendance_percentage:.2f}%"
        ])
        
        writer.writerow(row)
    
    return response


def export_lecture_attendance(lecture, filename=None):
    """
    Export attendance for a specific lecture to CSV
    
    Args:
        lecture: Lecture object
        filename: Optional custom filename
        
    Returns:
        HttpResponse with CSV file
    """
    if filename is None:
        filename = f'lecture_{lecture.id}_{datetime.now().strftime("%Y%m%d")}.csv'
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Student Name',
        'Roll Number',
        'Email',
        'Status',
        'Attendance Time',
        'Blockchain Verified',
        'Transaction Hash'
    ])
    
    # Get all enrolled students
    enrollments = lecture.course.enrollments.all().select_related('student')
    
    for enrollment in enrollments:
        student = enrollment.student
        attendance = student.attendances.filter(lecture=lecture).first()
        
        if attendance:
            writer.writerow([
                student.get_full_name() or student.username,
                enrollment.roll_number,
                student.email,
                'Present',
                attendance.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'Yes' if attendance.blockchain_verified else 'No',
                attendance.transaction_hash or 'N/A'
            ])
        else:
            writer.writerow([
                student.get_full_name() or student.username,
                enrollment.roll_number,
                student.email,
                'Absent',
                'N/A',
                'N/A',
                'N/A'
            ])
    
    return response


def export_student_attendance_report(student, filename=None):
    """
    Export individual student's attendance report to CSV
    
    Args:
        student: User object (student)
        filename: Optional custom filename
        
    Returns:
        HttpResponse with CSV file
    """
    if filename is None:
        filename = f'student_{student.username}_{datetime.now().strftime("%Y%m%d")}.csv'
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Course Code',
        'Course Name',
        'Lecture Title',
        'Lecture Date',
        'Lecture Time',
        'Attendance Status',
        'Attendance Time',
        'Blockchain Verified'
    ])
    
    # Get all enrollments
    enrollments = student.enrollments.all().select_related('course')
    
    for enrollment in enrollments:
        course = enrollment.course
        lectures = course.lectures.all().order_by('date', 'start_time')
        
        for lecture in lectures:
            attendance = student.attendances.filter(lecture=lecture).first()
            
            if attendance:
                writer.writerow([
                    course.code,
                    course.name,
                    lecture.title,
                    lecture.date.strftime('%Y-%m-%d'),
                    f"{lecture.start_time.strftime('%H:%M')} - {lecture.end_time.strftime('%H:%M')}",
                    'Present',
                    attendance.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'Yes' if attendance.blockchain_verified else 'No'
                ])
            else:
                writer.writerow([
                    course.code,
                    course.name,
                    lecture.title,
                    lecture.date.strftime('%Y-%m-%d'),
                    f"{lecture.start_time.strftime('%H:%M')} - {lecture.end_time.strftime('%H:%M')}",
                    'Absent',
                    'N/A',
                    'N/A'
                ])
    
    return response
