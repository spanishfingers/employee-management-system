import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'payroll-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance', 'project.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False