from datetime import datetime
from html import escape

from app.agents.investment.agent import Proposal, format_euro
from app.storage.decisions import SimulatedTransaction


def approval_receipt(business: str, proposal: Proposal, transaction: SimulatedTransaction) -> tuple[str, str]:
    """Render an approval receipt for the outbox and the multipart confirmation email.

    Args:
        business: Display name of the business that approved the proposal.
        proposal: Approved proposal with its rationale and simulated outcome.
        transaction: Recorded transaction with the reference shown on the Proposals page.

    Returns:
        The plain-text receipt and its HTML alternative.

    Steps:
        1. Format the amount, reference and timestamp from the recorded transaction.
        2. Render both versions and escape business and offer text in the HTML.
    """
    amount = format_euro(transaction.amount)
    reference = f"SIM-{transaction.id[:8].upper()}"
    approved_at = datetime.fromisoformat(transaction.created_at).strftime("%d %b %Y, %H:%M UTC")
    text = (
        f"CFOcus | {business}\nProposal approved (simulated)\n\n"
        f"{proposal.title}\nAmount: {amount}\n\nWhy: {proposal.rationale}\n\n"
        f"{proposal.on_approval}\n\nReference: {reference}\nApproved: {approved_at}"
    )
    html = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#f5f7f7;font:16px/1.5 'Segoe UI',Arial,sans-serif;color:#202f32">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="#f5f7f7">
  <tr><td align="center" style="padding:24px 12px">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="#ffffff"
           style="max-width:560px;text-align:left;border:1px solid #d9e1df;border-radius:12px">
      <tr><td bgcolor="#105647" style="padding:16px 24px;color:#ffffff;border-radius:12px 12px 0 0">
        <span style="font-size:21px;font-weight:700">CFOcus</span>
        <span style="margin-left:12px;font-size:14px;color:#eaf4ef">{escape(business)}</span>
      </td></tr>
      <tr><td style="padding:24px">
        <h1 style="margin:0 0 16px;font-size:26px;line-height:1.25">Proposal approved</h1>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="#eaf4ef">
          <tr><td style="padding:14px 18px;border-left:4px solid #17685b;color:#105647">
            <p style="margin:0 0 2px;font-size:14px">Simulated transaction amount</p>
            <p style="margin:0;font-size:32px;font-weight:bold;line-height:1.25">{escape(amount)}</p>
          </td></tr>
        </table>
        <h2 style="margin:20px 0 4px;font-size:17px">{escape(proposal.title)}</h2>
        <p style="margin:0">{escape(proposal.on_approval)}</p>
        <h2 style="margin:18px 0 4px;font-size:17px">Why this proposal</h2>
        <p style="margin:0">{escape(proposal.rationale)}</p>
      </td></tr>
      <tr><td style="padding:14px 24px;border-top:1px solid #d9e1df;color:#526368;font-size:13px">
        Reference <strong>{escape(reference)}</strong><br>Approved {escape(approved_at)}
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""
    return text, html
