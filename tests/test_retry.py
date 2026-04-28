"""
Unit Tests for API Retry Logic
--------------------------------
Tests the exponential backoff retry mechanism in ai_grader.

Uses 'mocking' — a testing technique where we replace real functions
with fake ones that simulate specific behaviours (like API errors).
This lets us test retry logic without making real API calls.

unittest.mock.patch temporarily replaces a function during a test.
When the test ends, the original function is restored automatically.
"""

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ai_grader import call_ai


class TestRetryLogic:
    """Tests for exponential backoff retry on API errors."""

    @patch('services.ai_grader.get_client')
    @patch('services.ai_grader.time.sleep')
    def test_retries_on_rate_limit(self, mock_sleep, mock_get_client):
        """
        Should retry 3 times on a 429 rate limit error, then return error.
        
        @patch replaces get_client and time.sleep with fakes.
        We patch time.sleep so the test doesn't actually wait 2+4+8 seconds.
        """
        # Make the client raise a 429 error every time
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('Error code: 429 Rate limit exceeded')
        mock_get_client.return_value = mock_client

        result = call_ai(
            developer_prompt='test',
            user_prompt='test',
            expect_json=False
        )

        # Should have tried 4 times total (1 initial + 3 retries)
        assert mock_client.chat.completions.create.call_count == 4

        # Should have slept 3 times (between retries, not before the first attempt)
        assert mock_sleep.call_count == 3

        # Check the sleep times are exponential: 2, 4, 8
        sleep_times = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_times == [2, 4, 8]

        # Should return an error message mentioning rate limit
        assert 'error' in result
        assert 'Rate limit' in result['error']

    @patch('services.ai_grader.get_client')
    @patch('services.ai_grader.time.sleep')
    def test_retries_on_timeout(self, mock_sleep, mock_get_client):
        """Should retry on timeout errors."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('Request timeout')
        mock_get_client.return_value = mock_client

        result = call_ai(
            developer_prompt='test',
            user_prompt='test',
            expect_json=False
        )

        # Should have retried
        assert mock_client.chat.completions.create.call_count == 4
        assert 'timed out' in result['error']

    @patch('services.ai_grader.get_client')
    @patch('services.ai_grader.time.sleep')
    def test_retries_on_server_error(self, mock_sleep, mock_get_client):
        """Should retry on 500/502/503 server errors."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('Error code: 502 Bad Gateway')
        mock_get_client.return_value = mock_client

        result = call_ai(
            developer_prompt='test',
            user_prompt='test',
            expect_json=False
        )

        assert mock_client.chat.completions.create.call_count == 4
        assert 'error' in result

    @patch('services.ai_grader.get_client')
    def test_no_retry_on_auth_error(self, mock_get_client):
        """Should NOT retry on 401 authentication errors — retrying won't help."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('Error code: 401 Unauthorized')
        mock_get_client.return_value = mock_client

        result = call_ai(
            developer_prompt='test',
            user_prompt='test',
            expect_json=False
        )

        # Should only try once — no retries for auth errors
        assert mock_client.chat.completions.create.call_count == 1
        assert 'Authentication failed' in result['error']

    @patch('services.ai_grader.get_client')
    @patch('services.ai_grader.time.sleep')
    def test_succeeds_on_second_attempt(self, mock_sleep, mock_get_client):
        """
        Should return successfully if the API works on a retry.
        First call fails with 429, second call succeeds.
        """
        # Create a mock response for the successful call
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Success response'
        mock_response.choices[0].finish_reason = 'stop'
        mock_response.usage = MagicMock()

        mock_client = MagicMock()
        # First call raises error, second call returns success
        mock_client.chat.completions.create.side_effect = [
            Exception('Error code: 429 Rate limit exceeded'),
            mock_response
        ]
        mock_get_client.return_value = mock_client

        result = call_ai(
            developer_prompt='test',
            user_prompt='test',
            expect_json=False
        )

        # Should have tried twice (1 fail + 1 success)
        assert mock_client.chat.completions.create.call_count == 2

        # Should have slept once (between the two attempts)
        assert mock_sleep.call_count == 1

        # Should return the successful response
        assert result == 'Success response'

    @patch('services.ai_grader.get_client')
    @patch('services.ai_grader.time.sleep')
    def test_exponential_backoff_timing(self, mock_sleep, mock_get_client):
        """Verify the exact backoff times: 2s, 4s, 8s."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('Error code: 503 Service Unavailable')
        mock_get_client.return_value = mock_client

        call_ai(developer_prompt='test', user_prompt='test', expect_json=False)

        # Verify exponential backoff: 2^0*2=2, 2^1*2=4, 2^2*2=8
        sleep_times = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_times == [2, 4, 8]