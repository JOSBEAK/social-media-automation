import unittest

from src.services.csv_account_parser import AccountCsvError, parse_account_csv


class AccountCsvTests(unittest.TestCase):
    def test_only_requires_username_and_password(self):
        accounts = parse_account_csv(
            b"Username, Password,notes\nalice,secret,first\nbob,p@ss,second\n", 10
        )
        self.assertEqual([account.username for account in accounts], ["alice", "bob"])
        self.assertEqual(accounts[0].password, "secret")

    def test_rejects_duplicate_usernames(self):
        with self.assertRaisesRegex(AccountCsvError, "duplicates"):
            parse_account_csv(b"username,password\nAlice,one\nalice,two\n", 10)

    def test_rejects_missing_headers(self):
        with self.assertRaisesRegex(AccountCsvError, "requires"):
            parse_account_csv(b"email,secret\na@example.com,password\n", 10)


if __name__ == "__main__":
    unittest.main()
