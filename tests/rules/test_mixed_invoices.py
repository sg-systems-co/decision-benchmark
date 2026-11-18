"""Sheet §5, mixed invoices (A12 build PR 3 commit 16): §5-a each line on its own, the decision by the most severe
line; §5-b where the law ties the treatment to the split, the split decides (not itemised: the whole invoice is
taxed). The §5-b rules are tested with their own rules (L-8, P-12, P-16, MS-2); registered here too."""

from decision_benchmark.task_sets.ap_invoices.models import Decision as D

from .factory import answer, my_line, set_lines, sg_line
from .my_cases import one_line, sg_one_line

RCI, OK = D.REQUEST_CORRECTED_INVOICE, D.APPROVE


def two_lines(records, case, first, second, country="MY"):
    """Make a one-line case two-line: the second line gets its own PO line and receipt."""
    po = records["purchase_orders"][0]
    category, price, account = second["category"], second["unit_price"], second["gl_account"]
    po["lines"].append({"line_no": 2, "description": f"{category} line", "category": category, "qty": 1,
                        "uom": "unit", "unit_price": price, "gl_account": account})
    records["goods_receipts"][0]["lines"].append({"po_line_no": 2, "qty_received": 1, "uom": "unit"})
    set_lines(case, [first, second["line"]])
    return records, case


def test_5a_my_wrongly_charged_line_makes_the_whole_invoice_corrected():
    r, c = one_line("it_services")
    second = {"category": "legal_services", "unit_price": "1000.00", "gl_account": "6160-000",
              "line": my_line(2, "legal_services", 1, "1000.00", rate="8", po_line_no=2, subject_outside_malaysia=True)}
    a = answer(*two_lines(r, c, my_line(1, "it_services", 1, "3200.00", po_line_no=1), second))
    assert (a.decision, a.tax_treatment) == (RCI, "SST_SHOULD_BE_EXEMPT")
    assert [(t.treatment, t.basis) for t in a.tax_lines] == [("SST_CORRECT", "MS-2"), ("SST_SHOULD_BE_EXEMPT", "MS-4")]


def test_5a_sg_exempt_line_charged_with_gst_and_a_claimable_line():
    r, c = sg_one_line()
    second = {"category": "it_services", "unit_price": "500.00", "gl_account": "6150-000",
              "line": sg_line(2, "it_services", 1, "500.00", po_line_no=2, exempt_supply="financial")}
    a = answer(*two_lines(r, c, sg_line(1, "machine_parts", 10, "150.00", po_line_no=1), second))
    assert (a.decision, a.tax_treatment) == (RCI, "GST_WRONGLY_CHARGED")
    assert [t.treatment for t in a.tax_lines] == ["CLAIMABLE", "GST_WRONGLY_CHARGED"]


def test_5a_near_miss_lines_with_the_same_treatment():
    r, c = sg_one_line()
    second = {"category": "it_services", "unit_price": "500.00", "gl_account": "6150-000",
              "line": sg_line(2, "it_services", 1, "500.00", po_line_no=2)}
    a = answer(*two_lines(r, c, sg_line(1, "machine_parts", 10, "150.00", po_line_no=1), second))
    assert (a.decision, a.tax_treatment) == (OK, "CLAIMABLE")
