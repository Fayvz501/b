"""Графики платежей через matplotlib (без GUI-бэкенда)."""
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.finance import LoanResult


def _save(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def chart_structure(res: LoanResult, title: str) -> bytes:
    """Структура платежа: проценты vs основной долг."""
    months = [r.month for r in res.schedule]
    principal = [r.principal for r in res.schedule]
    interest = [r.interest for r in res.schedule]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.stackplot(months, principal, interest,
                 labels=["Основной долг", "Проценты"],
                 colors=["#2E86AB", "#E63946"], alpha=0.85)
    ax.set_xlabel("Месяц")
    ax.set_ylabel("Платёж, ₽")
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    return _save(fig)


def chart_balance_compare(ann: LoanResult, diff: LoanResult) -> bytes:
    """Остаток долга по двум схемам."""
    months = [r.month for r in ann.schedule]
    ba = [r.balance for r in ann.schedule]
    bd = [r.balance for r in diff.schedule]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(months, ba, label="Аннуитет", color="#2E86AB", lw=2.5)
    ax.plot(months, bd, label="Дифференцированный", color="#E63946", lw=2.5)
    ax.fill_between(months, ba, bd, alpha=0.18, color="#E63946")
    ax.set_xlabel("Месяц")
    ax.set_ylabel("Остаток долга, ₽")
    ax.set_title("Остаток основного долга")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return _save(fig)


def chart_compare(ann: LoanResult, diff: LoanResult) -> bytes:
    """Сравнение размеров платежа."""
    months = [r.month for r in ann.schedule]
    pa = [r.payment for r in ann.schedule]
    pd = [r.payment for r in diff.schedule]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(months, pa,
            label=f"Аннуитет (переплата {ann.total_interest:,.0f} ₽)",
            color="#2E86AB", lw=2.5)
    ax.plot(months, pd,
            label=f"Дифф. (переплата {diff.total_interest:,.0f} ₽)",
            color="#E63946", lw=2.5)
    ax.set_xlabel("Месяц")
    ax.set_ylabel("Размер платежа, ₽")
    ax.set_title("Сравнение схем погашения")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return _save(fig)
