"""Генерация банковского отчёта в PDF (ReportLab).

Шрифт DejaVu Sans ищется в двух местах:
1. ./fonts/ — если закоммичен в репозиторий;
2. matplotlib (он его всегда ставит вместе с собой) — fallback,
   чтобы не зависеть от того, попала ли папка fonts/ в git.
"""
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from finance import LoanResult


def _find_font(filename: str) -> str:
    """Ищем .ttf в локальной папке fonts/, иначе берём из matplotlib."""
    local = os.path.join(os.path.dirname(__file__), "fonts", filename)
    if os.path.exists(local):
        return local

    import matplotlib
    mpl_path = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", filename)
    if os.path.exists(mpl_path):
        return mpl_path

    raise FileNotFoundError(
        f"Не найден шрифт {filename}. Положи его в ./fonts/ "
        f"или убедись что matplotlib установлен."
    )


pdfmetrics.registerFont(TTFont("DejaVu", _find_font("DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-B", _find_font("DejaVuSans-Bold.ttf")))


def _schedule_table(res: LoanResult, header_color: str):
    data = [["№", "Платёж, ₽", "Долг, ₽", "Проценты, ₽", "Остаток, ₽"]]
    for r in res.schedule:
        data.append([
            str(r.month),
            f"{r.payment:,.2f}",
            f"{r.principal:,.2f}",
            f"{r.interest:,.2f}",
            f"{r.balance:,.2f}",
        ])
    t = Table(data, repeatRows=1,
              colWidths=[1.2 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm, 3.4 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("FONTNAME", (0, 0), (-1, 0), "DejaVu-B"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F5F7FA")]),
    ]))
    return t


def generate_pdf(amount: float, rate: float, months: int,
                 ann: LoanResult, diff: LoanResult) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)

    styles = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=styles["Title"],
                           fontName="DejaVu-B", fontSize=18, spaceAfter=10)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                        fontName="DejaVu-B", fontSize=13,
                        spaceBefore=8, spaceAfter=6)
    body = ParagraphStyle("B", parent=styles["Normal"],
                          fontName="DejaVu", fontSize=10, leading=14)

    story = [
        Paragraph("Кредитный калькулятор — банковский отчёт", title),
        Paragraph(f"Сумма кредита: <b>{amount:,.2f} ₽</b>", body),
        Paragraph(f"Процентная ставка: <b>{rate}% годовых</b>", body),
        Paragraph(f"Срок кредита: <b>{months} мес.</b>", body),
        Spacer(1, 0.4 * cm),
        Paragraph("Сводное сравнение", h2),
    ]

    summary = [
        ["Параметр", "Аннуитет", "Дифференцированный"],
        ["Первый платёж", f"{ann.first_payment:,.2f} ₽", f"{diff.first_payment:,.2f} ₽"],
        ["Последний платёж", f"{ann.last_payment:,.2f} ₽", f"{diff.last_payment:,.2f} ₽"],
        ["Всего выплачено", f"{ann.total_paid:,.2f} ₽", f"{diff.total_paid:,.2f} ₽"],
        ["Переплата", f"{ann.total_interest:,.2f} ₽", f"{diff.total_interest:,.2f} ₽"],
        ["Экономия (дифф. vs ann.)",
         f"{ann.total_interest - diff.total_interest:,.2f} ₽",
         "—"],
    ]
    t = Table(summary, hAlign="LEFT",
              colWidths=[5 * cm, 5 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("FONTNAME", (0, 0), (-1, 0), "DejaVu-B"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D3557")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F1FAEE")]),
    ]))
    story.append(t)
    story.append(PageBreak())

    story.append(Paragraph("График платежей: аннуитет", h2))
    story.append(_schedule_table(ann, "#2E86AB"))
    story.append(PageBreak())
    story.append(Paragraph("График платежей: дифференцированный", h2))
    story.append(_schedule_table(diff, "#E63946"))

    doc.build(story)
    buf.seek(0)
    return buf.read()
