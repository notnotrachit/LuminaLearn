from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache

User = get_user_model()

class PasswordResetTests(TestCase):
    """Test cases for password reset functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass123"
        )
        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after tests"""
        cache.clear()

    def test_password_reset_form_loads(self):
        """Test that the password reset form loads correctly"""
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset your password")

    def test_password_reset_email_sent_valid_user(self):
        """Test that password reset email is sent for valid user"""
        response = self.client.post(
            reverse("password_reset"),
            {"email": "testuser@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        
        # Check email content
        email = mail.outbox[0]
        self.assertIn("Password Reset", email.subject)
        self.assertIn("testuser@example.com", email.to)

    def test_password_reset_email_sent_invalid_user(self):
        """Test that no email is sent for invalid user (but same response)"""
        response = self.client.post(
            reverse("password_reset"),
            {"email": "nonexistent@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("password_reset_done"))
        # No email should be sent for non-existent user
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_done_page(self):
        """Test that the password reset done page loads correctly"""
        response = self.client.get(reverse("password_reset_done"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email Sent!")

    def test_rate_limiting_functionality(self):
        """Test that rate limiting works after maximum attempts"""
        email = "testuser@example.com"
        
        # Make 5 requests (the limit)
        for i in range(5):
            response = self.client.post(
                reverse("password_reset"),
                {"email": email}
            )
            self.assertEqual(response.status_code, 302)
        
        # 6th request should be rate limited
        response = self.client.post(
            reverse("password_reset"),
            {"email": email}
        )
        # Should redirect to login with error message
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))

    def test_rate_limiting_per_ip(self):
        """Test that rate limiting is per-IP address"""
        # Simulate requests from different IPs by using different sessions
        email = "testuser@example.com"
        
        # Max out attempts for first session 
        for i in range(5):
            self.client.post(
                reverse("password_reset"),
                {"email": email}
            )
        
        # Create new client (simulates different session/IP)
        new_client = self.client_class()
        
        # Should still work with new client
        response = new_client.post(
            reverse("password_reset"),
            {"email": email}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("password_reset_done"))

    def test_password_reset_confirm_valid_token(self):
        """Test password reset confirmation with valid token"""
        # First, request password reset
        response = self.client.post(
            reverse("password_reset"),
            {"email": "testuser@example.com"}
        )
        
        # Should send email with reset link
        self.assertEqual(len(mail.outbox), 1)
        email_content = mail.outbox[0].body
        
        # Extract the reset URL from email (simplified for testing)
        # In real test, you'd parse the actual URL from email content
        # For now, just test that the confirm page loads
        
        # Test that confirm page loads (we'd need actual uidb64 and token in real test)
        # This is a simplified test that just checks the view exists
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        
        response = self.client.get(
            reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
        )
        self.assertEqual(response.status_code, 200)

    def test_password_reset_complete_page(self):
        """Test that the password reset complete page loads"""
        response = self.client.get(reverse("password_reset_complete"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password Reset Successful")

    def test_forgot_password_link_on_login_page(self):
        """Test that login page contains forgot password link"""
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/password_reset/"')
        self.assertContains(response, "Forgot your password?")