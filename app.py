from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()  # Loads .env file

app = Flask(__name__, static_folder='static')

# SECRET KEY
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key")

# DATABASE CONFIG – POSTGRESQL FIRST, SQLITE FALLBACK
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgresql://user:pass@localhost/dbname

if DATABASE_URL and DATABASE_URL.startswith("postgres"):
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print("Using PostgreSQL")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reminders.db'
    print("Using SQLite (fallback)")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Custom filter for {{ "now"|strftime(...) }}
@app.template_filter('strftime')
def _jinja2_filter_strftime(date, fmt=None):
    if date == "now" or date is None:
        date = datetime.now()
    if fmt is None:
        fmt = "%b %d"
    return date.strftime(fmt)

# Models
class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

class Alarm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    alarm_time = db.Column(db.DateTime, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    group = db.relationship('Group', backref=db.backref('alarms', lazy=True))
    is_done = db.Column(db.Boolean, default=False)
    notify_before_minutes = db.Column(db.Integer, nullable=True)

# Routes
@app.route('/')
def index():
    groups = Group.query.order_by(Group.name).all()
    if not any(g.name == 'General' for g in groups):
        db.session.add(Group(name='General'))
        db.session.commit()
    return render_template('index.html', groups=groups, selected_group=None)

@app.route('/group/<int:group_id>')
def view_group(group_id):
    selected_group = Group.query.get_or_404(group_id)
    groups = Group.query.order_by(Group.name).all()
    alarms = Alarm.query.filter_by(group_id=group_id).order_by(Alarm.alarm_time).all()
    serialized_alarms = [
        {
            'id': a.id,
            'title': a.title,
            'description': a.description or '',
            'alarm_time': a.alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
            'group_id': a.group_id,
            'is_done': a.is_done,
            'notify_before_minutes': a.notify_before_minutes or 0
        }
        for a in alarms
    ]
    return render_template('index.html', alarms=serialized_alarms, groups=groups, selected_group=selected_group)

@app.route('/api/alarms')
def api_alarms():
    alarms = Alarm.query.all()
    return jsonify({'alarms': [{
        'id': a.id,
        'title': a.title,
        'description': a.description or '',
        'alarm_time': a.alarm_time.isoformat(),
        'notify_before_minutes': a.notify_before_minutes or 0,
        'is_done': a.is_done
    } for a in alarms]})

@app.route('/timer')
def timer():
    return render_template('timer.html')

@app.route('/add', methods=['POST'])
def add_alarm():
    title = request.form['title']
    description = request.form['description']
    alarm_time_str = request.form['alarm_time']
    alarm_time = datetime.strptime(alarm_time_str, '%Y-%m-%dT%H:%M')
    notify_before = request.form.get('notify_before_minutes', type=int) or 0
    group_id = request.form.get('group_id', type=int)

    if not group_id:
        flash('No group selected!', 'error')
        return redirect(request.referrer or url_for('index'))

    alarm = Alarm(title=title, description=description, alarm_time=alarm_time,
                  group_id=group_id, notify_before_minutes=notify_before)
    db.session.add(alarm)
    db.session.commit()
    flash('Alarm added successfully!', 'success')
    return redirect(url_for('view_group', group_id=group_id))

@app.route('/add_group', methods=['POST'])
def add_group():
    name = request.form.get('group_name', '').strip()
    if not name:
        flash('Group name cannot be empty!', 'error')
    elif name.lower() == 'general':
        flash('Cannot use "General" as group name!', 'error')
    elif Group.query.filter_by(name=name).first():
        flash(f'Group "{name}" already exists!', 'error')
    else:
        db.session.add(Group(name=name))
        db.session.commit()
        flash(f'Group "{name}" created!', 'success')
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_alarm(id):
    alarm = Alarm.query.get_or_404(id)
    group_id = alarm.group_id
    db.session.delete(alarm)
    db.session.commit()
    flash('Alarm deleted!', 'success')
    return redirect(url_for('view_group', group_id=group_id))

@app.route('/delete_group/<int:group_id>', methods=['POST'])
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    if group.name == 'General':
        flash('Cannot delete the General group!', 'error')
    else:
        Alarm.query.filter_by(group_id=group_id).delete()
        db.session.delete(group)
        db.session.commit()
        flash(f'Group "{group.name}" deleted!', 'success')
    return redirect(url_for('index'))

@app.route('/toggle_done/<int:id>', methods=['POST'])
def toggle_done(id):
    alarm = Alarm.query.get_or_404(id)
    alarm.is_done = not alarm.is_done
    db.session.commit()
    return redirect(url_for('view_group', group_id=alarm.group_id))

@app.route('/service-worker.js')
def serve_sw():
    return send_from_directory('static', 'service-worker.js', cache_timeout=0)

@app.route('/alarm-worker.js')
def serve_alarm_worker():
    resp = send_from_directory('static', 'alarm-worker.js')
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Group.query.filter_by(name='General').first():
            db.session.add(Group(name='General'))
            db.session.commit()
    app.run(debug=True, host='0.0.0.0', port=5000) 