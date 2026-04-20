"""Organizations endpoint helpers.

Implements:
- GET /v3/Organizations (list)
- GET /v3/Organizations/{Organizationkey} (single)
- PUT /v3/Organizations/{Organizationkey} (full update)
- PATCH /v3/Organizations/{Organizationkey} (partial update: FullName only)

Notes:
- List Organizations supports OData query options such as $filter/$orderby/$top/$skip and may return @odata.nextLink for pagination.
- Single Organization supports $expand (e.g. BusinessCards, Contacts, ClientTeam).
- PUT supports $expand to update BusinessCards alongside the Organization.

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


def get_organization(
    client: KarbonClient,
    organization_key: str,
    *,
    expand: Optional[ExpandType] = None,
) -> Dict[str, Any]:
    """Get an Organization by key (GET /v3/Organizations/{Organizationkey}).

    expand can be a comma-separated string or a list/tuple/set of properties.
    Examples:
      - expand='Contacts,BusinessCards'
      - expand=['Contacts', 'BusinessCards']
    """
    params: Dict[str, Any] = {}
    exp = _expand_param(expand)
    if exp:
        params["$expand"] = exp

    url = client.url(f"/v3/Organizations/{organization_key}")
    return client.request("GET", url, params=params if params else None)


def list_organizations(
    client: KarbonClient,
    *,
    filter_: Optional[str] = None,
    orderby: Optional[str] = None,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """GET /v3/Organizations (paged list).

    Pass raw OData in filter_ (e.g. "FullName eq 'Sample Company'").
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

    url = client.url("/v3/Organizations")
    return client.request("GET", url, params=params if params else None)


def iter_organizations(
    client: KarbonClient,
    *,
    filter_: Optional[str] = None,
    orderby: Optional[str] = None,
    top: int = 100,
    extra_params: Optional[Dict[str, Any]] = None,
    max_pages: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield Organizations across pages using @odata.nextLink when present."""
    pages = 0
    resp = list_organizations(
        client, filter_=filter_, orderby=orderby, top=top, extra_params=extra_params
    )
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


def build_organizations_filter(
    *,
    full_name: Optional[str] = None,
    email_address: Optional[str] = None,
    contact_type_eq: Optional[str] = None,
    contact_type_contains: Optional[str] = None,
) -> Optional[str]:
    """Build a common $filter expression for /v3/Organizations.

    Examples produced:
      - FullName eq 'Sample Company'
      - EmailAddress eq 'info@samplecompany.com'
      - ContactType eq 'Prospect'
      - contains(ContactType, 'Client')

    Multiple expressions are combined with ' and '.
    Returns None if no inputs were provided.
    """
    parts = []
    if full_name is not None:
        parts.append(f"FullName eq '{full_name}'")
    if email_address is not None:
        parts.append(f"EmailAddress eq '{email_address}'")
    if contact_type_eq is not None:
        parts.append(f"ContactType eq '{contact_type_eq}'")
    if contact_type_contains is not None:
        parts.append(f"contains(ContactType, '{contact_type_contains}')")
    if not parts:
        return None
    return " and ".join(parts)


def update_organization_full(
    client: KarbonClient,
    organization_key: str,
    payload: Dict[str, Any],
    *,
    expand: Optional[ExpandType] = None,
) -> Dict[str, Any]:
    """Full update of an Organization (PUT /v3/Organizations/{Organizationkey}).

    If you include BusinessCards in the payload and you are updating existing cards,
    include required identifiers (e.g. BusinessCardKey/EntityType/EntityKey) per Karbon docs
    to avoid removing existing cards.

    Use expand='BusinessCards' (or ['BusinessCards']) if you want to update BusinessCards
    via this request.
    """
    params: Dict[str, Any] = {}
    exp = _expand_param(expand)
    if exp:
        params["$expand"] = exp

    url = client.url(f"/v3/Organizations/{organization_key}")
    return client.request("PUT", url, params=params if params else None, json=payload)


def update_organization_fullname(
    client: KarbonClient,
    organization_key: str,
    full_name: str,
) -> Dict[str, Any]:
    """Partial update of an Organization (PATCH /v3/Organizations/{Organizationkey}).

    This PATCH endpoint only supports editing the FullName property.
    """
    url = client.url(f"/v3/Organizations/{organization_key}")
    return client.request("PATCH", url, json={"FullName": full_name})
