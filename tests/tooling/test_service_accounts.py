"""service_accounts: the commit author address that GitLab gives a service account."""

import pytest

from scripts.service_accounts import is_service_account_email

REAL = "service_account_group_121124982_0a7e3460f6bd9f9f7cd1423796afd526@noreply.gitlab.com"


def test_the_address_of_a_duo_service_account_is_recognized() -> None:
    assert is_service_account_email(REAL)
    assert is_service_account_email(f"  {REAL.upper()} ")


@pytest.mark.parametrize(
    "email",
    [
        "agustin.tdc@gmail.com",
        "service_account_group_1_abc@example.com",
        "service_account_group_1_abc@noreply.gitlab.com.evil.io",
        "x.service_account_group_1_abc@noreply.gitlab.com",
        "service_account_@noreply.gitlab.com",
        "",
    ],
)
def test_other_addresses_are_not(email: str) -> None:
    assert not is_service_account_email(email)
