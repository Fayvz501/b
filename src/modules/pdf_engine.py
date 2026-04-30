import matplotlib.pyplot as plt
from weasyprint import HTML
import os

def build_report(df, user_id, title="Report"):
    img_path = f"chart_{user_id}.png"
    plt.figure(figsize=(10,6))
    plt.plot(df['Месяц'], df['Остаток'], marker='o', color='#2c3e50')
    plt.title("Динамика погашения долга")
    plt.grid(True)
    plt.savefig(img_path)
    plt.close()
    
    html = f"""
    <html>
    <style>
        body {{ font-family: sans-serif; color: #333; }}
        .box {{ border: 2px solid #2c3e50; padding: 20px; border-radius: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background: #2c3e50; color: white; padding: 10px; }}
        td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
    </style>
    <body>
        <div class='box'>
            <h1>{title}</h1>
            <p>Ниже представлен детальный график выплат, рассчитанный финансовым ботом.</p>
        </div>
        <img src="file://{os.path.abspath(img_path)}" style="width:100%; margin-top:20px;">
        {df.to_html()}
    </body>
    </html>
    """
    pdf_path = f"report_{user_id}.pdf"
    HTML(string=html).write_pdf(pdf_path)
    os.remove(img_path)
    return pdf_path