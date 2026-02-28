# Generated migration for Issue #6: Failed transaction queue
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_encrypt_stellar_seed'),
    ]

    operations = [
        migrations.CreateModel(
            name='FailedBlockchainTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('attendance', 'Mark Attendance'), ('lecture', 'Create Lecture'), ('course', 'Create Course'), ('other', 'Other')], max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending Retry'), ('retrying', 'Retrying'), ('success', 'Retry Successful'), ('failed', 'Permanently Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('transaction_data', models.JSONField(help_text='Original transaction parameters')),
                ('error_type', models.CharField(max_length=100)),
                ('error_message', models.TextField()),
                ('error_traceback', models.TextField(blank=True)),
                ('retry_count', models.IntegerField(default=0)),
                ('max_retries', models.IntegerField(default=3)),
                ('last_retry_at', models.DateTimeField(blank=True, null=True)),
                ('successful_tx_hash', models.CharField(blank=True, max_length=100, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, help_text='Admin notes')),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='failed_transactions', to='attendance.course')),
                ('lecture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='failed_transactions', to='attendance.lecture')),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_transactions', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='failed_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='failedblockchaintransaction',
            index=models.Index(fields=['status', '-created_at'], name='attendance_f_status_idx'),
        ),
        migrations.AddIndex(
            model_name='failedblockchaintransaction',
            index=models.Index(fields=['transaction_type', 'status'], name='attendance_f_type_status_idx'),
        ),
    ]
