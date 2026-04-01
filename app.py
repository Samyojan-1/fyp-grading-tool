from flask import Flask

# Create the Flask application
# __name__ tells Flask where to find templates, static files, etc.
app = Flask(__name__)

# This is a "route" — it tells Flask:
# "When someone visits the homepage (/), run this function"
@app.route('/')
def home():
    return '<h1>FYP Grading Tool</h1><p>It works!</p>'

# This block only runs when you execute this file directly
# (not when it's imported by something else)
if __name__ == '__main__':
    # debug=True means:
    # 1. Auto-restarts when you save changes
    # 2. Shows detailed errors in the browser
    # NEVER use debug=True in production — it's a security risk
    app.run(debug=True, port=5001)

# Just to let you know i want a different file for each service. so i know where everything is. i dont want all the features in one file. 