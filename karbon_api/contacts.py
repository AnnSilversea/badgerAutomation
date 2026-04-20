"""Contacts endpoint helpers.

Implements:
- GET /v3/Contacts (list)
- GET /v3/Contacts/{Contactkey} (single)
- PUT /v3/Contacts/{Contactkey} (full update)
- PATCH /v3/Contacts/{Contactkey} (partial update: limited fields)

Notes:
- List endpoints in Karbon API follow OData patterns ($filter/$orderby/$top/$skip and @odata.nextLink).
- Single Contact supports $expand (allowed: BusinessCards, ClientTeam).
- PUT supports $expand to update BusinessCards alongside the Contact.
- PATCH supports updating only: FirstName, MiddleName, LastName, PreferredName, Salutation, Suffix.

Docs: https://karbonhq.github.io/karbon-api-reference/
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional, Sequence, Union

from .client import KarbonClient

ExpandType = Union[str, Sequence[str]]


def _expand_param(expand: Optional[ExpandType]) -> Optional[str]:
    """Normalize expand parameter to a comma-separated string."""
    if not expand:
        return None
    if isinstance(expand, (list, tuple, set)):
        return ",".join(expand)
    return str(expand)


def get_contact(
    client: KarbonClient,
    contact_key: str,
    *,
    expand: Optional[ExpandType] = None,
) -> Dict[str, Any]:
    """Get a Contact by Contactkey.

    expand can be:
      - 'BusinessCards'
      - 'ClientTeam'
      - 'BusinessCards,ClientTeam'
      - or a list/tuple/set like ['BusinessCards', 'ClientTeam']
    """
    params: Dict[str, Any] = {}
    exp = _expand_param(expand)
    if exp:
        params["$expand"] = exp

    url = client.url(f"/v3/Contacts/{contact_key}")
    return client.request("GET", url, params=params if params else None)


def list_contacts(
    client: KarbonClient,
    *,
    filter_: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """GET /v3/Contacts (paged list).

    Pass raw OData in filter_ (e.g. "FullName eq 'Sample'" or "(contains(EmailAddress, 'sample@'))").
    """
    params: Dict[str, Any] = {}
    if filter_:
        params["$filter"] = filter_
    if orderby:
        params["$orderby"] = orderby
    if top is not None:
        params["$top"] = int(top)
    if skip is not None:
        params["$skip"] = int(skip)
    if extra_params:
        params.update(extra_params)

    url = client.url("/v3/Contacts")
    return client.request("GET", url, params=params if params else None)


def iter_contacts(
    client: KarbonClient,
    *,
    filter_: Optional[str] = None,
    orderby: Optional[str] = None,
    top: int = 100,
    extra_params: Optional[Dict[str, Any]] = None,
    max_pages: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield Contacts across pages using @odata.nextLink when present."""
    pages = 0
    resp = list_contacts(client, filter_=filter_, orderby=orderby, top=top, extra_params=extra_params)
    while True:
        pages += 1
        items = resp.get("value") or resp.get("values") or []
        for item in items:
            yield item

        next_link = resp.get("@odata.nextLink")
        if not next_link:
            break
        if max_pages is not None and pages >= max_pages:
            break
        resp = client.request("GET", next_link)


def build_contacts_filter(
    *,
    full_name_eq: Optional[str] = None,
    full_name_contains: Optional[str] = None,
    email_eq: Optional[str] = None,
    email_contains: Optional[str] = None,
    phone_eq: Optional[str] = None,
    phone_contains: Optional[str] = None,
    contact_type_eq: Optional[str] = None,
) -> Optional[str]:
    """Build a common $filter expression for /v3/Contacts.

    Creates expressions using eq / contains and combines them with ' and '.
    Returns None if no inputs were provided.

    Examples produced:
      FullName eq 'Sample Management Team'
      (contains(EmailAddress, 'sample@'))
      PhoneNumber eq '1234567890' and (contains(FullName, 'Management Team'))
    """
    parts = []
    if full_name_eq is not None:
        parts.append(f"FullName eq '{full_name_eq}'")
    if full_name_contains is not None:
        parts.append(f"(contains(FullName, '{full_name_contains}'))")
    if email_eq is not None:
        parts.append(f"EmailAddress eq '{email_eq}'")
    if email_contains is not None:
        parts.append(f"(contains(EmailAddress, '{email_contains}'))")
    if phone_eq is not None:
        parts.append(f"PhoneNumber eq '{phone_eq}'")
    if phone_contains is not None:
        parts.append(f"(contains(PhoneNumber, '{phone_contains}'))")
    if contact_type_eq is not None:
        parts.append(f"ContactType eq '{contact_type_eq}'")
    if not parts:
        return None
    return " and ".join(parts)


def update_contact_full(
    client: KarbonClient,
    contact_key: str,
    payload: Dict[str, Any],
    *,
    expand: Optional[ExpandType] = None,
) -> Dict[str, Any]:
    """Full update of a Contact (PUT /v3/Contacts/{Contactkey}).

    Use $expand (e.g. expand='BusinessCards') if you want to update BusinessCards in the same request.

    IMPORTANT: When updating existing BusinessCards, include BusinessCardKey, EntityType and EntityKey
    for each existing card to avoid removing the card and any associated Client Requests.
    """
    params: Dict[str, Any] = {}
    exp = _expand_param(expand)
    if exp:
        params["$expand"] = exp

    url = client.url(f"/v3/Contacts/{contact_key}")
    return client.request("PUT", url, params=params if params else None, json=payload)


_PATCH_ALLOWED_FIELDS = {
    "FirstName",
    "MiddleName",
    "LastName",
    "PreferredName",
    "Salutation",
    "Suffix",
}


def update_contact_partial(
    client: KarbonClient,
    contact_key: str,
    changes: Dict[str, Any],
    *,
    strict: bool = True,
) -> Dict[str, Any]:
    """Partial update of a Contact (PATCH /v3/Contacts/{Contactkey}).

    This endpoint supports editing ONLY these properties:
    FirstName, MiddleName, LastName, PreferredName, Salutation, Suffix.

    If strict=True (default), this function will raise ValueError if you pass any other fields.
    If strict=False, it will silently drop unsupported fields.
    """
    if strict:
        unsupported = set(changes.keys()) - _PATCH_ALLOWED_FIELDS
        if unsupported:
            raise ValueError(
                "PATCH /v3/Contacts only supports: "
                + ", ".join(sorted(_PATCH_ALLOWED_FIELDS))
                + f". Unsupported: {', '.join(sorted(unsupported))}"
            )
        payload = changes
    else:
        payload = {k: v for k, v in changes.items() if k in _PATCH_ALLOWED_FIELDS}

    url = client.url(f"/v3/Contacts/{contact_key}")
    return client.request("PATCH", url, json=payload)
