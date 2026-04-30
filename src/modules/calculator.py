import pandas as pd

class FinanceCore:
    @staticmethod
    def annuity_total(amount, rate, term):
        m_rate = (rate / 100) / 12
        if m_rate > 0:
            pay = amount * (m_rate * (1 + m_rate)**term) / ((1 + m_rate)**term - 1)
        else:
            pay = amount / term
        
        total_repayment = pay * term
        overpayment = total_repayment - amount
        
        # Генерация графика
        schedule = []
        bal = amount
        for i in range(1, term + 1):
            intr = bal * m_rate
            prin = pay - intr
            bal -= prin
            schedule.append([i, round(pay, 2), round(prin, 2), round(intr, 2), max(0, round(bal, 2))])
            
        df = pd.DataFrame(schedule, columns=['Месяц', 'Платеж', 'Тело', 'Проценты', 'Остаток'])
        return df, round(pay, 2), round(overpayment, 2)

    @staticmethod
    def compound_interest(p, r, t, n=12):
        # p=сумма, r=ставка, t=срок в годах, n=капитализаций в год
        # Для бота пересчитаем t из месяцев в годы
        years = t / 12
        final = p * (1 + (r/100)/n)**(n*years)
        return round(final, 2), round(final - p, 2)