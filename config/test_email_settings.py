import os
from pathlib import Path
import subprocess
import sys
import textwrap

from django.test import SimpleTestCase


class EmailSettingsTests(SimpleTestCase):
    def run_configuration(self, variables, script):
        environment = os.environ.copy()
        names = (
            "MAIL_BACKEND", "DEFAULT_FROM_EMAIL", "MANAGER_EMAIL", "SMTP_HOST",
            "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_USE_TLS",
            "SMTP_USE_SSL", "SMTP_TIMEOUT",
        )
        for name in names:
            environment.pop(name, None)
        environment.update({
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "SECRET_KEY": "isolated-email-settings-test-key-abcdefghijklmnopqrstuvwxyz-2026",
            "DEBUG": "False",
            "HTTPS_ENABLED": "False",
            "ALLOWED_HOSTS": "localhost,testserver",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        environment.update(variables)
        setup = """
import environ
from unittest.mock import patch
with patch.object(environ.Env, "read_env"):
    import django
    django.setup()
"""
        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent(setup) + textwrap.dedent(script)],
            cwd=Path(__file__).resolve().parent.parent,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

    def smtp_variables(self):
        return {
            "MAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "sender@example.test",
            "SMTP_PASSWORD": "fake-app-password-for-test",
            "SMTP_USE_TLS": "True",
            "SMTP_USE_SSL": "False",
            "SMTP_TIMEOUT": "12",
            "DEFAULT_FROM_EMAIL": "РКЦ <sender@example.test>",
            "MANAGER_EMAIL": "manager@example.test",
        }

    def test_console_is_available_without_smtp_credentials(self):
        result = self.run_configuration({}, """
            from django.core import mail
            backend = mail.mailers["default"]
            assert type(backend).__module__ == "django.core.mail.backends.console"
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_smtp_sends_using_tls_credentials_and_environment_addresses(self):
        result = self.run_configuration(self.smtp_variables(), """
            from django.conf import settings
            from django.core.mail import EmailMessage
            with patch("django.core.mail.backends.smtp.smtplib.SMTP") as smtp:
                sent = EmailMessage(
                    "Перевірка", "Тестовий лист", settings.DEFAULT_FROM_EMAIL,
                    [settings.MANAGER_EMAIL],
                ).send(using="default")
                assert sent == 1
                assert smtp.call_args.args == ("smtp.example.test", 587)
                assert smtp.call_args.kwargs["timeout"] == 12
                connection = smtp.return_value
                connection.starttls.assert_called_once()
                connection.login.assert_called_once_with(
                    "sender@example.test", "fake-app-password-for-test",
                )
                assert connection.sendmail.call_args.args[0] == "sender@example.test"
                assert connection.sendmail.call_args.args[1] == ["manager@example.test"]
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ssl_uses_ssl_transport_without_starttls(self):
        variables = self.smtp_variables()
        variables.update({"SMTP_PORT": "465", "SMTP_USE_TLS": "False", "SMTP_USE_SSL": "True"})
        result = self.run_configuration(variables, """
            from django.core import mail
            with patch("django.core.mail.backends.smtp.smtplib.SMTP_SSL") as smtp:
                backend = mail.mailers["default"]
                backend.open()
                assert smtp.call_args.args == ("smtp.example.test", 465)
                assert "context" in smtp.call_args.kwargs
                smtp.return_value.starttls.assert_not_called()
                backend.close()
        """)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_conflicting_tls_and_ssl_are_rejected(self):
        variables = self.smtp_variables()
        variables["SMTP_USE_SSL"] = "True"
        result = self.run_configuration(variables, "")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SMTP_USE_TLS і SMTP_USE_SSL", result.stderr)

    def test_empty_password_is_rejected(self):
        variables = self.smtp_variables()
        variables["SMTP_PASSWORD"] = ""
        result = self.run_configuration(variables, "")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SMTP_PASSWORD", result.stderr)

    def test_nonpositive_timeout_is_rejected(self):
        variables = self.smtp_variables()
        variables["SMTP_TIMEOUT"] = "0"
        result = self.run_configuration(variables, "")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SMTP_TIMEOUT", result.stderr)
