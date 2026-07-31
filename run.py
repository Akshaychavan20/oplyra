import os
from app import create_app, db
from app.models import User, Project, Content, SEOAnalysis, AnalyticsLog

# Get configuration name from environment variable (default to development)
config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

# Flask shell context helper
# Running 'flask shell' will automatically import db and the models for interactive testing.
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Project': Project,
        'Content': Content,
        'SEOAnalysis': SEOAnalysis,
        'AnalyticsLog': AnalyticsLog
    }

if __name__ == '__main__':
    # Default parameters for local hosting
    app.run(host='127.0.0.1', port=5000)
