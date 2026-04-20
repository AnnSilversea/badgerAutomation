"""email_service.py

Reusable email sender for FastAPI.

Usage (sync):
    from email_service import send_email
    send_email(to_email, subject, html_body)

Usage (async):
    from email_service import send_email_async
    await send_email_async(to_email, subject, html_body)

Usage (FastAPI BackgroundTasks):
    background_tasks.add_task(send_email, to_email, subject, html_body)

Configuration via environment variables:
    SMTP_HOST (default: smtp.office365.com)
    SMTP_PORT (default: 587)
    SMTP_USER (required)
    SMTP_PASS (required)
    SMTP_FROM (default: SMTP_USER)

Notes:
- Uses STARTTLS.
- Sends HTML by default, with optional plain-text fallback.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
from email.mime.text import MIMEText
import re
from typing import Any, Dict, List, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class SMTPConfig:
    host: str = os.getenv("SMTP_HOST", "smtp.office365.com")
    port: int = int(os.getenv("SMTP_PORT", "587"))
    user: str = os.getenv("SMTP_USER", "")
    password: str = os.getenv("SMTP_PASS", "")
    from_email: str = os.getenv("SMTP_FROM", "")  # if empty, use user

    def validate(self) -> None:
        missing = []
        if not self.user:
            missing.append("SMTP_USER")
        if not self.password:
            missing.append("SMTP_PASS")
        if missing:
            raise ValueError(f"Missing required env var(s): {', '.join(missing)}")


def _build_message(
    config: SMTPConfig,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    attachments: Optional[List[str]] = None,
) -> MIMEMultipart:
    if attachments:
        msg = MIMEMultipart("mixed")
        msg_body = MIMEMultipart("alternative")
        msg.attach(msg_body)
    else:
        msg = MIMEMultipart("alternative")
        msg_body = msg

    msg["From"] = config.from_email or config.user
    msg["To"] = to_email
    msg["Subject"] = subject

    # Plain text part first (optional)
    if text_body:
        msg_body.attach(MIMEText(text_body, "plain", "utf-8"))

    # HTML part
    msg_body.attach(MIMEText(html_body, "html", "utf-8"))

    # Attachments
    if attachments:
        for filepath in attachments:
            if not filepath or not os.path.isfile(filepath):
                continue
            
            ctype, encoding = mimetypes.guess_type(filepath)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            
            maintype, subtype = ctype.split("/", 1)
            
            with open(filepath, "rb") as f:
                part = MIMEBase(maintype, subtype)
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(filepath)}"')
            msg.attach(part)

    return msg


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    config: Optional[SMTPConfig] = None,
    timeout: int = 30,
    attachments: Optional[List[str]] = None,
) -> None:
    """Send an email via SMTP (blocking).

    Designed to be used in BackgroundTasks or inside asyncio.to_thread.
    """
    cfg = config or SMTPConfig()
    cfg.validate()

    msg = _build_message(cfg, to_email, subject, html_body, text_body, attachments)

    with smtplib.SMTP(cfg.host, cfg.port, timeout=timeout) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(cfg.user, cfg.password)
        server.send_message(msg)


async def send_email_async(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    config: Optional[SMTPConfig] = None,
    timeout: int = 30,
    attachments: Optional[List[str]] = None,
) -> None:
    """Async wrapper around send_email."""
    await asyncio.to_thread(send_email, to_email, subject, html_body, text_body, config, timeout, attachments)



def compute_efile_totals_from_details(
    details: List[Dict[str, Any]],
    karbon_update_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Compute correct email totals from per-record details.
    Rules:
      SUCCESS + karbon updated -> updated
      SUCCESS but karbon unchanged -> processed (ineligible, etc.)
      CLIENT_NOT_FOUND / missing_registration_number -> skipped
      ERROR (result==failed) -> failed_drake
      SUCCESS + karbon update failed -> failed_karbon
    """
    karbon = karbon_update_result or {}
    updated = int(karbon.get("updated") or 0)
    failed_karbon = int(karbon.get("failed") or 0)
    failed_drake = 0
    skipped = 0
    processed_ok = 0  # SUCCESS but no karbon update (ineligible)

    # Build set of workItemKeys that were in updates (we tried to update Karbon)
    karbon_details = karbon.get("details") or []
    updated_keys = {str(d.get("workItemKey")) for d in karbon_details if d.get("status") == "updated"}
    failed_karbon_keys = {str(d.get("workItemKey")) for d in karbon_details if d.get("status") == "failed"}

    for d in details or []:
        result = d.get("result", "")
        reason = d.get("reason", "")
        key = str(d.get("workItemKey", ""))

        if result == "failed":
            failed_drake += 1
        elif result == "skipped" and reason in ("client_not_found", "missing_registration_number"):
            skipped += 1
        elif result == "successful":
            if key in updated_keys:
                pass  # already counted in updated
            elif key in failed_karbon_keys:
                pass  # already counted in failed_karbon
            else:
                processed_ok += 1  # ineligible, no karbon update needed

    processed = len(details or [])
    return {
        "processed": processed,
        "updated": updated,
        "failed_drake": failed_drake,
        "failed_karbon": failed_karbon,
        "skipped": skipped,
    }


def build_efile_status_summary_email(
    *,
    totals: dict,
    processed_count: int,
    details: Optional[List[Dict[str, Any]]] = None,
) -> tuple[str, str, str]:

    """
    Build subject + HTML + TEXT for endpoint email.
    Includes masked details table.
    """
    subject = "[Badger] EFile Status Sync from Drake to Karbon"

    #  Mask details before rendering
    safe_details = mask_details(details or [])

    details_html, details_text = render_details_for_email(safe_details, max_rows=50)

    html = f"""
    <h3> EFile Status Sync from Drake to Karbon</h3>
    <p><b>Summary</b></p>
    <ul>
    <li><strong>Processed:</strong> {processed_count}</li>
    <li style="color: green;"><strong>Updated:</strong> {totals.get('updated', 0)}</li>
    <li style="color: red;"><strong>Drake RPA Failed:</strong> {totals.get('failed_drake', 0)}</li>
    <li style="color: red;"><strong>Fail Updating Karbon:</strong> {totals.get('failed_karbon', 0)}</li>
    <li><strong>Skipped:</strong> {totals.get('skipped', 0)}</li>
    </ul>
    <p><b>Details:</b></p>
    {details_html}
    <p>Please open Karbon to review item-level details.</p>
    """


    text = (
        "E-file Processing Completed\n"
        f"Processed: {processed_count}\n"
        f"Updated: {totals.get('updated', 0)}\n"
        f"Drake RPA Failed: {totals.get('failed_drake', 0)}\n"
        f"Fail Updating Karbon: {totals.get('failed_karbon', 0)}\n"
        f"Skipped: {totals.get('skipped', 0)}\n"
        + "\n"
        + details_text
    )

    return subject, html, text


SENSITIVE_KEYWORDS = {
    "registrationnumber", "ssn", "ein", "taxid", "tin", "clientid",
    "registration_number", "tax_id", "tax_id_number", "idnumber", "id_number"
}

def mask_id_last4(value: Any, keep_last: int = 4, mask_char: str = "•") -> Any:
    """
    Mask ID-like strings: keep only last N digits, preserve non-digit formatting.
    Examples:
      "74-2774583" -> "••-•••4583"
      "400-00-1032" -> "•••-••-1032"
      "927580441" -> "•••••0441"
      None -> None
    """
    if value is None:
        return None
    if not isinstance(value, str):
        # If it's numeric (int), cast to str and mask; else return as-is
        if isinstance(value, (int, float)):
            value = str(int(value))
        else:
            return value

    digits = re.findall(r"\d", value)
    if not digits:
        return value  # nothing to mask

    total_digits = len(digits)
    unmasked = digits[-keep_last:] if total_digits >= keep_last else digits[:]
    masked_count = max(total_digits - len(unmasked), 0)

    # build a masked digit stream, then re-insert into original format
    masked_digits = [mask_char] * masked_count + unmasked
    it = iter(masked_digits)

    out_chars = []
    for ch in value:
        if ch.isdigit():
            out_chars.append(next(it))
        else:
            out_chars.append(ch)

    return "".join(out_chars)

def mask_details(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mask sensitive IDs inside details list.
    Only last 4 digits are shown for SSN/EIN/Tax ID fields.
    """
    def is_sensitive_key(key: str) -> bool:
        k = (key or "").lower().replace("-", "_")
        return (
            k in SENSITIVE_KEYWORDS
            or "ssn" in k
            or "ein" in k
            or "tax" in k
            or "tin" in k
            or "registration" in k
        )

    masked: List[Dict[str, Any]] = []

    for item in details:
        if not isinstance(item, dict):
            masked.append(item)
            continue

        new_item: Dict[str, Any] = {}
        for k, v in item.items():
            if is_sensitive_key(k):
                new_item[k] = mask_id_last4(v)
            else:
                # OPTIONAL: if the value is a string but contains a long ID (>=6 digits)
                if isinstance(v, str):
                    digits = re.findall(r"\d", v)
                    if len(digits) >= 6:
                        new_item[k] = mask_id_last4(v)
                    else:
                        new_item[k] = v
                else:
                    new_item[k] = v

        masked.append(new_item)

    return masked

def _escape_html(s: Optional[str]) -> str:
    if s is None:
        return ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )

def render_details_for_email(details: List[Dict[str, Any]], max_rows: int = 50) -> Tuple[str, str]:
    details = details or []
    shown = details[:max_rows]

    excluded_cols = {"workItemKey", "reason",} 

    preferred_cols = [
        "registrationNumber",
        "client",
        "drake_status",
        "result",
        "error",
    ]

    header_labels = {
    "drake_status": "E-file Status",
    "registrationNumber": "SSN",
    "client": "Client",
    "result": "Result",
    "error": "Error",
    }

    cols = []
    seen = set()

    for c in preferred_cols:
        if c in excluded_cols:
            continue
        if any(isinstance(r, dict) and c in r for r in shown):
            cols.append(c); seen.add(c)

    for r in shown:
        if not isinstance(r, dict):
            continue
        for k in r.keys():
            if k in excluded_cols:
                continue
            if k not in seen:
                cols.append(k); seen.add(k)

    if not shown:
        html = "<p><b>Details:</b> (no item-level details)</p>"
        text = "Details: (no item-level details)"
        return html, text

    thead = "".join(
        f"<th style='text-align:left;border:1px solid #ddd;padding:6px'>"
        f"{_escape_html(header_labels.get(c, c))}"
        f"</th>"
        for c in cols
    )

    rows_html = []
    text_lines = []

    text_header = " | ".join(header_labels.get(c, c) for c in cols)
    text_lines.append(text_header)
    text_lines.append("-" * len(text_header))

    for item in shown:
        if not isinstance(item, dict):
            continue
        tds = []
        vals = []
        for c in cols:
            val = item.get(c)

            if c == "result" and isinstance(val, str):
                val_lower = val.lower()
                if val_lower == "failed_karbon":
                    val = "Failed Karbon"
                elif val_lower == "failed_drake" or val_lower == "failed":
                    val = "Failed Drake"
                elif val_lower == "updated":
                    val = "Updated"
                elif val_lower == "skipped":
                    val = "Skipped"
                elif val_lower == "successful":
                    val = "Success"

            s_val = str(val) if val is not None else ""
            tds.append(f"<td style='border:1px solid #ddd;padding:6px'>{_escape_html(s_val)}</td>")
            vals.append(s_val)
        rows_html.append(f"<tr>{''.join(tds)}</tr>")
        text_lines.append(" | ".join(vals))

    tbody = "".join(rows_html)
    table_html = (
        f"<table style='border-collapse:collapse;width:100%;font-size:12px;font-family:Arial,sans-serif'>"
        f"<thead><tr style='background-color:#f4f4f4'>{thead}</tr></thead>"
        f"<tbody>{tbody}</tbody>"
        f"</table>"
    )

    if len(details) > max_rows:
        msg = f"<p><i>... showing {max_rows} of {len(details)} items ...</i></p>"
        table_html += msg
        text_lines.append(f"... showing {max_rows} of {len(details)} items ...")

    return table_html, "\n".join(text_lines)

def build_ocr_completion_email(
    *,
    client_id: str,
    client_name: str,
    form_type: str,
    job_id: str,
) -> tuple[str, str, str]:
    """
    Build subject + HTML + TEXT for OCR completion email.
    """
    subject = "[Badger] Extract Tax Return Package from Drake"

    html = f"""
    <h3>Extract Tax Return Package from Drake</h3>
    <p>The OCR process for the following client has completed successfully.</p>
    <ul>
        <li><b>Client Name:</b> {_escape_html(client_name)}</li>
        <li><b>Client ID:</b>  *****{_escape_html(client_id[-4:])}</li>
        <li><b>Form Type:</b> {_escape_html(form_type)}</li>
        <li><b>File Name:</b> {_escape_html(job_id)}</li>
    </ul>
    """

    text = (
        "Extract Tax Return Package from Drake\n\n"
        f"Client Name: {client_name}\n"
        f"Client ID: {mask_id_last4(client_id)}\n"
        f"Form Type: {form_type}\n"
        f"File Name: {job_id}\n\n"
    )

    return subject, html, text

def render_ef_batch_details_for_email(details: List[Dict[str, Any]]) -> Tuple[str, str]:
    if not details:
        return "<p>(No item-level details)</p>", "(No item-level details)"

    # Headers for the table
    headers = ["Client ID", "Client Name","Status", "Message"]
    keys = ["clientId", "clientName","status", "message"]

    # HTML table
    thead_html = "".join(f"<th style='text-align:left;border:1px solid #ddd;padding:6px'>{_escape_html(h)}</th>" for h in headers)
    
    rows_html = []
    for item in details:
        tds = []
        for k in keys:
            val = str(item.get(k, ''))
            style = ""
            if k == 'status':
                style = f"color: {'green' if val.lower() == 'success' else 'red'}; font-weight: bold;"
            tds.append(f"<td style='border:1px solid #ddd;padding:6px; {style}'>{_escape_html(val)}</td>")
        rows_html.append(f"<tr>{''.join(tds)}</tr>")

    tbody_html = "".join(rows_html)
    table_html = (
        f"<table style='border-collapse:collapse;width:100%;font-size:12px;font-family:Arial,sans-serif'>"
        f"<thead><tr style='background-color:#f4f4f4'>{thead_html}</tr></thead>"
        f"<tbody>{tbody_html}</tbody>"
        f"</table>"
    )

    # Plain text table
    text_lines = [" | ".join(headers), "-" * (len(" | ".join(headers)) + 2)]
    for item in details:
        vals = [str(item.get(k, '')) for k in keys]
        text_lines.append(" | ".join(vals))
    
    text_table = "\n".join(text_lines)

    return table_html, text_table

def build_efile_batch_summary_email(
    *,
    totals: dict,
    details: Optional[List[Dict[str, Any]]] = None,
) -> tuple[str, str, str]:
    """
    Build subject + HTML + TEXT for the Drake EF Batch processing summary.
    """
    subject = "[Badger] Drake File Extension Processing Summary"
    
    safe_details = mask_details(details or [])

    details_html, details_text = render_ef_batch_details_for_email(safe_details)

    total = totals.get('total', 0)
    success = totals.get('success', 0)
    failed_drake = totals.get('failed_drake', totals.get('failed', 0))
    failed_karbon = totals.get('failed_karbon', 0)

    html = f"""
    <h3>Drake File Extension Processing Summary</h3>
    <p><b>Summary</b></p>
    <ul>
        <li><strong>Total Processed:</strong> {total}</li>
        <li style="color: green;"><strong>Success:</strong> {success}</li>
        <li style="color: red;"><strong>Drake RPA Failed:</strong> {failed_drake}</li>
        <li style="color: red;"><strong>Fail Updating Karbon:</strong> {failed_karbon}</li>
    </ul>
    <p><b>Details:</b></p>
    {details_html}
    """

    text = (
        "Drake File Extension Processing Summary\n\n"
        f"Total Processed: {total}\n"
        f"Success: {success}\n"
        f"Drake RPA Failed: {failed_drake}\n"
        f"Fail Updating Karbon: {failed_karbon}\n\n"
        "Details:\n"
        + details_text
    )

    return subject, html, text

def build_fi_processing_summary_email(
    *,
    processed_count: int,
    totals: dict,
    details: Optional[List[Dict[str, Any]]] = None,
) -> tuple[str, str, str]:
    """
    Build subject + HTML + TEXT for FI processing email.
    """
    subject = "[Badger] Filing Instructions Updated from Drake to Karbon"
    
    details_html = ""
    details_text = ""
    
    if details:
        rows = []
        text_lines = []
        for item in details:
            client = item.get("client", "Unknown")
            masked_ssn = mask_id_last4(item.get("registrationNumber")) or ""
            status = item.get("status", "")
            msg = item.get("message", "")
            
            rows.append(f"<tr><td style='border:1px solid #ddd;padding:6px'>{_escape_html(str(masked_ssn))}</td><td style='border:1px solid #ddd;padding:6px'>{_escape_html(str(client))}</td><td style='border:1px solid #ddd;padding:6px'>{_escape_html(str(status))}</td><td style='border:1px solid #ddd;padding:6px'>{_escape_html(str(msg))}</td></tr>")
            text_lines.append(f"{masked_ssn} | {client} | {status} | {msg}")
            
        details_html = f"""
        <table style='border-collapse:collapse;width:100%;font-size:12px;font-family:Arial,sans-serif'>
        <thead><tr style='background-color:#f4f4f4'><th style='border:1px solid #ddd;padding:6px'>SSN</th><th style='border:1px solid #ddd;padding:6px'>Client</th><th style='border:1px solid #ddd;padding:6px'>Status</th><th style='border:1px solid #ddd;padding:6px'>Message</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
        </table>
        """
        details_text = "\n".join(text_lines)

    html = f"""
    <h3>Filing Instructions Updated from Drake to Karbon</h3>
    <p><b>Summary</b></p>
    <ul>
    <li><strong>Processed:</strong> {processed_count}</li>
    <li style="color: green;"><strong>Updated:</strong> {totals.get('updated', 0)}</li>
    <li style="color: red;"><strong>Drake RPA Failed:</strong> {totals.get('failed_drake', 0)}</li>
    <li style="color: red;"><strong>Fail Updating Karbon:</strong> {totals.get('failed_karbon', 0)}</li>
    <li><strong>Skipped:</strong> {totals.get('skipped', 0)}</li>
    </ul>
    <p><b>Details:</b></p>
    {details_html}
    """

    text = (
        "Filing Instructions Updated from Drake to Karbon\n"
        f"Processed: {processed_count}\n"
        f"Updated: {totals.get('updated', 0)}\n"
        f"Drake RPA Failed: {totals.get('failed_drake', 0)}\n"
        f"Fail Updating Karbon: {totals.get('failed_karbon', 0)}\n"
        f"Skipped: {totals.get('skipped', 0)}\n\n"
        "Details:\n"
        + details_text
    )

    return subject, html, text

def build_drake_completion_email(
    status: str,
    client_name: str,
    client_id: str,
    form_type: str,
    items: int,
    error_message: Optional[str] = None,
    details: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, str, str]:

    is_success = status.lower() == "success"

    subject = "[Badger] Process PDFs into Drake"

    if is_success:
        title_color = "#28a745"
        title_text = "Drake Import Completed Successfully"
    else:
        title_color = "#dc3545"
        title_text = "Drake Import Failed"

    # Normalize form_type
    if isinstance(form_type, list):
        form_type_list = form_type
    else:
        form_type_list = [f.strip() for f in form_type.split(",")]

    form_type_html = "<br>".join(form_type_list)
    form_type_text = "\n".join(form_type_list)

    details_html = f"""
        <ul>
            <li><strong>Client Name:</strong> {client_name}</li>
            <li><strong>Client Identifier:</strong> {mask_id_last4(client_id)}</li>
            <li><strong>Form Type:</strong><br>{form_type_html}</li>
            <li><strong>Items processed:</strong> {items}</li>
            <li><strong>Status:</strong> <span style="color: {title_color}; font-weight: bold;">{status}</span></li>
        </ul>
    """

    if details:
        rows = []
        for item in details:
            ft = _escape_html(str(item.get("FormType") or ""))
            payer = _escape_html(str(item.get("PayerName", "") or ""))
            pid = mask_id_last4(str(item.get("ID", "") or ""))
            rows.append(f"<tr><td style='border:1px solid #ddd;padding:6px'>{ft}</td><td style='border:1px solid #ddd;padding:6px'>{payer}</td><td style='border:1px solid #ddd;padding:6px'>{pid}</td></tr>")
        
        if rows:
            details_html += f"""
            <div style="margin-top: 15px;">
            <strong>Processed Items:</strong>
            <table style='border-collapse:collapse;width:100%;font-size:12px;font-family:Arial,sans-serif;margin-top:5px;'>
            <thead><tr style='background-color:#f4f4f4'>
            <th style='border:1px solid #ddd;padding:6px;text-align:left'>Form</th>
            <th style='border:1px solid #ddd;padding:6px;text-align:left'>Payer / Employer</th>
            <th style='border:1px solid #ddd;padding:6px;text-align:left'>EIN / TIN</th>
            </tr></thead>
            <tbody>{''.join(rows)}</tbody>
            </table>
            </div>
            """

    if not is_success and error_message:
        details_html += f"""
        <h4 style="color: #dc3545; margin-top: 20px;">Error Details:</h4>
        <pre style="background-color: #f8f9fa; border: 1px solid #e9ecef; padding: 10px; border-radius: 4px; white-space: pre-wrap;">{error_message}</pre>
        """

    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: {title_color}; border-bottom: 2px solid {title_color}; padding-bottom: 10px;">{title_text}</h2>
        <p>The automated Drake data import process has finished with the following status:</p>
        {details_html}
        <p style="font-size: 0.9em; color: #777; margin-top: 20px;">This is an automated notification from the Badger Automation system.</p>
    </div>
    """

    text_body = f"""
    Drake Import Notification
    -------------------------
    Status: {status}
    Client Name: {client_name}
    Client Identifier: {mask_id_last4(client_id)}
    Form Type:
    {form_type_text}
    Items processed: {items}
    """

    if not is_success and error_message:
        text_body += f"\nError: {error_message}"

    return subject, html_body, text_body