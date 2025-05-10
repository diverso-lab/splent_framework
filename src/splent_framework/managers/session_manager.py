from flask_session import Session


class SessionManager:
    def __init__(self, app):
        self.sess = Session()
        self.sess.init_app(app)
