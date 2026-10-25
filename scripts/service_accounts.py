"""How a GitLab service account shows up as a commit author.

A Duo flow's commits are authored by an address like
``service_account_group_<id>_<hash>@noreply.gitlab.com`` (the committer is the person who
triggered the flow). The address is forgeable, so it is a second signal, never the only one: the
user of the pipeline decides who pushed, and this only adds a reason to hold or to fail.
"""

from __future__ import annotations

import re

SERVICE_ACCOUNT_EMAIL = re.compile(r"service_account_[a-z0-9_]+@noreply\.gitlab\.com")


def is_service_account_email(email: str) -> bool:
    """Whether ``email`` is the address GitLab gives a service account."""
    return SERVICE_ACCOUNT_EMAIL.fullmatch(email.strip().lower()) is not None
