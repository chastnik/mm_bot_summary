import unittest

from mattermost_bot import MattermostBot


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


class _SessionStub:
    def __init__(self, status_code):
        self.status_code = status_code

    def post(self, *args, **kwargs):
        return _Response(self.status_code)


class TestMattermostBotTimeParsing(unittest.TestCase):
    def test_parse_night_time_as_24h(self):
        bot = MattermostBot()
        parsed = bot._parse_time_from_message("ежедневно в 2 ночи")
        self.assertEqual(parsed, "02:00")


class TestMattermostBotMessageSending(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_returns_true_on_201(self):
        bot = MattermostBot()
        bot.base_url = "https://example.org"
        bot._session_requests = _SessionStub(201)

        result = await bot._send_message("channel-id", "hello")

        self.assertTrue(result)
