import smtplib
from email.message import EmailMessage
import os

def send_mail_alert(equipment_list):
    if not equipment_list:
        return

    EMAIL_ADDR = os.getenv("EMAIL_ADDR")
    EMAIL_PASS = os.getenv("EMAIL_PASS")


    if not EMAIL_ADDR or not EMAIL_PASS:
        raise ValueError("EMAIL_ADDR and EMAIL_PASS environment variables must be set")

    msg = EmailMessage()
    msg['Subject'] = "🚨 KAYNES ELECTRONICS : Calibration Alert"
    msg['From'] = f"Kaynes Electronics Tracker <{EMAIL_ADDR}>"
    msg['To'] = EMAIL_ADDR

    body = "KAYNES ELECTRONICS CALIBRATION ALERT\n"
    body += "="*40 + "\n\n"

    for item in equipment_list:
        body += f"Asset: {item.c2_asset_id} | Location: {item.c13_location or 'N/A'} | Due: {item.c20_due_date}\n"

    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
            server.login(EMAIL_ADDR, EMAIL_PASS)
            server.send_message(msg)
        print("Mail sent successfully")
    except Exception as e:
        print(f"Mail Error: {e}")
