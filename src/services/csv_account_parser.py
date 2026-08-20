import csv
import io
from dataclasses import dataclass


class AccountCsvError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedAccount:
    username: str
    password: str


def parse_account_csv(content: bytes, max_accounts: int) -> list[ParsedAccount]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AccountCsvError("CSV must use UTF-8 encoding") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise AccountCsvError("CSV must have a username,password header row")

    normalized = {name.strip().lower(): name for name in reader.fieldnames if name}
    missing = {"username", "password"} - normalized.keys()
    if missing:
        raise AccountCsvError("CSV requires username and password columns")

    accounts = []
    seen = set()
    for row_number, row in enumerate(reader, start=2):
        username = (row.get(normalized["username"]) or "").strip()
        password = row.get(normalized["password"]) or ""
        if not username or not password:
            raise AccountCsvError(f"Row {row_number} has an empty username or password")
        canonical_username = username.casefold()
        if canonical_username in seen:
            raise AccountCsvError(f"Row {row_number} duplicates username '{username}'")
        seen.add(canonical_username)
        accounts.append(ParsedAccount(username, password))
        if len(accounts) > max_accounts:
            raise AccountCsvError(f"CSV exceeds the {max_accounts} account limit")

    if not accounts:
        raise AccountCsvError("CSV contains no account rows")
    return accounts
