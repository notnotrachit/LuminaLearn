from django import template

register = template.Library()

@register.simple_tag
def has_attendance(lecture, student):
    """Check if a student has attendance for a lecture."""
    return lecture.attendances.filter(student=student).exists()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Divide the value by the argument."""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def get_color_class(percent):
    """Return a CSS class based on attendance percentage."""
    try:
        percent = float(percent)
        if percent < 50:
            return "bg-red-500"
        elif percent < 75:
            return "bg-yellow-500"
        else:
            return "bg-green-500"
    except (ValueError, TypeError):
        return "bg-gray-400" 