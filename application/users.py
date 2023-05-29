import functools
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for, Response, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from application.db import get_db, log
import re
import json #to get data from js

bp = Blueprint('users', __name__, url_prefix='/users')

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    admin = session.get('admin')
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM user WHERE id = ?', (user_id,)
        ).fetchone()

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('users.login'))

        return view(**kwargs)

    return wrapped_view

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session['admin'] == 0:
            flash("Administrator login required!")
            return redirect(url_for('users.settings'))

        return view(**kwargs)

    return wrapped_view

#defines the index page
@bp.route('/', methods=['GET','POST'])
@login_required
@admin_required #only admins can view userlist
def index():
    if request.method == 'POST': #register user
        username = request.form['username'].capitalize()
        password = request.form['password']
        privilege = request.form['privilege']
        db = get_db()
        error = None

        if re.compile('[^0-9a-zA-Z]+').search(username) or len(username) > 20: #ensures no special charecters are present in username, should prevent injection attacks
            error = "Invalid Username"
        elif not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif not privilege:
            error = 'Privilege is required.'

        if privilege == 'admin':
            admin = 1
        else:
            admin = 0

        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, admin, password) VALUES (?, ?, ?)",
                    (username, admin, generate_password_hash(password)),
                )
                print(generate_password_hash(password)) #temp
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                session.clear()
                return redirect(url_for("users.login"))

        if error is not None:
            flash(error) 

    return render_template('users/list.html')

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username'].capitalize()
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM user WHERE username = ?', (username,)
        ).fetchone()

        if re.compile('[^0-9a-zA-Z]+').search(username): #ensures no special charecters are present in username, should prevent injection attacks
            error = "Invalid Username"
        elif user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            log("INFO","Logging in user " + username.lower())
            session.clear()
            session['user_id'] = user['id']
            session['admin'] = user['admin']
            return redirect(url_for('index'))
        else:
            log("WARN", "Failed login - user " + username.lower() + ": " + error)
            flash(error)

    return render_template('users/login.html')

@bp.route('/settings', methods=('GET', 'POST'))
@login_required
def user():
    if request.method == 'POST':
        db = get_db()
        user_id = session["user_id"]
        error = None
        if "change_password" in request.form:
            oldpassword = request.form['oldpassword']
            newpassword = request.form['newpassword']
            if not oldpassword or not newpassword: #check that the form is complete
                error = 'All fields are required.'

            user_data = db.execute('SELECT * FROM user WHERE id = {}'.format(user_id,)).fetchone() #grab user data to check old passowrd

            if user_data is None: #catch database errors
                error = 'Database error.'
            elif not check_password_hash(user_data['password'], oldpassword): #check that the old password is correct
                error = 'Incorrect password.'

            log("INFO","User " + user_data['username'].lower() + " changed their password")
            db.execute("UPDATE user SET password = '{}' WHERE id = '{}'".format(generate_password_hash(newpassword),user_id)) #update password
            db.commit()
        elif "change_username" in request.form:
            password = request.form['password']
            newusername = request.form['newusername'].capitalize()
            
            if not password or not newusername: #check that the form is complete
                error = 'All fields are required.'

            user_data = db.execute('SELECT * FROM user WHERE id = {}'.format(user_id,)).fetchone() #grab user data to check password

            if re.compile('[^0-9a-zA-Z]+').search(newusername) or len(newusername) > 20: #ensures no special charecters are present in username, should prevent injection attacks
                error = "Invalid New Username"
            elif user_data is None: #catch database errors
                error = 'Database error.'
            elif not check_password_hash(user_data['password'], password): #check that the password is correct
                error = 'Incorrect password.'

            log("INFO","User " + user_data['username'].lower() + " changed their username to " + newusername.lower())
            db.execute("UPDATE user SET username = '{}' WHERE id = '{}'".format(newusername,user_id)) #update username
            db.commit()
        flash(error)

    return render_template('users/settings.html')


#defines a users function which is called when /getusers is accessed
@bp.route('/getusers', methods=['GET', 'POST'])
@login_required
@admin_required
def getusers():
    db = get_db()
    user_id = session["user_id"]
    user_data = db.execute('SELECT * FROM user')
    users = []
    for user in user_data:
        role = "Admin" if user['admin'] == 1 else "User"
        users.append({'id': user['id'], 'username': user['username'], 'role': role})

    return jsonify(users)

#reset password route
@bp.route('/resetpassword', methods=['GET'])
@login_required
@admin_required
def resetpassword():
    if request.method == 'GET':
        user_id = request.args.get('id')
        username = request.args.get('user')
        password = request.args.get('password')
        db = get_db()
        log("INFO","Admin " + g.user['username'].lower() + " changed " + username + "'s password!")
        db.execute("UPDATE user SET password = '{}' WHERE id = '{}'".format(generate_password_hash(password), user_id)) #update password
        db.commit()

    return Response(status=200)

#delete user route
@bp.route('/deleteuser', methods=['GET'])
@login_required
@admin_required
def deleteuser():
    if request.method == 'GET':
        admin = True if request.args.get('admin') == "Admin" else False

        db = get_db()

        user_data = db.execute('SELECT * FROM user WHERE admin = 1').fetchall()
        if admin and len(user_data) == 1:
            return Response(status=403)

        user_id = request.args.get('id')
        username = request.args.get('user')
        log("INFO","Admin " + g.user['username'].lower() + " deleted " + username + "'s account!")
        db.execute("DELETE FROM user WHERE id = '{}'".format(user_id))
        db.commit()

        return Response(status=200)
    
#change role route
@bp.route('/changerole', methods=['GET'])
@login_required
@admin_required
def changerole():
    admin = True if request.args.get('admin') == "Admin" else False

    db = get_db()

    user_data = db.execute('SELECT * FROM user WHERE admin = 1').fetchall()
    if admin and len(user_data) == 1:
        return Response(status=403)

    user_id = request.args.get('id')
    username = request.args.get('user')

    if not admin:
        log("INFO","Admin " + g.user['username'].lower() + " made " + username + " an admin!")
        db.execute("UPDATE user SET admin = 1 WHERE id = '{}'".format(user_id))
    else:
        log("INFO","Admin " + g.user['username'].lower() + " demoted " + username + " to a user!")
        db.execute("UPDATE user SET admin = 0 WHERE id = '{}'".format(user_id))
    db.commit()

    return Response(status=200)