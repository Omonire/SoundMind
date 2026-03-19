import unittest
from app import app, db, User, Job
import json

class SoundMindTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_signup(self):
        response = self.app.post('/signup',
                                 data=json.dumps(dict(email='test@example.com', password='password')),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'User created successfully', response.data)

    def test_login(self):
        self.app.post('/signup',
                       data=json.dumps(dict(email='test@example.com', password='password')),
                       content_type='application/json')
        response = self.app.post('/login',
                                data=json.dumps(dict(email='test@example.com', password='password')),
                                content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Logged in successfully', response.data)

    def test_paystack_webhook(self):
        import hmac
        import hashlib
        import os

        os.environ['PAYSTACK_SECRET_KEY'] = 'test_secret'
        self.app.post('/signup',
                       data=json.dumps(dict(email='test@example.com', password='password')),
                       content_type='application/json')

        payload = {
            "event": "charge.success",
            "data": {
                "amount": 250000, # 2,500 NGN
                "customer": {"email": "test@example.com"}
            }
        }
        payload_bytes = json.dumps(payload).encode('utf-8')
        signature = hmac.new(b'test_secret', payload_bytes, hashlib.sha512).hexdigest()

        response = self.app.post('/webhook/paystack',
                                 data=payload_bytes,
                                 content_type='application/json',
                                 headers={'x-paystack-signature': signature})

        self.assertEqual(response.status_code, 200)
        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            self.assertEqual(user.credits_balance, 50)

    def test_credit_calculation(self):
        self.app.post('/signup',
                       data=json.dumps(dict(email='test2@example.com', password='password')),
                       content_type='application/json')

        # Manually give credits to test process logic
        with app.app_context():
            user = User.query.filter_by(email='test2@example.com').first()
            user.credits_balance = 10
            db.session.commit()

        # Login
        self.app.post('/login',
                       data=json.dumps(dict(email='test2@example.com', password='password')),
                       content_type='application/json')

        # Test credit deduction (ceiling based)
        # 1500 chars should take 2 credits
        text = "A" * 1500
        # We need to mock external API calls to Gemini and ElevenLabs for this to run in CI
        # But for this test let's just check the calculation logic if we could

        # Actually, let's just test a helper if we had one, but it's inside 'process'
        # Let's mock the process_document and generate_audio calls
        import unittest.mock as mock
        with mock.patch('app.process_document', return_value="script"), \
             mock.patch('app.generate_audio', return_value="/static/test.mp3"):
            response = self.app.post('/process',
                                     data=json.dumps(dict(text=text, mode='monologue')),
                                     content_type='application/json')
            self.assertEqual(response.status_code, 200)
            with app.app_context():
                user = User.query.filter_by(email='test2@example.com').first()
                self.assertEqual(user.credits_balance, 8) # 10 - 2

if __name__ == '__main__':
    unittest.main()
