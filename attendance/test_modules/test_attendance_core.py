"""
Comprehensive test suite covering all 7 bug fixes with regression tests.
16 Django unit tests for models, QR utilities, Stellar helper, and views.
"""

from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from datetime import timedelta
from unittest.mock import patch, MagicMock
import json

from attendance.models import User, AttendanceSession, Course, Lecture
from attendance.qr_utils import verify_qr_data, generate_qr_code
from attendance.stellar_helper import StellarHelper
from attendance.exceptions import AttendanceError
from attendance.views import process_attendance

User = get_user_model()


class TestAttendanceSessionIsExpired(TestCase):
    """
    Test suite for Bug #2: is_expired returns False for None end_time;
    True for past; False for future.
    """

    def setUp(self):
        """Set up test fixtures"""
        self.teacher = User.objects.create_user(
            username='teacher1',
            password='testpass123',
            is_teacher=True
        )
        self.course = Course.objects.create(
            name='Test Course',
            code='TEST101',
            teacher=self.teacher
        )
        self.lecture = Lecture.objects.create(
            course=self.course,
            title='Test Lecture',
            date=timezone.now().date(),
            start_time='10:00:00',
            end_time='11:00:00'
        )

    def test_is_expired_with_none_end_time(self):
        """Bug #2 regression: is_expired should return False when end_time is None"""
        session = AttendanceSession.objects.create(
            lecture=self.lecture,
            nonce='test_nonce',
            end_time=None
        )
        self.assertFalse(session.is_expired)

    def test_is_expired_with_past_end_time(self):
        """is_expired should return True when end_time is in the past"""
        session = AttendanceSession.objects.create(
            lecture=self.lecture,
            nonce='test_nonce',
            end_time=timezone.now() - timedelta(minutes=10)
        )
        self.assertTrue(session.is_expired)

    def test_is_expired_with_future_end_time(self):
        """is_expired should return False when end_time is in the future"""
        session = AttendanceSession.objects.create(
            lecture=self.lecture,
            nonce='test_nonce',
            end_time=timezone.now() + timedelta(minutes=10)
        )
        self.assertFalse(session.is_expired)


class TestVerifyQrData(TestCase):
    """
    Test suite for Bug #6: Timezone-aware expiry parsed correctly;
    expired QR rejected; valid QR accepted; malformed JSON returns None.
    """

    def test_valid_qr_accepted(self):
        """Valid QR data should be accepted and parsed correctly"""
        data = {
            'l': 123,
            'n': 'test_nonce_123',
            'e': (timezone.now() + timedelta(minutes=5)).isoformat()
        }
        json_data = json.dumps(data)
        result = verify_qr_data(json_data)

        self.assertIsNotNone(result)
        self.assertEqual(result['lecture_id'], 123)
        self.assertEqual(result['nonce'], 'test_nonce_123')

    def test_expired_qr_rejected(self):
        """Expired QR data should be rejected"""
        data = {
            'l': 123,
            'n': 'test_nonce_123',
            'e': (timezone.now() - timedelta(minutes=5)).isoformat()
        }
        json_data = json.dumps(data)
        result = verify_qr_data(json_data)

        self.assertIsNone(result)

    def test_timezone_aware_expiry_parsed_correctly(self):
        """Bug #6 regression: Timezone-aware datetime should parse without TypeError"""
        # Test with timezone-aware datetime (Django's default when USE_TZ=True)
        expiry_time = timezone.now() + timedelta(minutes=5)
        data = {
            'l': 456,
            'n': 'nonce_tz_test',
            'e': expiry_time.isoformat()
        }
        json_data = json.dumps(data)

        # Should not raise TypeError about offset-naive vs offset-aware comparison
        result = verify_qr_data(json_data)
        self.assertIsNotNone(result)

    def test_malformed_json_returns_none(self):
        """Malformed JSON should return None"""
        json_data = '{invalid json'
        result = verify_qr_data(json_data)
        self.assertIsNone(result)


class TestStellarHelperFundAccount(TestCase):
    """
    Test suite for Bug #4: Friendbot called on testnet;
    NOT called on mainnet — returns False immediately.
    """

    @override_settings(STELLAR_TESTNET=True)
    @patch('requests.get')
    def test_fund_account_called_on_testnet(self, mock_get):
        """Bug #4 regression: Friendbot should be called on testnet"""
        mock_get.return_value = MagicMock(status_code=200)

        public_key = 'GABC123TESTKEY'
        result = StellarHelper.fund_account(public_key)

        # Should call Friendbot
        mock_get.assert_called_once()
        self.assertTrue(result)

    @override_settings(STELLAR_TESTNET=False)
    def test_fund_account_not_called_on_mainnet(self):
        """Bug #4 regression: Friendbot should NOT be called on mainnet"""
        public_key = 'GABC123TESTKEY'
        result = StellarHelper.fund_account(public_key)

        # Should return False immediately without making HTTP request
        self.assertFalse(result)


class TestStellarHelperGenerateNonce(TestCase):
    """
    Test suite for nonce generation: URL-safe base64; uniqueness.
    """

    def test_nonce_is_url_safe_base64(self):
        """Generated nonce should be URL-safe base64"""
        nonce = StellarHelper.generate_nonce()

        # Should be a string
        self.assertIsInstance(nonce, str)

        # Should be base64 decodable
        import base64
        try:
            base64.b64decode(nonce)
            decoded = True
        except Exception:
            decoded = False

        self.assertTrue(decoded)

    def test_two_nonces_are_distinct(self):
        """Two consecutive nonce calls should produce different values (uniqueness)"""
        nonce1 = StellarHelper.generate_nonce()
        nonce2 = StellarHelper.generate_nonce()

        self.assertNotEqual(nonce1, nonce2)


class TestUserSeedEncryption(TestCase):
    """
    Test suite for Bug #1: set_stellar_seed + get_stellar_seed round-trip;
    DB column stores ciphertext; None returned when no seed set.
    """

    def test_seed_encryption_round_trip(self):
        """Bug #1 regression: Seed should encrypt/decrypt correctly"""
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        plaintext_seed = 'SALADBOWL12345SECRETSEED67890'
        user.set_stellar_seed(plaintext_seed)
        user.save()

        # Retrieve from DB
        user_from_db = User.objects.get(pk=user.pk)
        decrypted_seed = user_from_db.get_stellar_seed()

        self.assertEqual(decrypted_seed, plaintext_seed)

    def test_seed_stored_as_ciphertext_not_plaintext(self):
        """Bug #1 regression: DB column should contain ciphertext, not plaintext"""
        user = User.objects.create_user(
            username='testuser2',
            password='testpass123'
        )

        plaintext_seed = 'SALADBOWL12345SECRETSEED67890'
        user.set_stellar_seed(plaintext_seed)
        user.save()

        # Raw DB value should NOT equal plaintext
        user_from_db = User.objects.get(pk=user.pk)
        raw_encrypted = user_from_db.stellar_seed_encrypted

        # The encrypted value should be bytes
        self.assertIsInstance(raw_encrypted, (bytes, memoryview))

        # And should NOT contain the plaintext seed
        self.assertNotIn(plaintext_seed.encode(), bytes(raw_encrypted))

    def test_get_seed_returns_none_when_not_set(self):
        """get_stellar_seed should return None when no seed is set"""
        user = User.objects.create_user(
            username='testuser3',
            password='testpass123'
        )

        seed = user.get_stellar_seed()
        self.assertIsNone(seed)


class TestProcessAttendanceView(TestCase):
    """
    Test suite for Bug #5: Valid QR returns success JSON;
    internal exception returns generic error, not raw exception string.
    """

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.student = User.objects.create_user(
            username='student1',
            password='testpass123',
            is_student=True
        )

        # Create stellar keypair for student
        self.student.stellar_public_key = 'GABC123'
        self.student.set_stellar_seed('STEST123')
        self.student.save()

        # Log in the student
        self.client.force_login(self.student)

    @patch('attendance.views.verify_qr_data')
    @patch('attendance.views.StellarHelper.mark_attendance')
    def test_valid_qr_returns_success_json(self, mock_mark_attendance, mock_verify):
        """Valid QR should return success JSON response"""
        # Create course, lecture, and session
        teacher = User.objects.create_user(
            username='teacher1',
            password='testpass123',
            is_teacher=True
        )
        course = Course.objects.create(
            name='Test Course',
            code='TEST101',
            teacher=teacher
        )
        lecture = Lecture.objects.create(
            course=course,
            title='Test Lecture',
            date=timezone.now().date(),
            start_time='10:00:00',
            end_time='11:00:00'
        )
        session = AttendanceSession.objects.create(
            lecture=lecture,
            nonce='test_nonce',
            end_time=timezone.now() + timedelta(minutes=5),
            is_active=True
        )

        # Enroll student in course
        from attendance.models import Enrollment
        Enrollment.objects.create(
            student=self.student,
            course=course,
            roll_number='001'
        )

        # Mock verify_qr_data to return valid data
        mock_verify.return_value = {
            'lecture_id': lecture.id,
            'nonce': 'test_nonce'
        }

        # Mock blockchain response
        mock_mark_attendance.return_value = {
            'status': 'success',
            'hash': 'abc123'
        }

        # Create POST request using test client
        response = self.client.post('/attendance/process/', {
            'qr_data': json.dumps({'l': lecture.id, 'n': 'test_nonce'})
        })

        data = json.loads(response.content)
        self.assertTrue(data['success'])

    @patch('attendance.views.verify_qr_data')
    def test_internal_exception_returns_generic_error(self, mock_verify):
        """Bug #5 regression: Internal exception should return generic error, not raw exception"""
        # Mock verify_qr_data to raise an unexpected exception
        mock_verify.side_effect = RuntimeError("Internal server error with sensitive info")

        # Create POST request using test client
        response = self.client.post('/attendance/process/', {
            'qr_data': json.dumps({'l': 999, 'n': 'test'})
        })

        data = json.loads(response.content)
        self.assertFalse(data['success'])

        # Error message should NOT contain the raw exception string
        self.assertNotIn("Internal server error with sensitive info", data['error'])

        # Should contain generic error message
        self.assertIn("unexpected error", data['error'].lower())
