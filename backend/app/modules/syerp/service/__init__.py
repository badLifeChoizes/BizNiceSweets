"""SYERP service layer (business logic).


Split into cohesive submodules (chore-syerp-service-split); this package
re-exports the full public surface so `from app.modules.syerp.service import X`
and `service.X` keep working unchanged.
"""
from __future__ import annotations

from app.modules.syerp.service._common import (
    _COST_QUANTUM,  # noqa: F401
)
from app.modules.syerp.service.accounts import (
    _gl_account_id_by_code,  # noqa: F401
    list_gl_accounts,
)
from app.modules.syerp.service.ar import (
    _INVOICE_NUMBER_RE,  # noqa: F401
    INVOICE_TRANSITIONS,
    _get_invoice_row,  # noqa: F401
    _invoice_received_amount,  # noqa: F401
    _invoice_to_read,  # noqa: F401
    _invoice_transition_allowed,  # noqa: F401
    _load_invoice_lines,  # noqa: F401
    _next_invoice_number,  # noqa: F401
    _PreparedInvoiceLine,  # noqa: F401
    _uninvoiced_qty,  # noqa: F401
    advance_invoice_status,
    create_invoice,
    generate_invoice_number,
    get_invoice,
    get_receipt,
    list_invoices,
    list_receipts,
    list_uninvoiced_shipments,
    post_invoice,
    record_receipt,
)
from app.modules.syerp.service.bills import (
    _BILL_NUMBER_RE,  # noqa: F401
    BILL_TRANSITIONS,
    _already_billed_qty,  # noqa: F401
    _bill_paid_amount,  # noqa: F401
    _bill_to_read,  # noqa: F401
    _bill_transition_allowed,  # noqa: F401
    _get_bill_row,  # noqa: F401
    _is_exact_match,  # noqa: F401
    _is_overpayment,  # noqa: F401
    _load_bill_lines,  # noqa: F401
    _next_bill_number,  # noqa: F401
    _PreparedBillLine,  # noqa: F401
    _unbilled_qty,  # noqa: F401
    advance_bill_status,
    create_bill,
    generate_bill_number,
    get_bill,
    list_bills,
    list_payments,
    list_unbilled_receipts,
    post_bill,
    record_payment,
)
from app.modules.syerp.service.inventory import (
    _adjustment_violates_floor,  # noqa: F401
    _derive_onhand,  # noqa: F401
    compute_new_moving_avg,
    get_bin_on_hand,
    get_item_on_hand,
    get_item_onhand,
    list_item_transactions,
    post_adjustment,
    post_issue,
    post_putaway,
    post_receipt,
    post_transfer,
)
from app.modules.syerp.service.items import (
    _ITEM_CODE_RE,  # noqa: F401
    _build_item_kwargs,  # noqa: F401
    _next_item_code,  # noqa: F401
    _validate_plum_part,  # noqa: F401
    create_item,
    generate_item_code,
    get_item,
    list_items,
    update_item,
)
from app.modules.syerp.service.journal import (
    _get_journal_entry_row,  # noqa: F401
    _je_account_id,  # noqa: F401
    _je_is_balanced,  # noqa: F401
    _je_side,  # noqa: F401
    _je_to_read,  # noqa: F401
    _je_totals,  # noqa: F401
    _load_journal_lines,  # noqa: F401
    _require_gl_account,  # noqa: F401
    _reverse_lines,  # noqa: F401
    derive_account_balance,
    get_account_register,
    get_journal_entry,
    latest_journal_entry_id_for_source,
    list_journal_entries,
    post_journal_entry,
    reverse_journal_entry,
)
from app.modules.syerp.service.locations import (
    create_location,
    get_location,
    list_locations,
    update_location,
)
from app.modules.syerp.service.partners import (
    _build_partner_kwargs,  # noqa: F401
    archive_partner,
    create_partner,
    generate_partner_code,
    get_partner,
    list_partners,
    update_partner,
)
from app.modules.syerp.service.purchasing import (
    _PO_NUMBER_RE,  # noqa: F401
    PO_TRANSITIONS,
    _get_line_row,  # noqa: F401
    _get_po_row,  # noqa: F401
    _is_over_receipt,  # noqa: F401
    _load_po_lines,  # noqa: F401
    _next_line_no,  # noqa: F401
    _next_po_number,  # noqa: F401
    _po_aggregates,  # noqa: F401
    _po_rollup_status,  # noqa: F401
    _po_to_read,  # noqa: F401
    _POAggregates,  # noqa: F401
    _require_draft,  # noqa: F401
    add_line,
    advance_po_status,
    create_po,
    generate_po_number,
    get_po,
    list_pos,
    receive_line,
    remove_line,
    update_line,
)
from app.modules.syerp.service.reports import (
    ap_aging_report,
    ar_aging_report,
    balance_sheet,
    profit_loss,
    trial_balance,
)

__all__ = [
    "BILL_TRANSITIONS",
    "INVOICE_TRANSITIONS",
    "PO_TRANSITIONS",
    "add_line",
    "advance_bill_status",
    "advance_invoice_status",
    "advance_po_status",
    "ap_aging_report",
    "ar_aging_report",
    "archive_partner",
    "balance_sheet",
    "compute_new_moving_avg",
    "create_bill",
    "create_invoice",
    "create_item",
    "create_location",
    "create_partner",
    "create_po",
    "derive_account_balance",
    "generate_bill_number",
    "generate_invoice_number",
    "generate_item_code",
    "generate_partner_code",
    "generate_po_number",
    "get_account_register",
    "get_bill",
    "get_bin_on_hand",
    "get_invoice",
    "get_item",
    "get_item_on_hand",
    "get_item_onhand",
    "get_journal_entry",
    "get_location",
    "get_partner",
    "get_po",
    "get_receipt",
    "latest_journal_entry_id_for_source",
    "list_bills",
    "list_invoices",
    "list_gl_accounts",
    "list_item_transactions",
    "list_items",
    "list_journal_entries",
    "list_locations",
    "list_partners",
    "list_payments",
    "list_pos",
    "list_receipts",
    "list_unbilled_receipts",
    "list_uninvoiced_shipments",
    "post_adjustment",
    "post_bill",
    "post_invoice",
    "post_issue",
    "post_journal_entry",
    "post_putaway",
    "post_receipt",
    "post_transfer",
    "profit_loss",
    "receive_line",
    "record_payment",
    "record_receipt",
    "remove_line",
    "reverse_journal_entry",
    "trial_balance",
    "update_item",
    "update_line",
    "update_location",
    "update_partner",
]
