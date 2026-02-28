# Course Factory Migration Guide

## Overview

This document describes the migration strategy for transitioning existing courses from the monolithic attendance contract to the new factory-based architecture.

## Background

### Old Architecture (Monolithic)
- Single `attendance` contract manages all courses
- All lectures and attendance records stored in one contract
- Limited scalability and isolation

### New Architecture (Factory Pattern)
- `course_factory` contract creates individual course contracts
- Each course has its own dedicated contract instance
- Better isolation, scalability, and permission management

## Migration Strategy

### Phase 1: Parallel Operation (Recommended)

Run both systems in parallel during transition period.

#### Timeline
- **Weeks 1-2**: Deploy factory contract, test with new courses
- **Weeks 3-4**: Migrate existing courses to factory pattern
- **Week 5**: Deprecate old contract, switch all operations to factory

#### Benefits
- Zero downtime migration
- Gradual rollout reduces risk
- Easy rollback if issues arise

### Phase 2: Data Migration

#### Step 1: Export Existing Course Data

```python
# management/commands/export_courses_for_migration.py
from django.core.management.base import BaseCommand
from attendance.models import Course, Lecture, Attendance
import json


class Command(BaseCommand):
    help = 'Export existing course data for factory migration'

    def handle(self, *args, **options):
        courses_data = []

        for course in Course.objects.all():
            course_data = {
                'id': course.id,
                'name': course.name,
                'code': course.code,
                'teacher_id': course.teacher.id,
                'teacher_public_key': course.teacher.stellar_public_key,
                'lectures': [],
                'created_at': course.created_at.isoformat(),
            }

            # Export lectures for this course
            for lecture in course.lectures.all():
                lecture_data = {
                    'id': lecture.id,
                    'title': lecture.title,
                    'scheduled_time': lecture.scheduled_time.isoformat(),
                    'blockchain_id': lecture.blockchain_lecture_id,
                    'attendance_records': lecture.attendance_records.count(),
                }
                course_data['lectures'].append(lecture_data)

            courses_data.append(course_data)

        # Save to JSON file
        with open('courses_migration_data.json', 'w') as f:
            json.dump(courses_data, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                f'Exported {len(courses_data)} courses to courses_migration_data.json'
            )
        )
```

Run export:
```bash
python manage.py export_courses_for_migration
```

#### Step 2: Deploy Factory Contract

```bash
# Deploy course_factory contract to blockchain
./scripts/deploy_course_factory.sh

# Save contract ID
export COURSE_FACTORY_CONTRACT_ID="<factory_contract_id>"
```

#### Step 3: Create Course Contracts via Factory

```python
# management/commands/migrate_courses_to_factory.py
from django.core.management.base import BaseCommand
from attendance.models import Course
from attendance.stellar_helper import StellarHelper
import json


class Command(BaseCommand):
    help = 'Migrate existing courses to factory pattern'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate migration without actual blockchain transactions',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Load exported data
        with open('courses_migration_data.json', 'r') as f:
            courses_data = json.load(f)

        stellar_helper = StellarHelper()
        migrated_count = 0
        failed_courses = []

        for course_data in courses_data:
            course = Course.objects.get(id=course_data['id'])

            self.stdout.write(f"Migrating course: {course.name} (ID: {course.id})")

            try:
                if not dry_run:
                    # Create course contract via factory
                    result = stellar_helper.create_course_via_factory(
                        teacher_public_key=course_data['teacher_public_key'],
                        course_code=course.code,
                        course_name=course.name,
                    )

                    # Store new contract ID
                    course.factory_contract_id = result['contract_id']
                    course.migrated_to_factory = True
                    course.migration_tx_hash = result['transaction_hash']
                    course.save()

                    # Migrate lectures to new contract
                    for lecture_data in course_data['lectures']:
                        lecture = course.lectures.get(id=lecture_data['id'])

                        # Re-create lecture in new contract
                        lecture_result = stellar_helper.create_lecture_in_course_contract(
                            contract_id=result['contract_id'],
                            lecture_id=str(lecture.id),
                            teacher_public_key=course.teacher.stellar_public_key,
                        )

                        lecture.factory_blockchain_id = lecture_result['lecture_id']
                        lecture.save()

                    migrated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Migrated course {course.name} with {len(course_data["lectures"])} lectures'
                        )
                    )
                else:
                    self.stdout.write(f'[DRY RUN] Would migrate course: {course.name}')
                    migrated_count += 1

            except Exception as e:
                failed_courses.append({
                    'course_id': course.id,
                    'course_name': course.name,
                    'error': str(e)
                })
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to migrate course {course.name}: {e}')
                )

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'Migration complete!'))
        self.stdout.write(f'Successfully migrated: {migrated_count} courses')
        self.stdout.write(f'Failed: {len(failed_courses)} courses')

        if failed_courses:
            self.stdout.write('\nFailed courses:')
            for failed in failed_courses:
                self.stdout.write(f"  - {failed['course_name']}: {failed['error']}")
```

Run migration:
```bash
# Test first with dry run
python manage.py migrate_courses_to_factory --dry-run

# Execute actual migration
python manage.py migrate_courses_to_factory
```

#### Step 4: Migrate Attendance Records (Historical Data)

**Important**: Historical attendance records can remain in the old contract. New attendance will use the new course contracts.

**Option A (Recommended)**: Keep historical data in old contract
- Simpler migration
- Read-only access to old contract for historical records
- All new attendance uses factory contracts

**Option B**: Migrate historical attendance
- More complex, requires re-writing attendance records
- Higher blockchain costs
- Only necessary if old contract will be fully deprecated

For Option A:
```python
# attendance/models.py - Add field to track migration status
class Attendance(models.Model):
    # ... existing fields ...
    legacy_contract = models.BooleanField(default=False)  # True if from old contract
    factory_contract_id = models.CharField(max_length=100, null=True)  # New contract ID
```

#### Step 5: Update StellarHelper Logic

```python
# attendance/stellar_helper.py

class StellarHelper:
    def mark_attendance(self, lecture, student_public_key, nonce):
        """Mark attendance using appropriate contract"""
        course = lecture.course

        # Check if course has been migrated to factory
        if hasattr(course, 'factory_contract_id') and course.factory_contract_id:
            # Use new course-specific contract
            return self._mark_attendance_factory(
                contract_id=course.factory_contract_id,
                lecture_id=str(lecture.id),
                student_public_key=student_public_key,
                nonce=nonce,
            )
        else:
            # Use old monolithic contract (legacy)
            return self._mark_attendance_legacy(
                lecture_id=str(lecture.id),
                student_public_key=student_public_key,
                nonce=nonce,
            )
```

### Phase 3: Verification

#### Verify Migration Success

```python
# management/commands/verify_factory_migration.py
from django.core.management.base import BaseCommand
from attendance.models import Course, Lecture
from attendance.stellar_helper import StellarHelper


class Command(BaseCommand):
    help = 'Verify course factory migration completed successfully'

    def handle(self, *args, **options):
        stellar_helper = StellarHelper()
        errors = []

        # Check all courses
        total_courses = Course.objects.count()
        migrated_courses = Course.objects.filter(migrated_to_factory=True).count()

        self.stdout.write(f'Total courses: {total_courses}')
        self.stdout.write(f'Migrated to factory: {migrated_courses}')

        # Verify each migrated course
        for course in Course.objects.filter(migrated_to_factory=True):
            try:
                # Verify contract exists on blockchain
                contract_exists = stellar_helper.verify_course_contract_exists(
                    course.factory_contract_id
                )

                if not contract_exists:
                    errors.append(f'Contract not found for course: {course.name}')
                    continue

                # Verify lectures in contract
                for lecture in course.lectures.all():
                    lecture_exists = stellar_helper.verify_lecture_in_contract(
                        contract_id=course.factory_contract_id,
                        lecture_id=str(lecture.id),
                    )

                    if not lecture_exists:
                        errors.append(
                            f'Lecture {lecture.title} not found in contract for course {course.name}'
                        )

                self.stdout.write(
                    self.style.SUCCESS(f'✓ Verified course: {course.name}')
                )

            except Exception as e:
                errors.append(f'Error verifying course {course.name}: {e}')

        # Report errors
        if errors:
            self.stdout.write(self.style.ERROR('\n⚠ Verification errors found:'))
            for error in errors:
                self.stdout.write(f'  - {error}')
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✓ All courses verified successfully!')
            )
```

Run verification:
```bash
python manage.py verify_factory_migration
```

### Phase 4: Deprecate Old Contract (Optional)

After confirming migration success:

1. **Mark old contract as read-only** (for historical data access)
2. **Update all UI** to use factory-based courses
3. **Archive old contract code** (keep for reference)
4. **Document cutover date** in system logs

## Rollback Plan

If migration fails:

### Immediate Rollback

```python
# Revert to old contract
# 1. Remove factory_contract_id from courses
Course.objects.update(factory_contract_id=None, migrated_to_factory=False)

# 2. Revert StellarHelper to use old contract
# (keep old methods available during migration period)

# 3. Stop factory contract deployments
```

### Database Migrations

Create reversible Django migrations:

```python
# migrations/XXXX_add_factory_fields.py
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='course',
            name='factory_contract_id',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='course',
            name='migrated_to_factory',
            field=models.BooleanField(default=False),
        ),
    ]

# Rollback with:
# python manage.py migrate attendance <previous_migration>
```

## Cost Estimation

### Blockchain Costs

For each course:
- Factory contract deployment: ~0.1 XLM
- Course creation via factory: ~0.01 XLM
- Lecture creation (per lecture): ~0.005 XLM

Example for 100 courses with 30 lectures each:
- Factory deployment: 0.1 XLM
- Course creation: 100 × 0.01 = 1 XLM
- Lecture creation: 100 × 30 × 0.005 = 15 XLM
- **Total: ~16.1 XLM (~$2 USD at current rates)**

### Time Estimation

- Export existing data: 5 minutes
- Deploy factory contract: 10 minutes
- Migrate per course: ~30 seconds
- Verification: 10 minutes

**Total for 100 courses: ~1 hour**

## Best Practices

1. **Test on testnet first**: Complete full migration on testnet before mainnet
2. **Backup everything**: Database snapshots before migration
3. **Monitor closely**: Watch for errors during migration
4. **Communicate downtime**: Inform users of maintenance window
5. **Keep old contract**: Maintain read-only access for historical data

## Support

For migration assistance:
- **Technical Team**: dev@luminalearn.example.com
- **Blockchain Team**: blockchain@luminalearn.example.com

## References

- [Issue #21: Factory Contracts Implementation](https://github.com/notnotrachit/LuminaLearn/issues/21)
- [Factory Pattern Documentation](../soroban/course_factory/README.md)
- [Soroban Contract Migration Guide](https://soroban.stellar.org/docs/how-to-guides/migration)
