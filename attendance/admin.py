from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Course, Lecture, Enrollment, AttendanceSession, Attendance

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_admin', 'is_teacher', 'is_student', 'stellar_public_key')
    list_filter = ('is_admin', 'is_teacher', 'is_student')
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Roles', {'fields': ('is_admin', 'is_teacher', 'is_student')}),
        ('Blockchain', {'fields': ('stellar_public_key', 'stellar_seed')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1

class LectureInline(admin.TabularInline):
    model = Lecture
    extra = 1

class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'teacher', 'enrollment_code', 'enrollment_expires_at', 'created_at')
    search_fields = ('code', 'name', 'teacher__username', 'enrollment_code')
    list_filter = ('created_at', 'teacher')
    readonly_fields = ('enrollment_code', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'teacher')
        }),
        ('Enrollment', {
            'fields': ('enrollment_code', 'enrollment_expires_at'),
            'description': 'The enrollment code is automatically generated and allows students to self-enroll in this course.'
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    inlines = [EnrollmentInline, LectureInline]
    
    actions = ['regenerate_enrollment_codes']
    
    def regenerate_enrollment_codes(self, request, queryset):
        """Admin action to regenerate enrollment codes for selected courses."""
        for course in queryset:
            course.enrollment_code = Course.generate_enrollment_code()
            course.save()
        
        count = queryset.count()
        self.message_user(
            request,
            f'Successfully regenerated enrollment codes for {count} course(s).'
        )
    
    regenerate_enrollment_codes.short_description = "Regenerate enrollment codes"

class LectureAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'date', 'start_time', 'end_time', 'blockchain_lecture_id')
    list_filter = ('date', 'course')
    search_fields = ('title', 'course__name', 'course__code')

class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'roll_number', 'enrollment_date')
    list_filter = ('course', 'enrollment_date')
    search_fields = ('student__username', 'course__name', 'roll_number')

class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('lecture', 'start_time', 'end_time', 'is_active')
    list_filter = ('is_active', 'start_time')
    search_fields = ('lecture__title', 'lecture__course__name')

class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'lecture', 'timestamp', 'blockchain_verified')
    list_filter = ('blockchain_verified', 'timestamp', 'lecture__course')
    search_fields = ('student__username', 'lecture__title', 'lecture__course__name')

admin.site.register(User, CustomUserAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Lecture, LectureAdmin)
admin.site.register(Enrollment, EnrollmentAdmin)
admin.site.register(AttendanceSession, AttendanceSessionAdmin)
admin.site.register(Attendance, AttendanceAdmin)
