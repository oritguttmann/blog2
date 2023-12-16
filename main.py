from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
from sqlalchemy import ForeignKey
from typing import List
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship, Mapped, mapped_column
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm
import os
global logged_in
logged_in = 0


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login


# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db") #'sqlite:///posts.db'
db = SQLAlchemy()
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="blog_posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(250), nullable=False)
    img_url = db.Column(db.String(250), nullable=False)


# TODO: Create a User table for all your registered users. ***V***
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    blog_posts: Mapped[List["BlogPost"]] = relationship(back_populates="user")


with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def admin_only(func):
    def wrapper(*args, **kwargs):
        if current_user.id == 1:
            return func(*args,**kwargs)
        else:
            return abort(403)
    wrapper.__name__ = func.__name__
    return wrapper

# TODO: Use Werkzeug to hash the user's password when creating a new user. ***V***
@app.route('/register', methods=["GET","POST"])
def register():
    global logged_in
    form = RegisterForm()
    if form.validate_on_submit():
        password_plain = form.password.data
        password_hash = generate_password_hash(password=password_plain, method="pbkdf2:sha256", salt_length=8)
        new_user = User(
            email= form.email.data,
            password=password_hash,
            name=form.name.data
        )
        try:
            with app.app_context():
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                logged_in = 1
                return redirect(url_for('get_all_posts'))
        except sqlalchemy.exc.IntegrityError:
            logged_in = 0
            flash('The typed mail is already exists. Please log in.')
            return redirect(url_for('login'))
    return render_template("register.html", form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=["GET", "POST"])
def login():
    global logged_in
    form = LoginForm()
    if form.validate_on_submit():
        with app.app_context():
            email = form.email.data
            password = form.password.data
            user_by_mail = db.session.execute(db.select(User).where(User.email == email)).scalar()
            if user_by_mail and check_password_hash(user_by_mail.password, password):
                login_user(user_by_mail)
                logged_in = 1
                return redirect(url_for('get_all_posts'))
            else:
                if not user_by_mail:
                    logged_in = 0
                    flash('The typed mail was not found. Please try again.')
                    return render_template("login.html", form=form)
                else:
                    logged_in = 0
                    flash('Incorrect password. Please try again.')
                    return render_template("login.html",form=form)
    return render_template("login.html",form=form)


@app.route('/logout')
def logout():
    global logged_in
    logged_in = 0
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    global logged_in
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    if logged_in:
        curr_id = current_user.id
    else:
        curr_id = 0
    return render_template("index.html", all_posts=posts, log_in=logged_in, admin= curr_id)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>")
def show_post(post_id):
    global logged_in
    requested_post = db.get_or_404(BlogPost, post_id)
    if logged_in:
        curr_id = current_user.id
    else:
        curr_id = 0
    return render_template("post.html", post=requested_post, log_in=logged_in, admin= curr_id)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    global logged_in
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
            author_id = current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, log_in=logged_in)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    global logged_in
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, log_in=logged_in)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    global logged_in
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    global logged_in
    return render_template("about.html", log_in=logged_in)


@app.route("/contact")
def contact():
    global logged_in
    return render_template("contact.html", log_in=logged_in)


if __name__ == "__main__":
    app.run(debug=False, port=5002)
