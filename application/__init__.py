import os
import traceback

from flask import Flask

from . import backend, control, db, users


def create_app(test_config=None):
    
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY='TeAFL25rAaZutN8lloICx9Tm3cKZl7JEvKvu7gne4dNRKNFVATMuAN3Us3z5NKTd',
        DATABASE=os.path.join(app.instance_path, 'database.sqlite'),
    )
    
    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    try:
        db.init_app(app)
        app.register_blueprint(users.bp)
        app.register_blueprint(control.bp)
        app.add_url_rule('/', endpoint='index')
        backend.start(app) # calls our backend function, which starts a sub-process with the application context, even if nobody loads the web app
    except Exception:
        print(traceback.format_exc()) # unfortunately, logging doesn't work at this point in application loading
        
    return app
