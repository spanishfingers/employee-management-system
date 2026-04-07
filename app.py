from flask import Flask
from flask_login import LoginManager
from config import Config
from models import db, User
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure instance folder exists
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        seed_default_users()

    return app


def seed_default_users():
    """Create default admin and employee accounts if they don't exist."""
    from models import User

    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin', base_salary=0.0)
        admin.set_password('admin123')
        db.session.add(admin)

    if not User.query.filter_by(username='employee1').first():
        emp = User(username='employee1', role='employee', base_salary=50000.0)
        emp.set_password('emp123')
        db.session.add(emp)

    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    print("=" * 50)
    print("  Employee Payroll Management System")
    print("=" * 50)
    print("  Default Credentials:")
    print("  Admin    -> username: admin     | password: admin123")
    print("  Employee -> username: employee1 | password: emp123")
    print("=" * 50)
    app.run(debug=True)