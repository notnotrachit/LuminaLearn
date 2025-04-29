from django import template

register = template.Library()

@register.simple_tag
def has_attendance(lecture, student):
    """Check if a student has attendance for a lecture."""
    return lecture.attendances.filter(student=student).exists() 