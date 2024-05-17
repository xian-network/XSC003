import unittest
from contracting.stdlib.bridge.time import Datetime
from contracting.client import ContractingClient
from xian_py.wallet import Wallet
import datetime

class TestCurrencyContract(unittest.TestCase):
    def setUp(self):
        # Called before every test, bootstraps the environment.
        self.client = ContractingClient()
        self.client.flush()

        with open("token_xsc003.py") as f:
            code = f.read()
            self.client.submit(code, name="currency")

        self.currency = self.client.get_contract("currency")

    def tearDown(self):
        # Called after every test, ensures each test starts with a clean slate and is isolated from others
        self.client.flush()

    def test_initial_balance(self):
        # GIVEN the initial setup
        # WHEN checking the initial balance
        sys_balance = self.currency.balances["sys"]
        # THEN the balance should be as expected
        self.assertEqual(sys_balance, 1_000_000)

    def test_transfer(self):
        # GIVEN a transfer setup
        self.currency.transfer(amount=100, to="bob", signer="sys")
        # WHEN checking balances after transfer
        bob_balance = self.currency.balances["bob"]
        sys_balance = self.currency.balances["sys"]
        # THEN the balances should reflect the transfer correctly
        self.assertEqual(bob_balance, 100)
        self.assertEqual(sys_balance, 999_900)

    def test_change_metadata(self):
        # GIVEN a non-operator trying to change metadata
        with self.assertRaises(Exception):
            self.currency.change_metadata(
                key="token_name", value="NEW TOKEN", signer="bob"
            )
        # WHEN the operator changes metadata
        self.currency.change_metadata(key="token_name", value="NEW TOKEN", signer="sys")
        new_name = self.currency.metadata["token_name"]
        # THEN the metadata should be updated correctly
        self.assertEqual(new_name, "NEW TOKEN")

    def test_approve_and_allowance(self):
        # GIVEN an approval setup
        self.currency.approve(amount=500, to="eve", signer="sys")
        # WHEN checking the allowance
        allowance = self.currency.balances["sys", "eve"]
        # THEN the allowance should be set correctly
        self.assertEqual(allowance, 500)

    def test_transfer_from_without_approval(self):
        # GIVEN an attempt to transfer without approval
        # WHEN the transfer is attempted
        # THEN it should fail
        with self.assertRaises(Exception):
            self.currency.transfer_from(
                amount=100, to="bob", main_account="sys", signer="bob"
            )

    def test_transfer_from_with_approval(self):
        # GIVEN a setup with approval
        self.currency.approve(amount=200, to="bob", signer="sys")
        # WHEN transferring with approval
        self.currency.transfer_from(
            amount=100, to="bob", main_account="sys", signer="bob"
        )
        bob_balance = self.currency.balances["bob"]
        sys_balance = self.currency.balances["sys"]
        remaining_allowance = self.currency.balances["sys", "bob"]
        # THEN the balances and allowance should reflect the transfer
        self.assertEqual(bob_balance, 100)
        self.assertEqual(sys_balance, 999_900)
        self.assertEqual(remaining_allowance, 100)

    # XST002 / Permit Tests

    # Helper Functions

    def fund_wallet(self, funder, spender, amount):
        self.currency.transfer(amount=100, to=spender, signer=funder)

    def construct_permit_msg(self, owner: str, spender: str, value: float, deadline: dict):
        return f"{owner}:{spender}:{value}:{deadline}:currency"

    def create_deadline(self, minutes=1):
        d = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        return Datetime(d.year, d.month, d.day, hour=d.hour, minute=d.minute)

    # Permit Tests

    def test_permit_valid(self):
        # GIVEN a valid permit setup
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        deadline = self.create_deadline()
        spender = "some_spender"
        value = 100
        msg = self.construct_permit_msg(public_key, spender, value, deadline)
        signature = wallet.sign_msg(msg)
        # WHEN the permit is granted
        response = self.currency.permit(owner=public_key, spender=spender, value=value, deadline=deadline, signature=signature)
        # THEN the response should indicate success
        self.assertIn("Permit granted", response)

    def test_permit_expired(self):
        # GIVEN a permit setup with an expired deadline
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        deadline = self.create_deadline(minutes=-1)  # Past deadline
        spender = "some_spender"
        value = 100
        msg = self.construct_permit_msg(public_key, spender, value, deadline)
        signature = wallet.sign_msg(msg)
        # WHEN the permit is attempted
        # THEN it should fail due to expiration
        with self.assertRaises(Exception) as context:
            self.currency.permit(owner=public_key, spender=spender, value=value, deadline=deadline, signature=signature)
        self.assertIn('Permit has expired', str(context.exception))

    def test_permit_invalid_signature(self):
        # GIVEN a permit setup with an invalid signature
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        deadline = self.create_deadline()
        spender = "some_spender"
        value = 100
        msg = self.construct_permit_msg(public_key, spender, value, deadline)
        signature = wallet.sign_msg(msg + "tampered")
        # WHEN the permit is attempted
        # THEN it should fail due to invalid signature
        with self.assertRaises(Exception) as context:
            self.currency.permit(owner=public_key, spender=spender, value=value, deadline=deadline, signature=signature)
        self.assertIn('Invalid signature', str(context.exception))

    def test_permit_double_spending(self):
        # GIVEN a permit setup with a double spending attempt
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        deadline = self.create_deadline()
        spender = "some_spender"
        value = 100
        msg = self.construct_permit_msg(public_key, spender, value, deadline)
        signature = wallet.sign_msg(msg)
        self.currency.permit(owner=public_key, spender=spender, value=value, deadline=deadline, signature=signature)
        # WHEN the permit is used again
        # THEN it should fail due to double spending
        with self.assertRaises(Exception) as context:
            self.currency.permit(owner=public_key, spender=spender, value=value, deadline=deadline, signature=signature)
        self.assertIn('Permit can only be used once', str(context.exception))

    # XST003 / Streaming Payments

    # Helper Functions

    def create_date(self, year, month, day):
        # Helper method to create date dictionaries
        d = datetime.datetime(year, month, day)
        return Datetime(d.year, d.month, d.day, hour=d.hour, minute=d.minute)
    
    def construct_stream_permit_msg(self, sender, receiver, rate, begins, closes, deadline):
        return f"{sender}:{receiver}:{rate}:{begins}:{closes}:{deadline}:currency"

    def test_create_stream_success(self):
        # GIVEN a valid stream creation setup
        sender = 'alice'
        receiver = 'bob'
        rate = 10.0
        begins = self.create_date(2023, 1, 1)
        closes = self.create_date(2023, 12, 31)
        
        self.client.signer = sender
        # WHEN the stream is created
        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)
        # THEN the stream should be active and have correct properties
        self.assertEqual(self.currency.streams[stream_id, 'status'], 'active')
        self.assertEqual(self.currency.streams[stream_id, 'begins'], begins)
        self.assertEqual(self.currency.streams[stream_id, 'closes'], closes)
        self.assertEqual(self.currency.streams[stream_id, 'receiver'], receiver)
        self.assertEqual(self.currency.streams[stream_id, 'sender'], sender)
        self.assertEqual(self.currency.streams[stream_id, 'rate'], rate)
        self.assertEqual(self.currency.streams[stream_id, 'claimed'], 0)

    def test_create_stream_invalid_dates(self):
        # GIVEN a stream creation setup with invalid date ranges
        sender = 'alice'
        receiver = 'bob'
        rate = 10.0
        begins = self.create_date(2023, 12, 31)
        closes = self.create_date(2023, 1, 1)  # Invalid since close date is before begin date
        
        self.client.signer = sender
        # WHEN the stream is attempted to be created
        # THEN it should fail due to invalid date ranges
        with self.assertRaises(Exception):
            self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes)

    def test_create_stream_negative_rate(self):
        # GIVEN a stream creation setup with a negative rate
        sender = 'alice'
        receiver = 'bob'
        rate = -10.0  # Invalid rate
        begins = Datetime(year=2023, month=1, day=1, hour=0, minute=0)
        closes = Datetime(year=2024, month=1, day=1, hour=0, minute=0)
        
        # WHEN the stream is attempted to be created
        # THEN it should fail due to negative rate
        with self.assertRaises(Exception):
            self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

    def test_sender_can_balance_stream(self):
        # GIVEN a stream setup where the sender can balance the stream
        sender = 'alice'
        receiver = 'bob'
        begins = Datetime(year=2023, month=1, day=1, hour=0, minute=0)
        closes = Datetime(year=2024, month=1, day=1, hour=0, minute=0)
        seconds_in_period = (closes - begins).seconds
        self.currency.balances[sender] = seconds_in_period
        self.currency.balances[receiver] = 0
        rate = 1

        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN the stream is balanced by the sender
        balance_res = self.currency.balance_stream(stream_id=stream_id, signer=sender, environment={"now": closes})
        # THEN the balances should be updated correctly
        self.assertIn("Claimed", balance_res)
        self.assertEqual(self.currency.balances[receiver], seconds_in_period)
        self.assertEqual(self.currency.balances[sender], 0)

    def test_receiver_can_balance_stream(self):
        # GIVEN a stream setup where the receiver can balance the stream
        sender = 'mary'
        receiver = 'janine'
        begins = Datetime(year=2023, month=1, day=1, hour=0, minute=0)
        closes = Datetime(year=2024, month=1, day=1, hour=0, minute=0)
        seconds_in_period = (closes - begins).seconds
        self.currency.balances[sender] = seconds_in_period
        self.currency.balances[receiver] = 0

        rate = 1

        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN the stream is balanced by the receiver
        balance_res = self.currency.balance_stream(stream_id=stream_id, signer=receiver, environment={"now": closes})
        # THEN the balances should be updated correctly
        self.assertIn("Claimed", balance_res)
        self.assertEqual(self.currency.balances[receiver], seconds_in_period)
        self.assertEqual(self.currency.balances[sender], 0)

    def test_balance_stream_failure_no_amount_due(self):
        # GIVEN a stream setup where no amount is due
        sender = 'alice'
        receiver = 'bob'
        rate = 10.0
        begins = Datetime(year=2023, month=1, day=1, hour=0)
        closes = Datetime(year=2023, month=1, day=1, hour=1)
        env = {"now": begins}

        self.client.signer = sender
        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN the stream is attempted to be balanced after it closes
        # THEN it should fail due to no amount being due
        with self.assertRaises(AssertionError):
            self.currency.balance_stream(stream_id=stream_id, environment=env, signer=sender)

    def test_partial_balance_stream(self):
        # GIVEN a stream setup where only a partial balance is possible
        sender = 'mary'
        receiver = 'janine'
        begins = Datetime(year=2023, month=1, day=1, hour=0, minute=0)
        closes = Datetime(year=2024, month=1, day=1, hour=0, minute=0)
        seconds_in_period = (closes - begins).seconds
        self.currency.balances[sender] = seconds_in_period / 2
        self.currency.balances[receiver] = 0

        rate = 1

        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN the stream is balanced by the receiver
        balance_res = self.currency.balance_stream(stream_id=stream_id, signer=receiver, environment={"now": closes})
        # THEN the balances should be updated to reflect only the available amount
        self.assertIn("Claimed", balance_res)
        self.assertEqual(self.currency.balances[receiver], seconds_in_period / 2)
        self.assertEqual(self.currency.balances[sender], 0)

    def test_receiver_can_finalize_stream(self):
        # GIVEN a stream setup where the receiver can finalize the stream
        sender = 'mary'
        receiver = 'janine'
        begins = Datetime(year=2023, month=1, day=1, hour=0, minute=0)
        closes = Datetime(year=2024, month=1, day=1, hour=0, minute=0)
        seconds_in_period = (closes - begins).seconds
        self.currency.balances[sender] = seconds_in_period
        self.currency.balances[receiver] = 0

        rate = 1

        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        balance_res = self.currency.balance_stream(stream_id=stream_id, signer=receiver, environment={"now": closes})
        # WHEN the stream is finalized by the receiver
        finalize_res = self.currency.finalize_stream(stream_id=stream_id, signer=receiver, environment={"now": closes})
        # THEN the stream should be finalized and the status updated
        self.assertIn("Finalized", finalize_res)
        self.assertEqual(self.currency.streams[stream_id, 'status'], 'finalized')
        self.assertEqual(self.currency.streams[stream_id, 'claimed'], seconds_in_period)

    def test_sender_can_finalize_stream(self):
        # GIVEN a stream setup where the sender can finalize the stream
        sender = 'mary'
        receiver = 'janine'
        begins = Datetime(year=2023, month=1, day=1, hour=0, minute=0)
        closes = Datetime(year=2024, month=1, day=1, hour=0, minute=0)
        seconds_in_period = (closes - begins).seconds
        self.currency.balances[sender] = seconds_in_period
        self.currency.balances[receiver] = 0

        rate = 1

        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        balance_res = self.currency.balance_stream(stream_id=stream_id, signer=receiver, environment={"now": closes})
        # WHEN the stream is finalized by the sender
        finalize_res = self.currency.finalize_stream(stream_id=stream_id, signer=sender, environment={"now": closes})
        # THEN the stream should be finalized and the status updated
        self.assertIn("Finalized", finalize_res)
        self.assertEqual(self.currency.streams[stream_id, 'status'], 'finalized')
        self.assertEqual(self.currency.streams[stream_id, 'claimed'], seconds_in_period)

    def test_finalize_stream_fails_if_oustanding_balance(self):
        # GIVEN a stream setup where there is an outstanding balance
        sender = 'mary'
        receiver = 'janine'
        begins = Datetime(year=2023, month=1, day=1, hour=0, minute=0)
        closes = Datetime(year=2024, month=1, day=1, hour=0, minute=0)
        seconds_in_period = (closes - begins).seconds
        self.currency.balances[sender] = seconds_in_period
        self.currency.balances[receiver] = 0

        rate = 1

        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN the stream is attempted to be finalized
        # THEN it should fail due to the outstanding balance
        with self.assertRaises(Exception):
            self.currency.finalize_stream(stream_id=stream_id, signer=sender, environment={"now": closes})

        with self.assertRaises(Exception):
            self.currency.finalize_stream(stream_id=stream_id, signer=receiver, environment={"now": closes})
        
    def test_change_close_time_success(self):
        # GIVEN a stream setup where the close time can be changed
        sender = 'alice'
        receiver = 'bob'
        rate = 10.0
        begins = Datetime(year=2023, month=1, day=1, hour=0)
        closes = Datetime(year=2023, month=1, day=10, hour=0)
        new_close_time = Datetime(year=2023, month=1, day=5, hour=0)
        env = {"now": Datetime(year=2023, month=1, day=3, hour=0)}

        self.client.signer = sender
        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN the close time is changed
        result = self.currency.change_close_time(stream_id=stream_id, new_close_time=new_close_time, environment=env, signer=sender)
        # THEN the close time should be updated correctly
        self.assertIn("Changed close time of stream to", result)

        updated_close_time = self.currency.streams[stream_id, 'closes']
        self.assertEqual(updated_close_time, new_close_time)

    def test_change_close_time_before_now(self):
        # GIVEN a stream setup where the close time is attempted to be changed to a time before now
        sender = 'alice'
        receiver = 'bob'
        rate = 10.0
        begins = Datetime(year=2023, month=1, day=1, hour=0)
        closes = Datetime(year=2023, month=1, day=10, hour=0)
        new_close_time = Datetime(year=2022, month=12, day=31, hour=23)
        now = Datetime(year=2023, month=1, day=3, hour=0)
        env = {"now": now}

        self.client.signer = sender
        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN the close time is changed to a time before now
        self.currency.change_close_time(stream_id=stream_id, new_close_time=new_close_time, environment=env, signer=sender)
        # THEN the close time should be set to now
        assert self.currency.streams[stream_id, 'closes'] == now

    def test_change_close_time_before_begins(self):
        # GIVEN a stream setup where the close time is attempted to be changed to a time before it begins
        sender = 'alice'
        receiver = 'bob'
        rate = 10.0

        begins = Datetime(year=2023, month=1, day=1, hour=0)
        closes = Datetime(year=2023, month=1, day=10, hour=0)
        new_close_time = Datetime(year=2022, month=12, day=31, hour=23)
        env = {"now": Datetime(year=2021, month=1, day=3, hour=0)}

        self.client.signer = sender
        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN the close time is changed to a time before it begins
        self.currency.change_close_time(stream_id=stream_id, new_close_time=new_close_time, environment=env, signer=sender)
        # THEN the close time should be set to the begin time
        assert self.currency.streams[stream_id, 'closes'] == begins

    def test_create_stream_valid_permit(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1

        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        deadline = Datetime(year=2023, month=1, day=11)
        env = {"now": Datetime(year=2023, month=1, day=3, hour=0)}
        signature = wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))

        # WHEN
        stream_id = self.currency.create_stream_from_permit(sender=public_key, receiver=receiver, rate=rate, begins=begins, closes=closes, deadline=deadline, signature=signature, environment=env)

        # THEN
        self.assertIsNotNone(stream_id)
        self.assertEqual(self.currency.streams[stream_id, 'receiver'], receiver)
        self.assertEqual(self.currency.streams[stream_id, 'rate'], rate)
        self.assertEqual(self.currency.streams[stream_id, 'begins'], begins)
        self.assertEqual(self.currency.streams[stream_id, 'closes'], closes)

    def test_replay_create_stream_with_permit(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1

        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        deadline = Datetime(year=2023, month=1, day=11)
        signature = wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))
        now = Datetime(year=2023, month=1, day=9)
        env = {"now": now}
        # WHEN
        stream_id = self.currency.create_stream_from_permit(sender=public_key, receiver=receiver, rate=rate, begins=begins, closes=closes, deadline=deadline, signature=signature, environment=env)

        # THEN
        with self.assertRaises(Exception):
            self.currency.create_stream_from_permit(sender=public_key, receiver=receiver, rate=rate, begins=begins, closes=closes, signature=signature)

    def test_create_stream_invalid_permit(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1

        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        deadline = Datetime(year=2023, month=1, day=11)
        env = {"now": Datetime(year=2023, month=1, day=12)}
        signature = f"{wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))}:invalid"

        # WHEN / THEN
        with self.assertRaises(Exception):
            self.currency.create_stream_from_permit(sender=public_key, receiver=receiver, rate=rate, begins=begins, closes=closes, deadline=deadline, signature=signature)

    def test_create_stream_invalid_permit_wrong_sender(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1

        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        deadline = Datetime(year=2023, month=1, day=11)
        signature = f"{wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))}"

        # WHEN / THEN
        with self.assertRaises(Exception):
            self.currency.create_stream_from_permit(sender="wrong_sender", receiver=receiver, rate=rate, begins=begins, closes=closes, signature=signature)

    def test_create_stream_invalid_permit_wrong_receiver(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1

        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        deadline = Datetime(year=2023, month=1, day=11)
        signature = f"{wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))}"

        # WHEN / THEN
        with self.assertRaises(Exception):
            self.currency.create_stream_from_permit(sender=public_key, receiver="wrong_receiver", rate=rate, begins=begins, closes=closes, signature=signature)

    def test_create_stream_invalid_permit_wrong_rate(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1

        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        deadline = Datetime(year=2023, month=1, day=11)
        signature = f"{wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))}"

        # WHEN / THEN
        with self.assertRaises(Exception):
            self.currency.create_stream_from_permit(sender=public_key, receiver=receiver, rate=10, begins=begins, closes=closes, signature=signature)

    def test_create_stream_invalid_permit_wrong_begin_date(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1

        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        wrong_date = Datetime(year=2023, month=1, day=11)
        deadline = Datetime(year=2023, month=1, day=12)
        signature = f"{wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))}"

        # WHEN / THEN
        with self.assertRaises(Exception):
            self.currency.create_stream_from_permit(sender=public_key, receiver=receiver, rate=rate, begins=wrong_date, closes=closes, signature=signature)

    def test_create_stream_invalid_permit_wrong_closes_date(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1

        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        wrong_date = Datetime(year=2023, month=1, day=11)
        deadline = Datetime(year=2023, month=1, day=12)
        signature = f"{wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))}"

        # WHEN / THEN
        with self.assertRaises(Exception):
            self.currency.create_stream_from_permit(sender=public_key, receiver=receiver, rate=rate, begins=begins, closes=wrong_date, signature=signature)


    def test_create_stream_invalid_permit_expired_deadline(self):
        # GIVEN
        receiver = 'bob'
        private_key = 'ed30796abc4ab47a97bfb37359f50a9c362c7b304a4b4ad1b3f5369ecb6f7fd8'
        wallet = Wallet(private_key)
        public_key = wallet.public_key
        rate = 1
        environment={"now": Datetime(year=2023, month=1, day=13)}
        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        deadline = Datetime(year=2023, month=1, day=12)
        signature = f"{wallet.sign_msg(self.construct_stream_permit_msg(public_key, receiver, rate, begins, closes, deadline))}"

        # WHEN / THEN
        with self.assertRaises(Exception):
            self.currency.create_stream_from_permit(sender=public_key, receiver=receiver, rate=rate, begins=begins, closes=closes, deadline=deadline, signature=signature)

    def test_forfeit_stream_success(self):
        # GIVEN
        receiver = 'receiver_account'
        sender = 'sender_account'
        rate = 1
        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)

        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # WHEN
        result = self.currency.forfeit_stream(
            stream_id=stream_id,
            signer=receiver
        )

        # THEN
        self.assertEqual(self.currency.streams[stream_id, 'status'], 'forfeit')
        self.assertEqual(result, f"Forfeit stream {stream_id}")

    def test_forfeit_stream_non_existent(self):
        # GIVEN
        receiver = 'receiver_account'
        stream_id = 'non-existant-id'

        # WHEN / THEN

        with self.assertRaises(AssertionError):
            self.currency.forfeit_stream(
                stream_id=stream_id,
                signer=receiver
            )

    def test_forfeit_stream_not_active(self):
        # GIVEN
        receiver = 'receiver_account'
        stream_id = 'non-existant-id'
        sender = 'sender_account'
        rate = 1
        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)

        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)
        self.currency.streams[stream_id, 'status'] = 'finalized'

        # WHEN / THEN

        # Execute and Verify
        with self.assertRaises(AssertionError):
            self.currency.forfeit_stream(
                stream_id=stream_id,
                signer=receiver
            )

    def test_forfeit_stream_not_receiver(self):
        # GIVEN
        receiver = 'receiver_account'
        stream_id = 'non-existant-id'
        sender = 'sender_account'
        rate = 1
        begins = Datetime(year=2023, month=1, day=1)
        closes = Datetime(year=2023, month=1, day=10)
        other_user = 'other_user'

        # WHEN
        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)

        # THEN
        with self.assertRaises(AssertionError):
            self.currency.forfeit_stream(
                stream_id=stream_id,
                signer=other_user
            )

    def test_close_balance_finalize(self):
        # GIVEN a stream setup
        sender = 'alice'
        self.currency.balances[sender] = 100000000000000
        receiver = 'bob'
        rate = 10.0
        begins = self.create_date(2023, 1, 1)
        closes = self.create_date(2023, 12, 31)
        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)
        
        # WHEN close_balance_finalize is called by the sender
        self.currency.close_balance_finalize(stream_id=stream_id, signer=sender, environment={"now": closes})
        
        # THEN the stream should be closed, balanced, and finalized
        stream_status = self.currency.streams[stream_id, 'status']
        self.assertEqual(stream_status, 'finalized')
        self.assertEqual(self.currency.streams[stream_id, 'closes'], closes)
        self.assertEqual(self.currency.balances[receiver], (closes - begins).seconds * rate)

    def test_balance_finalize(self):
        # GIVEN a stream setup
        sender = 'alice'
        self.currency.balances[sender] = 100000000000000
        receiver = 'bob'
        rate = 1
        begins = self.create_date(2023, 1, 1)
        closes = self.create_date(2023, 12, 31)
        stream_id = self.currency.create_stream(receiver=receiver, rate=rate, begins=begins, closes=closes, signer=sender)
        
        # WHEN balance_finalize is called by the receiver
        self.currency.balance_finalize(stream_id=stream_id, signer=receiver, environment={"now": closes})
        
        # THEN the stream should be balanced and finalized
        stream_status = self.currency.streams[stream_id, 'status']
        self.assertEqual(stream_status, 'finalized')
        self.assertEqual(self.currency.balances[receiver], (closes - begins).seconds * rate)

if __name__ == "__main__":
    unittest.main()
