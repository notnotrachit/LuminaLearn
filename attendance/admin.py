from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import User, Course, Lecture, Enrollment, AttendanceSession, Attendance, FailedBlockchainTransaction

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
    list_display = ('code', 'name', 'teacher', 'created_at')
    search_fields = ('code', 'name', 'teacher__username')
    inlines = [EnrollmentInline, LectureInline]

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

class FailedBlockchainTransactionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing failed blockchain transactions.
    Issue #6: Add admin dashboard for blockchain monitoring/retries
    """
    list_display = (
        'id',
        'transaction_type',
        'status_badge',
        'error_type',
        'retry_info',
        'created_at',
        'actions_column',
    )
    list_filter = ('status', 'transaction_type', 'created_at')
    search_fields = (
        'error_type',
        'error_message',
        'student__username',
        'lecture__title',
        'course__name',
    )
    readonly_fields = (
        'transaction_type',
        'transaction_data',
        'error_type',
        'error_message',
        'error_traceback',
        'created_at',
        'updated_at',
        'resolved_at',
        'successful_tx_hash',
    )
    fieldsets = (
        ('Transaction Info', {
            'fields': ('transaction_type', 'status', 'transaction_data')
        }),
        ('Error Details', {
            'fields': ('error_type', 'error_message', 'error_traceback'),
            'classes': ('collapse',)
        }),
        ('Retry Info', {
            'fields': ('retry_count', 'max_retries', 'last_retry_at', 'successful_tx_hash')
        }),
        ('Related Objects', {
            'fields': ('student', 'lecture', 'course')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'resolved_at', 'resolved_by', 'notes')
        }),
    )
    actions = ['retry_selected_transactions', 'mark_as_cancelled']

    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': 'orange',
            'retrying': 'blue',
            'success': 'green',
            'failed': 'red',
            'cancelled': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def retry_info(self, obj):
        """Display retry count and capability"""
        if obj.can_retry():
            return format_html(
                '{}/{} - <strong style="color: green;">Can retry</strong>',
                obj.retry_count,
                obj.max_retries
            )
        return f'{obj.retry_count}/{obj.max_retries} - Max retries reached'
    retry_info.short_description = 'Retries'

    def actions_column(self, obj):
        """Display action buttons"""
        if obj.can_retry():
            retry_url = reverse('admin:retry_failed_transaction', args=[obj.id])
            return format_html(
                '<a class="button" href="{}">Retry Now</a>',
                retry_url
            )
        return '-'
    actions_column.short_description = 'Actions'

    def retry_selected_transactions(self, request, queryset):
        """Admin action to retry multiple transactions"""
        from .stellar_helper import StellarHelper

        retried = 0
        failed = 0

        for transaction in queryset.filter(status='pending'):
            if not transaction.can_retry():
                continue

            try:
                # Update status
                transaction.status = 'retrying'
                transaction.last_retry_at = timezone.now()
                transaction.retry_count += 1
                transaction.save()

                # Attempt retry based on transaction type
                helper = StellarHelper()
                tx_data = transaction.transaction_data

                if transaction.transaction_type == 'attendance':
                    result = helper.manual_attendance(
                        lecture_id=tx_data['lecture_id'],
                        student_public_key=tx_data['student_public_key'],
                        nonce=tx_data.get('nonce', '')
                    )
                # Add other transaction types as needed

                # Mark as success
                transaction.mark_success(
                    tx_hash=result.get('transaction_hash', ''),
                    resolved_by=request.user
                )
                retried += 1

            except Exception as e:
                transaction.status = 'pending'
                transaction.error_message += f"\n\nRetry failed: {str(e)}"
                transaction.save()
                failed += 1

        self.message_user(
            request,
            f'Retried {retried} transactions successfully. {failed} failed.'
        )
    retry_selected_transactions.short_description = 'Retry selected transactions'

    def mark_as_cancelled(self, request, queryset):
        """Admin action to cancel transactions"""
        updated = queryset.update(
            status='cancelled',
            resolved_at=timezone.now(),
            resolved_by=request.user
        )
        self.message_user(request, f'{updated} transactions marked as cancelled.')
    mark_as_cancelled.short_description = 'Mark as cancelled'


admin.site.register(User, CustomUserAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Lecture, LectureAdmin)
admin.site.register(Enrollment, EnrollmentAdmin)
admin.site.register(AttendanceSession, AttendanceSessionAdmin)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(FailedBlockchainTransaction, FailedBlockchainTransactionAdmin)
