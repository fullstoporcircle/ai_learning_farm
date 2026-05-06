from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, default='default_user')
    knowledge_coins = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    knowledge_items = db.relationship('KnowledgeItem', back_populates='user', lazy='dynamic')
    plots = db.relationship('Plot', back_populates='user', lazy='dynamic')
    backpack_items = db.relationship('BackpackItem', back_populates='user', lazy='dynamic')

class KnowledgeItem(db.Model):
    __tablename__ = 'knowledge_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer, default=1)
    srs_level = db.Column(db.Integer, default=0)
    mastery = db.Column(db.Float, default=0.0)
    prerequisite_ids = db.Column(db.JSON, default=list)
    next_review_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    tags = db.Column(db.JSON, default=list)
    domain = db.Column(db.String(100), nullable=True)
    depth = db.Column(db.String(20), default='basic')

    formula = db.Column(db.Text, default='')
    derivation_steps = db.Column(db.JSON, default=list)
    common_mistakes = db.Column(db.JSON, default=list)
    application_examples = db.Column(db.JSON, default=list)

    paired_with_id = db.Column(db.Integer, db.ForeignKey('knowledge_items.id'), nullable=True)
    paired_at = db.Column(db.DateTime, nullable=True)
    difficulty_offset = db.Column(db.Float, default=0.0)

    user = db.relationship('User', back_populates='knowledge_items')
    plots = db.relationship('Plot', back_populates='knowledge_item', lazy='dynamic')
    backpack_items = db.relationship('BackpackItem', back_populates='knowledge_item', lazy='dynamic')

    paired_with = db.relationship('KnowledgeItem', remote_side=[id], uselist=False)

class Plot(db.Model):
    __tablename__ = 'plots'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('knowledge_items.id'), nullable=True)
    plot_index = db.Column(db.Integer, nullable=False)
    growth_value = db.Column(db.Integer, default=0)
    is_harvestable = db.Column(db.Boolean, default=False)
    crop_variant = db.Column(db.String(20), default='normal')
    planted_at = db.Column(db.DateTime, nullable=True)
    error_plot_correct = db.Column(db.Integer, default=0)

    user = db.relationship('User', back_populates='plots')
    knowledge_item = db.relationship('KnowledgeItem', back_populates='plots')

class BackpackItem(db.Model):
    __tablename__ = 'backpack_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('knowledge_items.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    user = db.relationship('User', back_populates='backpack_items')
    knowledge_item = db.relationship('KnowledgeItem', back_populates='backpack_items')


class StudySession(db.Model):
    __tablename__ = 'study_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('knowledge_items.id'), nullable=True)
    verify_type = db.Column(db.String(20), default='recite')
    score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())


class ExamSession(db.Model):
    __tablename__ = 'exam_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tags = db.Column(db.JSON, default=list)
    total_questions = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    avg_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())
    finished_at = db.Column(db.DateTime, nullable=True)

    answers = db.relationship('ExamAnswer', back_populates='session', lazy='dynamic')


class ExamAnswer(db.Model):
    __tablename__ = 'exam_answers'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=False)
    knowledge_item_id = db.Column(db.Integer, db.ForeignKey('knowledge_items.id'), nullable=True)
    question_text = db.Column(db.Text, default='')
    user_answer = db.Column(db.Text, default='')
    score = db.Column(db.Float, default=0.0)
    is_correct = db.Column(db.Boolean, default=False)
    correct_answer = db.Column(db.Text, default='')
    verify_type = db.Column(db.String(20), default='explain')

    session = db.relationship('ExamSession', back_populates='answers')
    knowledge_item = db.relationship('KnowledgeItem')