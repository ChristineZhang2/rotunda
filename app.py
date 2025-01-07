from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///purple_insta.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

GOOGLE_CIVIC_API_KEY = os.environ.get(
    'GOOGLE_CIVIC_API_KEY', 'AIzaSyDZRssXSb5m-0SoX4JQJd5ohkMaWg9G-vM')


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    zip_code = db.Column(db.String(10))


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.Column(db.Integer, default=0)
    comments = db.relationship('Comment', backref='post', lazy='dynamic')


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def init_db():
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")


@app.route('/')
@login_required
def index():
    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template('index.html', posts=posts)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        zip_code = request.form.get('zip_code')

        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email,
                        password=generate_password_hash(password, method='pbkdf2:sha256'),
                        zip_code=zip_code)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/post', methods=['POST'])
@login_required
def create_post():
    content = request.form.get('content')
    new_post = Post(content=content, user_id=current_user.id)
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/like/<int:post_id>')
@login_required
def like_post(post_id):
    post = Post.query.get(post_id)
    if post:
        post.likes += 1
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('content')
    new_comment = Comment(content=content, user_id=current_user.id, post_id=post_id)
    db.session.add(new_comment)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/civic_quiz', methods=['GET', 'POST'])
@login_required
def civic_quiz():
    if request.method == 'POST':
        answers = [
            int(request.form.get('answer1', 0)),
            int(request.form.get('answer2', 0)),
            int(request.form.get('answer3', 0))
        ]
        score = calculate_civic_engagement_score(answers)
        return render_template('quiz_result.html', score=score)
    return render_template('civic_quiz.html')


def calculate_civic_engagement_score(answers):
    total_questions = len(answers)
    correct_answers = sum(answers)
    score = (correct_answers / total_questions) * 100
    return round(score, 1)


@app.route('/representatives')
@login_required
def representatives():
    if not current_user.zip_code:
        flash('Please update your zip code in your profile.')
        return redirect(url_for('index'))

    try:
        zip_code = current_user.zip_code
        api_url = f"https://www.googleapis.com/civicinfo/v2/representatives?key={GOOGLE_CIVIC_API_KEY}&address={zip_code}"
        response = requests.get(api_url)
        response.raise_for_status()

        data = response.json()
        offices = data.get('offices', [])
        officials = data.get('officials', [])

        reps = []
        for office in offices:
            for index in office['officialIndices']:
                official = officials[index]
                rep = {
                    'name': official.get('name'),
                    'office': office.get('name'),
                    'party': official.get('party'),
                    'phones': official.get('phones', []),
                    'urls': official.get('urls', []),
                    'emails': official.get('emails', []),
                    'photoUrl': official.get('photoUrl')
                }
                reps.append(rep)

        return render_template('representatives.html', representatives=reps)
    except requests.RequestException as e:
        flash(f'Error fetching representative information: {str(e)}')
        return redirect(url_for('index'))


@app.route('/contact_rep/<rep_name>', methods=['GET', 'POST'])
@login_required
def contact_rep(rep_name):
    if request.method == 'POST':
        message = request.form.get('message')
        flash(f'Message sent to {rep_name}: {message}')
        return redirect(url_for('representatives'))
    return render_template('contact_rep.html', rep_name=rep_name)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=8005)
