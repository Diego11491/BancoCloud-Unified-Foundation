import json, unittest
from src.aws.bff.common.responses import response
class ResponseTests(unittest.TestCase):
    def test_response(self):
        r = response(200, {'ok': True})
        self.assertEqual(r['statusCode'], 200)
        self.assertEqual(json.loads(r['body']), {'ok': True})
if __name__ == '__main__': unittest.main()
