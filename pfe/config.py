import os

class Config:
    # Secret key (used for sessions/CSRF). Change in production.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # Default DB: XAMPP MySQL (root user, no password)
    # Use 127.0.0.1 instead of localhost to force TCP
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:@127.0.0.1:3306/pfe_db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
# config.py
class Config:
    # ... tes autres configs
    POWERBI_EMBED_URL =" https://app.powerbi.com/reportEmbed?reportId=3013134f-5f30-4f7f-81ad-14f4faa1b04e&autoAuth=true&ctid=604f1a96-cbe8-43f8-abbf-f8eaf5d85730"
