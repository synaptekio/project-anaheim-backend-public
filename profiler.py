# Run python profiler.py to see performance and bottlenecks on page loads and API calls
from werkzeug.middleware.profiler import ProfilerMiddleware
from app import app

app.config['PROFILE'] = True
app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])
app.run(debug = True)
