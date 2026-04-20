"""WorkItems endpoint helpers.

Implements:
- GET /v3/WorkItems (list)
- GET /v3/WorkItems/{WorkItemKey} (single)
- iterator with OData nextLink pagination
- PUT /v3/WorkItems/{WorkItemKey} (full update)
- PATCH /v3/WorkItems/{WorkItemKey} (partial update)

Notes:
- List endpoints in Karbon API follow OData patterns ($filter/$orderby/$top/$skip and @odata.nextLink).
- PATCH supports updating only Description and DeadlineDate (per endpoint docs).
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from .client import KarbonClient


def list_workitems(
    client: KarbonClient,
    *,
    top: Optional[int] = None,
    skip: Optional[int] = None,
    orderby: Optional[str] = None,
    filter_: Optional[str] = None,
    expand: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """GET /v3/WorkItems with common OData query options."""
    url = client.url("/v3/WorkItems")
    params: Dict[str, Any] = {}

    if top is not None:
        params["$top"] = int(top)
    if skip is not None:
        params["$skip"] = int(skip)
    if orderby:
        params["$orderby"] = orderby
    if filter_:
        params["$filter"] = filter_
    if expand:
        params["$expand"] = expand
    if extra_params:
        params.update(extra_params)

    return client.request("GET", url, params=params if params else None)


def get_workitem(
    client: KarbonClient,
    workitem_key: str,
) -> Dict[str, Any]:
    """GET /v3/WorkItems/{WorkItemKey} - get a single Work Item by key."""
    url = client.url(f"/v3/WorkItems/{workitem_key}")
    return client.request("GET", url)


def iter_workitems(
    client: KarbonClient,
    *,
    top: int = 100,
    orderby: Optional[str] = None,
    filter_: Optional[str] = None,
    expand: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
    max_pages: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """Iterate through work items using @odata.nextLink if present."""
    pages = 0
    resp = list_workitems(
        client,
        top=top,
        orderby=orderby,
        filter_=filter_,
        expand=expand,
        extra_params=extra_params,
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


def update_workitem_full(
    client: KarbonClient,
    workitem_key: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """PUT /v3/WorkItems/{WorkItemKey} - full update of a Work Item."""
    url = client.url(f"/v3/WorkItems/{workitem_key}")
    return client.request("PUT", url, json=payload)


_PATCH_ALLOWED_FIELDS = {"Description", "DeadlineDate"}


def update_workitem_partial(
    client: KarbonClient,
    workitem_key: str,
    changes: Dict[str, Any],
    *,
    strict: bool = True,
) -> Dict[str, Any]:
    """PATCH /v3/WorkItems/{WorkItemKey} - partial update.

    Allowed fields: Description, DeadlineDate.

    If strict=True (default), raise ValueError for unsupported fields.
    If strict=False, drop unsupported fields.
    """
    if strict:
        unsupported = set(changes.keys()) - _PATCH_ALLOWED_FIELDS
        if unsupported:
            raise ValueError(
                "PATCH /v3/WorkItems only supports: "
                + ", ".join(sorted(_PATCH_ALLOWED_FIELDS))
                + f". Unsupported: {', '.join(sorted(unsupported))}"
            )
        payload = changes
    else:
        payload = {k: v for k, v in changes.items() if k in _PATCH_ALLOWED_FIELDS}

    url = client.url(f"/v3/WorkItems/{workitem_key}")
    return client.request("PATCH", url, json=payload)