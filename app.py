import os
import smtplib
import sys
import pandas as pd
from datetime import date, datetime, timedelta
import datetime as dt_module
from email.message import EmailMessage
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, make_response
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

BASE_DIR = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.secret_key = "kaynes_ff_qam_42_final"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///calibration_master.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


def _normalize_header(header):
    """Normalize uploaded sheet headers for resilient column mapping."""
    return ''.join(ch.lower() for ch in str(header) if ch.isalnum())

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


class UserAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # admin / user


class LocationEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), unique=True, nullable=False)
    email = db.Column(db.String(200), nullable=False)


class MailConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_email = db.Column(db.String(200), nullable=False)
    app_key = db.Column(db.String(300), nullable=False)
    default_to = db.Column(db.String(500), nullable=True)
    smtp_host = db.Column(db.String(100), nullable=False, default='smtp.zoho.com')
    smtp_port = db.Column(db.Integer, nullable=False, default=465)
    is_active = db.Column(db.Boolean, default=True)


class SchedulerConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hour = db.Column(db.Integer, nullable=False, default=9)
    minute = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)


def initialize_defaults():
    if not UserAccount.query.filter_by(username='admin').first():
        db.session.add(UserAccount(username='admin', password='admin123', role='admin'))
    if not UserAccount.query.filter_by(username='user').first():
        db.session.add(UserAccount(username='user', password='user123', role='user'))
    db.session.commit()


def get_mail_config():
    return MailConfig.query.filter_by(is_active=True).order_by(MailConfig.id.desc()).first()


def get_scheduler_config():
    return SchedulerConfig.query.filter_by(is_active=True).order_by(SchedulerConfig.id.desc()).first()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('index', alert='access_denied'))
        return fn(*args, **kwargs)
    return wrapper

# --- MAINTAINING YOUR ALERT LOGIC WITH 30/15 DAY ADDITION ---
def check_alerts():
    with app.app_context():
        today = datetime.now().date()
        t30 = today + timedelta(days=30)

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

        mail_cfg = get_mail_config()
        if not mail_cfg:
            print("Mail config missing. Add sender email and app key in Admin panel.")
            return False

        EMAIL_ADDR = mail_cfg.sender_email
        EMAIL_PASS = mail_cfg.app_key
        location_mail_map = {
            m.location.strip().lower(): [x.strip() for x in m.email.split(',') if x.strip()]
            for m in LocationEmail.query.all() if m.location and m.email
        }

        grouped_due_items = {}
        for due_item in (items_15 + items_30):
            key = (due_item.c13_location or '').strip().lower() or "__unmapped__"
            grouped_due_items.setdefault(key, []).append(due_item)

        default_recipients = [x.strip() for x in (mail_cfg.default_to or '').split(',') if x.strip()] or [EMAIL_ADDR]
        sent_any = False
        try:
            with smtplib.SMTP_SSL(mail_cfg.smtp_host, mail_cfg.smtp_port) as server:
                server.login(EMAIL_ADDR, EMAIL_PASS)
                for location_key, location_items in grouped_due_items.items():
                    recipients = location_mail_map.get(location_key) or default_recipients
                    # Sender should receive only the consolidated summary mail, not location-wise mails.
                    recipients = [r for r in recipients if r.strip().lower() != EMAIL_ADDR.strip().lower()]
                    if not recipients:
                        continue
                    msg = EmailMessage()
                    msg['From'] = f"Kaynes Electronics Calibration System <{EMAIL_ADDR}>"
                    msg['To'] = ", ".join(sorted(set(recipients)))
                    location_title = location_items[0].c13_location if location_items[0].c13_location else "Unmapped Location"
                    msg['Subject'] = f"🚨 Calibration Alert ({location_title}): 15/30-Day Items"

                    body = "KAYNES ELECTRONICS - CALIBRATION ALERT\n" + "="*40 + "\n"
                    body += f"\nLocation: {location_title}\n"
                    items_15_loc = [i for i in location_items if (i.c20_due_date - today).days <= 15]
                    items_30_loc = [i for i in location_items if 15 < (i.c20_due_date - today).days <= 30]
                    if items_15_loc:
                        body += "\n🟡 15 DAYS LEFT:\n"
                        for i in items_15_loc:
                            days = (i.c20_due_date - today).days
                            body += f"- {i.c2_asset_id} | {i.c3_eq_name} | Due: {i.c20_due_date} ({days} days)\n"
                    if items_30_loc:
                        body += "\n🔵 30 DAYS LEFT:\n"
                        for i in items_30_loc:
                            days = (i.c20_due_date - today).days
                            body += f"- {i.c2_asset_id} | {i.c3_eq_name} | Due: {i.c20_due_date} ({days} days)\n"

                    msg.set_content(body)
                    server.send_message(msg)
                    sent_any = True

                # Sender gets one consolidated mail with all locations/items.
                summary_msg = EmailMessage()
                summary_msg['From'] = f"Kaynes Electronics Calibration System <{EMAIL_ADDR}>"
                summary_msg['To'] = EMAIL_ADDR
                summary_msg['Subject'] = "🚨 Calibration Alert Summary (All Locations)"
                summary_body = "KAYNES ELECTRONICS - CALIBRATION ALERT SUMMARY\n" + "=" * 48 + "\n"
                for location_items in grouped_due_items.values():
                    location_title = location_items[0].c13_location if location_items[0].c13_location else "Unmapped Location"
                    summary_body += f"\nLocation: {location_title}\n"
                    for i in location_items:
                        days = (i.c20_due_date - today).days
                        tag = "15D" if days <= 15 else "30D"
                        summary_body += f"- [{tag}] {i.c2_asset_id} | {i.c3_eq_name} | Due: {i.c20_due_date} ({days} days)\n"
                summary_msg.set_content(summary_body)
                server.send_message(summary_msg)
            return sent_any
        except Exception as e:
            print(f"Mail Error: {e}")
            return False

def send_test_email(subject, body):
    mail_cfg = get_mail_config()
    if not mail_cfg:
        raise ValueError("Mail config missing. Please save Sender Mail + App Key in Admin panel.")

    EMAIL_ADDR = mail_cfg.sender_email
    EMAIL_PASS = mail_cfg.app_key
    recipients = mail_cfg.default_to or EMAIL_ADDR
    msg = EmailMessage()
    msg['From'] = f"Kaynes Electronics Calibration System <{EMAIL_ADDR}>"
    msg['To'] = recipients
    msg['Subject'] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL(mail_cfg.smtp_host, mail_cfg.smtp_port) as server:
        server.login(EMAIL_ADDR, EMAIL_PASS)
        server.send_message(msg)

@app.route('/send_test_email')
@login_required
@admin_required
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
# Run task daily at configured local time.
# Defaults: 09:00 (9:00 AM). Override with AUTO_MAIL_HOUR / AUTO_MAIL_MINUTE env vars.
AUTO_MAIL_HOUR = int(os.getenv('AUTO_MAIL_HOUR', '9'))
AUTO_MAIL_MINUTE = int(os.getenv('AUTO_MAIL_MINUTE', '0'))
scheduler.add_job(func=check_alerts, trigger="cron", hour=AUTO_MAIL_HOUR, minute=AUTO_MAIL_MINUTE, id="daily_alert_job", replace_existing=True)
scheduler.start()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = UserAccount.query.filter_by(username=username).first()
        if user and user.password == password:
            session['user'] = user.username
            session['role'] = user.role
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid username or password')
    return render_template('login.html', error=None)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    items = CalibrationMaster.query.all()
    today = datetime.now().date()
    total_with_due = 0
    due_30_count = 0
    due_15_count = 0
    not_due_count = 0
    overdue_count = 0
    for item in items:
        if not item.c20_due_date:
            continue
        total_with_due += 1
        days_left = (item.c20_due_date - today).days
        if days_left < 0:
            overdue_count += 1
        if days_left <= 15:
            due_15_count += 1
            due_30_count += 1
        elif days_left <= 30:
            due_30_count += 1
        else:
            not_due_count += 1
    due_percentage = round((due_30_count / total_with_due) * 100, 2) if total_with_due else 0

    users = UserAccount.query.order_by(UserAccount.username.asc()).all() if session.get('role') == 'admin' else []
    location_mails = LocationEmail.query.order_by(LocationEmail.location.asc()).all() if session.get('role') == 'admin' else []
    mail_cfg = get_mail_config() if session.get('role') == 'admin' else None
    scheduler_cfg = get_scheduler_config() if session.get('role') == 'admin' else None
    return render_template(
        'index.html',
        items=items,
        today=today,
        current_role=session.get('role', 'user'),
        users=users,
        location_mails=location_mails,
        mail_cfg=mail_cfg,
        scheduler_cfg=scheduler_cfg,
        total_with_due=total_with_due,
        due_30_count=due_30_count,
        due_15_count=due_15_count,
        not_due_count=not_due_count,
        overdue_count=overdue_count,
        due_percentage=due_percentage
    )

@app.route('/download_master')
@login_required
def download_master():
    items = CalibrationMaster.query.all()
    today = date.today()
    data = []
    for item in items:
        days_left = (item.c20_due_date - today).days if item.c20_due_date else None
        if days_left is None:
            status = 'N/A'
        elif days_left <= 15:
            status = '15D'
        elif days_left <= 30:
            status = '30D'
        else:
            status = 'OK'

        row = {
            "Sl. No": item.c1_sl_no or "",
            "Kaynes Asset ID": item.c2_asset_id or "",
            "Name of Eqpmt.": item.c3_eq_name or "",
            "Make": item.c4_make or "",
            "Model No.": item.c5_model_no or "",
            "Equipment Sl No": item.c6_eq_sl_no or "",
            "Range": item.c7_range or "",
            "Accuracy": item.c8_accuracy or "",
            "Acceptance Criteria": item.c9_acceptance_criteria or "",
            "Application": item.c10_application or "",
            "Parameter": item.c11_parameter or "",
            "Owner": item.c12_owner or "",
            "Location (Line Name)": item.c13_location or "",
            "Calibration Agency": item.c14_cal_agency or "",
            "Type of Agency (NABL Lab, Internal, Traceable to NABL Lab, Authorized Service Provider)": item.c15_is_nabl or "",
            "Calibration or Verification method (External / Internal / Onsite / Verification)": item.c16_verif_method or "",
            "Calibration Procedure Reference": item.c21_remarks or "",
            "Calibration Frequency": item.c17_frequency or "",
            "Calibration Certificate No.": item.c18_cert_no or "",
            "Calibration Date": item.c19_cal_date.strftime('%Y-%m-%d') if item.c19_cal_date else "",
            "Due Date": item.c20_due_date.strftime('%Y-%m-%d') if item.c20_due_date else "",
            "Status": status
        }
        data.append(row)
    df = pd.DataFrame(data)
    csv_data = df.to_csv(index=False)
    response = make_response(csv_data)
    response.headers['Content-Disposition'] = 'attachment; filename=calibration_master.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

# --- REMAINING ROUTES (YOUR ORIGINAL FLOW) ---
@app.route('/manage_record', methods=['POST'])
@login_required
@admin_required
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


@app.route('/upload_excel', methods=['POST'])
@login_required
@admin_required
def upload_excel():
    file = request.files.get('excel_file')
    if not file or file.filename == '':
        return redirect(url_for('index', alert='upload_no_file'))

    try:
        # Supports xlsx/xls (and csv as a fallback if users provide csv)
        if file.filename.lower().endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        print(f"Upload read error: {e}")
        return redirect(url_for('index', alert='upload_read_error'))

    # Map many possible header variants to existing DB fields.
    header_map = {
        'slno': 'c1_sl_no',
        'serialnumber': 'c1_sl_no',
        'kaynesassetid': 'c2_asset_id',
        'assetid': 'c2_asset_id',
        'nameofeqpmt': 'c3_eq_name',
        'equipname': 'c3_eq_name',
        'equipmentname': 'c3_eq_name',
        'make': 'c4_make',
        'modelno': 'c5_model_no',
        'equipmentslno': 'c6_eq_sl_no',
        'range': 'c7_range',
        'accuracy': 'c8_accuracy',
        'acceptancecriteria': 'c9_acceptance_criteria',
        'application': 'c10_application',
        'parameter': 'c11_parameter',
        'owner': 'c12_owner',
        'locationlinename': 'c13_location',
        'location': 'c13_location',
        'calibrationagency': 'c14_cal_agency',
        'typeofagencynabllabinternaltraceabletonabllabauthorizedserviceprovider': 'c15_is_nabl',
        'typeofagency': 'c15_is_nabl',
        'calibrationorverificationmethodexternalinternalonsiteverification': 'c16_verif_method',
        'calibrationorverificationmethod': 'c16_verif_method',
        'calibrationprocedurereference': 'c21_remarks',
        'calibrationfrequency': 'c17_frequency',
        'calibrationcertificateno': 'c18_cert_no',
        'calibrationdate': 'c19_cal_date',
        'duedate': 'c20_due_date',
    }

    resolved_columns = {}
    for col in df.columns:
        key = _normalize_header(col)
        mapped = header_map.get(key)
        if mapped:
            resolved_columns[col] = mapped

    # Require at least Asset ID to upsert records
    if 'c2_asset_id' not in resolved_columns.values():
        return redirect(url_for('index', alert='upload_missing_asset'))

    upserted = 0
    for _, row in df.iterrows():
        row_data = {}
        for src_col, model_col in resolved_columns.items():
            value = row.get(src_col)
            if pd.isna(value):
                continue
            row_data[model_col] = value

        asset_id = str(row_data.get('c2_asset_id', '')).strip()
        if not asset_id:
            continue

        item = CalibrationMaster.query.filter_by(c2_asset_id=asset_id).first() or CalibrationMaster(c2_asset_id=asset_id)

        for field, value in row_data.items():
            if field in ('c19_cal_date', 'c20_due_date'):
                parsed = None
                if isinstance(value, (datetime, pd.Timestamp)):
                    parsed = value.date()
                else:
                    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y'):
                        try:
                            parsed = datetime.strptime(str(value).strip(), fmt).date()
                            break
                        except ValueError:
                            continue
                if parsed:
                    setattr(item, field, parsed)
            else:
                setattr(item, field, str(value).strip())

        db.session.add(item)
        upserted += 1

    db.session.commit()
    return redirect(url_for('index', alert='upload_success', count=upserted))

@app.route('/manual_alert')
@login_required
@admin_required
def manual_alert():
    alert_sent = check_alerts()
    if alert_sent:
        return redirect(url_for('index', alert='sent'))
    return redirect(url_for('index', alert='none'))

@app.route('/delete_record/<int:item_id>')
@login_required
@admin_required
def delete_record(item_id):
    record = CalibrationMaster.query.get(item_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return redirect(url_for('index', alert='deleted'))


@app.route('/manage_user', methods=['POST'])
@login_required
@admin_required
def manage_user():
    action = request.form.get('action')
    username = request.form.get('username', '').strip()

    if action == 'add':
        password = request.form.get('password', '')
        role = request.form.get('role', 'user')
        if not username or not password or role not in ('admin', 'user'):
            return redirect(url_for('index', alert='user_invalid'))
        if UserAccount.query.filter_by(username=username).first():
            return redirect(url_for('index', alert='user_exists'))
        db.session.add(UserAccount(username=username, password=password, role=role))
        db.session.commit()
        return redirect(url_for('index', alert='user_added'))

    if action == 'delete':
        user = UserAccount.query.filter_by(username=username).first()
        if not user or user.username == 'admin':
            return redirect(url_for('index', alert='user_delete_blocked'))
        db.session.delete(user)
        db.session.commit()
        return redirect(url_for('index', alert='user_deleted'))

    return redirect(url_for('index', alert='user_invalid'))


@app.route('/manage_location_mail', methods=['POST'])
@login_required
@admin_required
def manage_location_mail():
    location = request.form.get('location', '').strip()
    email = request.form.get('email', '').strip()
    if not location or not email:
        return redirect(url_for('index', alert='location_mail_invalid'))

    entry = LocationEmail.query.filter_by(location=location).first() or LocationEmail(location=location)
    entry.email = email
    db.session.add(entry)
    db.session.commit()
    return redirect(url_for('index', alert='location_mail_saved'))


@app.route('/save_mail_config', methods=['POST'])
@login_required
@admin_required
def save_mail_config():
    sender_email = request.form.get('sender_email', '').strip()
    app_key = request.form.get('app_key', '').strip()
    default_to = request.form.get('default_to', '').strip()
    smtp_host = request.form.get('smtp_host', 'smtp.zoho.com').strip() or 'smtp.zoho.com'
    smtp_port_raw = request.form.get('smtp_port', '465').strip() or '465'

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        return redirect(url_for('index', alert='mail_cfg_invalid'))

    if not sender_email or not app_key:
        return redirect(url_for('index', alert='mail_cfg_invalid'))

    # Keep one active config record; update latest if exists.
    cfg = get_mail_config() or MailConfig(sender_email=sender_email, app_key=app_key)
    cfg.sender_email = sender_email
    cfg.app_key = app_key
    cfg.default_to = default_to
    cfg.smtp_host = smtp_host
    cfg.smtp_port = smtp_port
    cfg.is_active = True
    db.session.add(cfg)
    db.session.commit()
    return redirect(url_for('index', alert='mail_cfg_saved'))


@app.route('/save_scheduler_config', methods=['POST'])
@login_required
@admin_required
def save_scheduler_config():
    hour_raw = request.form.get('hour', '9').strip() or '9'
    minute_raw = request.form.get('minute', '0').strip() or '0'
    try:
        hour = int(hour_raw)
        minute = int(minute_raw)
    except ValueError:
        return redirect(url_for('index', alert='mail_cfg_invalid'))

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return redirect(url_for('index', alert='mail_cfg_invalid'))

    cfg = get_scheduler_config() or SchedulerConfig(hour=hour, minute=minute, is_active=True)
    cfg.hour = hour
    cfg.minute = minute
    cfg.is_active = True
    db.session.add(cfg)
    db.session.commit()

    scheduler.add_job(func=check_alerts, trigger="cron", hour=hour, minute=minute, id="daily_alert_job", replace_existing=True)
    return redirect(url_for('index', alert='mail_cfg_saved'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        initialize_defaults()
        scheduler_cfg = get_scheduler_config()
        if scheduler_cfg:
            scheduler.add_job(
                func=check_alerts,
                trigger="cron",
                hour=scheduler_cfg.hour,
                minute=scheduler_cfg.minute,
                id="daily_alert_job",
                replace_existing=True
            )
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=True, use_reloader=False)
