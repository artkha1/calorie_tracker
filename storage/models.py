from flask_sqlalchemy import SQLAlchemy
from datetime import date
from collections import OrderedDict

db = SQLAlchemy()


class Record:
    def __init__(self, timestamp, info, user_id, record_id):
        self.id = record_id
        self.timestamp = timestamp
        self.info = info
        self.user_id = user_id


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)


class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fdc_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    calories = db.Column(db.Float, default=0)
    protein = db.Column(db.Float, default=0)
    fat = db.Column(db.Float, default=0)
    carbs = db.Column(db.Float, default=0)


class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey('food.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    quantity = db.Column(db.Float, nullable=False, default=1)

    user = db.relationship('User', backref=db.backref('log_entries', lazy=True))
    food = db.relationship('Food', backref=db.backref('log_entries', lazy=True))


class DBRecordManager:
    def __init__(self, db):
        self._db = db

    def create_record(self, user_id, timestamp, info):
        # info: {fdc_id: quantity}  (always one entry from update_log)
        user = User.query.filter_by(username=user_id).first()
        if not user:
            user = User(username=user_id)
            self._db.session.add(user)
            self._db.session.flush()

        for fdc_id, quantity in info.items():
            food = Food.query.filter_by(fdc_id=fdc_id).first()
            if not food:
                continue
            entry = LogEntry(
                user_id=user.id,
                food_id=food.id,
                date=timestamp.date(),
                quantity=quantity,
            )
            self._db.session.add(entry)

        self._db.session.commit()

    def query_user_records(self, user_id, start_time=None, end_time=None):
        user = User.query.filter_by(username=user_id).first()
        if not user:
            return {}

        query = LogEntry.query.filter_by(user_id=user.id)
        if start_time:
            query = query.filter(LogEntry.date >= start_time.date())
        if end_time:
            query = query.filter(LogEntry.date < end_time.date())

        results = OrderedDict()
        for entry in query.order_by(LogEntry.id).all():
            results[entry.id] = Record(
                timestamp=entry.date,
                info={entry.food.fdc_id: entry.quantity},
                user_id=user_id,
                record_id=entry.id,
            )
        return results

    def remove_record(self, record_id):
        entry = LogEntry.query.get(record_id)
        if entry:
            self._db.session.delete(entry)
            self._db.session.commit()
