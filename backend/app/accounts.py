from typing import Annotated

from fastapi import Header, HTTPException
from pydantic import BaseModel


class AccountProfile(BaseModel):
    """A business that can sign in; its id is also its account id in the forecast service."""

    id: str
    business_name: str
    description: str


# Add new demo businesses here, in the frontend's account list and in the forecast service's data.
ACCOUNTS: dict[str, AccountProfile] = {
    "amalfi": AccountProfile(
        id="amalfi",
        business_name="Pizzeria Amalfi",
        description="a small restaurant in Frankfurt owned by Vincenzo Amalfi",
    ),
}


def get_account(x_account_id: Annotated[str | None, Header()] = None) -> AccountProfile:
    """FastAPI dependency: the signed-in business, as forwarded by the frontend server.

    The frontend checks the login and sets `X-Account-Id`; the browser never calls this API directly.

    Args:
        x_account_id: Account id from the `X-Account-Id` header.

    Returns:
        The account profile.
    """
    if x_account_id is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    account = ACCOUNTS.get(x_account_id)
    if account is None:
        raise HTTPException(status_code=403, detail="This account is not known.")
    return account
