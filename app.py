import os
import sqlite3
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

WORK_START_HOUR = int(os.getenv('WORK_START_HOUR', 9))
WORK_END_HOUR = int(os.getenv('WORK_END_HOUR', 18))
SLOT_MINUTES = int(os.getenv('SLOT_MINUTES', 30))
BOXES = int(os.getenv('BOXES', 2))
BRAND_NAME = os.getenv('BRAND_NAME', 'CarWash')
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'admin')

TZ = ZoneInfo('Europe/Kyiv')
DAY_NAMES = ['понеділок', 'вівторок', 'середа', 'четвер', 'пʼятниця', 'субота', 'неділя']

app = Flask(__name__)


def init_db():
    conn = sqlite3.connect('carwash.db')
    c = conn.cursor()
    c.execute(
        '''CREATE TABLE IF NOT EXISTS bookings (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               user_name TEXT NOT NULL,
               car_type TEXT NOT NULL,
               service TEXT NOT NULL,
               date TEXT NOT NULL,
               time TEXT NOT NULL,
               created_at TEXT NOT NULL
           )'''
    )
    conn.commit()
    conn.close()


init_db()

SERVICES = ['Зовнішня мийка', 'Комплексна мийка', 'Хімчистка']
CAR_TYPES = ['Седан', 'Позашляховик', 'Мікроавтобус']


@app.context_processor
def inject_brand():
    return dict(brand=BRAND_NAME)


def get_available_slots(date_str: str):
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    start = datetime.combine(date_obj, time(hour=WORK_START_HOUR), tzinfo=TZ)
    end = datetime.combine(date_obj, time(hour=WORK_END_HOUR), tzinfo=TZ)
    delta = timedelta(minutes=SLOT_MINUTES)
    slots = []
    conn = sqlite3.connect('carwash.db')
    c = conn.cursor()
    current = start
    while current < end:
        t_str = current.strftime('%H:%M')
        c.execute('SELECT COUNT(*) FROM bookings WHERE date=? AND time=?', (date_str, t_str))
        if c.fetchone()[0] < BOXES:
            slots.append(t_str)
        current += delta
    conn.close()
    return slots


@app.route('/')
def index():
    return redirect(url_for('book'))


@app.route('/book', methods=['GET', 'POST'])
def book():
    today = datetime.now(TZ).date()
    selected_date = request.values.get('date', today.strftime('%Y-%m-%d'))
    message = None
    if request.method == 'POST':
        name = request.form['name']
        service = request.form['service']
        car_type = request.form['car_type']
        date_val = request.form['date']
        time_val = request.form['time']
        conn = sqlite3.connect('carwash.db')
        c = conn.cursor()
        c.execute(
            'INSERT INTO bookings (user_name, car_type, service, date, time, created_at) VALUES (?,?,?,?,?,?)',
            (name, car_type, service, date_val, time_val, datetime.now(TZ).isoformat()),
        )
        conn.commit()
        conn.close()
        message = 'Запис збережено!'
    slots = get_available_slots(selected_date)
    return render_template(
        'book.html',
        services=SERVICES,
        car_types=CAR_TYPES,
        slots=slots,
        selected_date=selected_date,
        message=message,
    )


@app.route('/my', methods=['GET'])
def my_bookings():
    name = request.values.get('name')
    records = []
    if name:
        conn = sqlite3.connect('carwash.db')
        c = conn.cursor()
        c.execute(
            'SELECT service, car_type, date, time FROM bookings WHERE user_name=? ORDER BY date, time',
            (name,),
        )
        records = c.fetchall()
        conn.close()
    return render_template('my.html', bookings=records, name=name)


@app.route('/about')
def about():
    return render_template('about.html', start=WORK_START_HOUR, end=WORK_END_HOUR)


@app.route('/admin')
def admin():
    token = request.args.get('token')
    if token != ADMIN_TOKEN:
        return 'Заборонено', 403
    date_str = request.args.get('date')
    if not date_str:
        date_str = datetime.now(TZ).strftime('%Y-%m-%d')
    conn = sqlite3.connect('carwash.db')
    c = conn.cursor()
    c.execute(
        'SELECT id, user_name, car_type, service, time FROM bookings WHERE date=? ORDER BY time',
        (date_str,),
    )
    bookings = c.fetchall()
    conn.close()
    day_name = DAY_NAMES[datetime.strptime(date_str, '%Y-%m-%d').weekday()]
    today_str = datetime.now(TZ).strftime('%Y-%m-%d')
    tomorrow_str = (datetime.now(TZ) + timedelta(days=1)).strftime('%Y-%m-%d')
    return render_template(
        'admin.html',
        bookings=bookings,
        date=date_str,
        day_name=day_name,
        token=token,
        today=today_str,
        tomorrow=tomorrow_str,
    )


@app.route('/admin/cancel/<int:booking_id>')
def admin_cancel(booking_id):
    token = request.args.get('token')
    date_str = request.args.get('date')
    if token != ADMIN_TOKEN:
        return 'Заборонено', 403
    conn = sqlite3.connect('carwash.db')
    c = conn.cursor()
    c.execute('DELETE FROM bookings WHERE id=?', (booking_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin', token=token, date=date_str))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
