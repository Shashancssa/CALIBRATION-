import os
import smtplib
import pandas as pd
from datetime import datetime, timedelta
import datetime as dt_module
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, session, make_response
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = "kaynes_ff_qam_42_final"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///calibration_master.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODEL (MAINTAINING YOUR 21 COLUMNS) ---
class CalibrationMaster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    c1_sl_no = db.Column(db.String(50))
    c2_asset_id = db.Column(db.String(100), unique=True, nullable=False)
    c3_eq_name = db.Column(db.String(200))
    c4_make = db.Column(db.String(200))
    c5_model_no = db.Column(db.String(200))
    c6_eq_sl_no = db.Column(db.String(200))
    c7_range = db.Column(db.String(200))
    c8_accuracy = db.Column(db.String(200))
    c9_acceptance_criteria = db.Column(db.String(500))
    c10_application = db.Column(db.String(500))
    c11_parameter = db.Column(db.String(200))
    c12_owner = db.Column(db.String(200))
    c13_location = db.Column(db.String(200))
    c14_cal_agency = db.Column(db.String(200))
    c15_is_nabl = db.Column(db.String(50))
    c16_verif_method = db.Column(db.String(500))
    c17_frequency = db.Column(db.String(100))
    c18_cert_no = db.Column(db.String(200))
    c19_cal_date = db.Column(db.Date)
    c20_due_date = db.Column(db.Date)
    c21_remarks = db.Column(db.String(500))

    def to_dict(self):
        return {
            "c1_sl_no": self.c1_sl_no or "", "c2_asset_id": self.c2_asset_id or "",
            "c3_eq_name": self.c3_eq_name or "", "c4_make": self.c4_make or "",
            "c5_model_no": self.c5_model_no or "", "c6_eq_sl_no": self.c6_eq_sl_no or "",
            "c7_range": self.c7_range or "", "c8_accuracy": self.c8_accuracy or "",
            "c9_acceptance_criteria": self.c9_acceptance_criteria or "",
            "c10_application": self.c10_application or "", "c11_parameter": self.c11_parameter or "",
            "c12_owner": self.c12_owner or "", "c13_location": self.c13_location or "",
            "c14_cal_agency": self.c14_cal_agency or "", "c15_is_nabl": self.c15_is_nabl or "",
            "c16_verif_method": self.c16_verif_method or "", "c17_frequency": self.c17_frequency or "",
            "c18_cert_no": self.c18_cert_no or "",
            "c19_cal_date": self.c19_cal_date.strftime('%Y-%m-%d') if self.c19_cal_date else "",
            "c20_due_date": self.c20_due_date.strftime('%Y-%m-%d') if self.c20_due_date else "",
            "c21_remarks": self.c21_remarks or ""
        }

# --- MAINTAINING YOUR ALERT LOGIC WITH 30/15 DAY ADDITION ---
def check_alerts():
    with app.app_context():
        today = datetime.now().date()
        t30 = today + timedelta(days=30)
        t15 = today + timedelta(days=15)

        # Include items due in the past 30 days too (overdue counts as immediate alert)
        all_due = CalibrationMaster.query.filter(CalibrationMaster.c20_due_date <= t30).all()
        items_15 = [item for item in all_due if (item.c20_due_date - today).days <= 15]
        items_30 = [item for item in all_due if 15 < (item.c20_due_date - today).days <= 30]

        print(f"check_alerts(): today={today}, total_due_up_to_30_days={len(all_due)}, 15d={len(items_15)}, 30d={len(items_30)}")
        for item in all_due:
            d = (item.c20_due_date - today).days
            print(f" - {item.c2_asset_id}: due={item.c20_due_date}, days={d}")

        if not items_15 and not items_30:
            # No pending alerts in window, do nothing
            return False

        EMAIL_ADDR = "shashank.c@kaynestechnology.net"
        EMAIL_PASS = "PKXbWyCKWPJF"
        msg = EmailMessage()
        msg['From'] = f"Calibration System <{EMAIL_ADDR}>"
        msg['To'] = "shashank.c@kaynestechnology.net"
        msg['Subject'] = "🚨 Calibration Alert: 15/30-Day Items"

        body = "KAYNES TECHNOLOGY - CALIBRATION ALERT\n" + "="*40 + "\n"
        if items_15:
            body += "\n🔴 15 DAYS LEFT:\n"
            for i in items_15:
                days = (i.c20_due_date - today).days
                body += f"- {i.c2_asset_id} | {i.c3_eq_name} | Due: {i.c20_due_date} ({days} days)\n"
        if items_30:
            body += "\n🟡 30 DAYS LEFT:\n"
            for i in items_30:
                days = (i.c20_due_date - today).days
                body += f"- {i.c2_asset_id} | {i.c3_eq_name} | Due: {i.c20_due_date} ({days} days)\n"

        msg.set_content(body)
        try:
            with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
                server.login(EMAIL_ADDR, EMAIL_PASS)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Mail Error: {e}")
            return False

def send_test_email(subject, body):
    EMAIL_ADDR = "shashank.c@kaynestechnology.net"
    EMAIL_PASS = "Kt8AWJB95FPa"  # put the app-specific password here
    msg = EmailMessage()
    msg['From'] = f"Calibration System <{EMAIL_ADDR}>"
    msg['To'] = "shashank.c@kaynestechnology.net"
    msg['Subject'] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
        server.login(EMAIL_ADDR, EMAIL_PASS)
        server.send_message(msg)

@app.route('/send_test_email')
def send_test_email_route():
    try:
        send_test_email("KAYNES Test", "This is a manual test email from /send_test_email")
        print("INFO: test email sent")
        return "Test email sent successfully. Check inbox and terminal logs."
    except Exception as e:
        print("ERROR:", e)
        return f"Test email failed: {e}", 500

# Scheduler with daily 9:00 AM trigger (and still manual trigger available)
# Use your local timezone here; for IST use 'Asia/Kolkata'.
# For Python 3.9+, zoneinfo is available in standard library.
from zoneinfo import ZoneInfo

scheduler = BackgroundScheduler(timezone=ZoneInfo('Asia/Kolkata'))
# Run task at 9:00 AM local time every day
scheduler.add_job(func=check_alerts, trigger="cron", hour=9, minute=0)
scheduler.start()

@app.route('/')
def index():
    items = CalibrationMaster.query.all()
    return render_template('index.html', items=items, today=datetime.now().date())

@app.route('/download_master')
def download_master():
    items = CalibrationMaster.query.all()
    today = date.today()
    data = []
    for item in items:
        row = item.to_dict()
        if item.c20_due_date:
            row['Days Left'] = (item.c20_due_date - today).days
        else:
            row['Days Left'] = 'N/A'
        data.append(row)
    df = pd.DataFrame(data)
    csv_data = df.to_csv(index=False)
    response = make_response(csv_data)
    response.headers['Content-Disposition'] = 'attachment; filename=calibration_master.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

# --- REMAINING ROUTES (YOUR ORIGINAL FLOW) ---
@app.route('/manage_record', methods=['POST'])
def manage_record():
    d = request.form
    item = CalibrationMaster.query.filter_by(c2_asset_id=d.get('c2_asset_id')).first() or CalibrationMaster(c2_asset_id=d.get('c2_asset_id'))

    # Full mapping of 21 fields (use the same names as your HTML form fields)
    field_map = {
        'c1_sl_no': 'c1_sl_no',
        'c2_asset_id': 'c2_asset_id',
        'c3_eq_name': 'c3_eq_name',
        'c4_make': 'c4_make',
        'c5_model_no': 'c5_model_no',
        'c6_eq_sl_no': 'c6_eq_sl_no',
        'c7_range': 'c7_range',
        'c8_accuracy': 'c8_accuracy',
        'c9_acceptance_criteria': 'c9_acceptance_criteria',
        'c10_application': 'c10_application',
        'c11_parameter': 'c11_parameter',
        'c12_owner': 'c12_owner',
        'c13_location': 'c13_location',
        'c14_cal_agency': 'c14_cal_agency',
        'c15_is_nabl': 'c15_is_nabl',
        'c16_verif_method': 'c16_verif_method',
        'c17_frequency': 'c17_frequency',
        'c18_cert_no': 'c18_cert_no',
        'c19_cal_date': 'c19_cal_date',
        'c20_due_date': 'c20_due_date',
        'c21_remarks': 'c21_remarks'
    }

    for form_key, model_key in field_map.items():
        value = d.get(form_key)
        if value in (None, ''):
            continue
        if model_key in ('c19_cal_date', 'c20_due_date'):
            try:
                parsed = datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                continue
            setattr(item, model_key, parsed)
        else:
            setattr(item, model_key, value)

    db.session.add(item)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/manual_alert')
def manual_alert():
    alert_sent = check_alerts()
    if alert_sent:
        return redirect(url_for('index', alert='sent'))
    return redirect(url_for('index', alert='none'))

@app.route('/delete_record/<int:item_id>')
def delete_record(item_id):
    record = CalibrationMaster.query.get(item_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return redirect(url_for('index', alert='deleted'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, use_reloader=False)