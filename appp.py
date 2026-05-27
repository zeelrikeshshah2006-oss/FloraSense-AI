from flask import Flask, render_template, request,redirect, url_for, session

import os
import numpy as np
import tensorflow as tf
from tensorflow import keras    
from PIL import Image
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)

model = keras.models.load_model('C:\\Users\\Zeel\\OneDrive\\Desktop\\aicw project\\train_model.keras')


# ---------------- LOGIN PAGE ----------------
login_page = """
<h2>Login Page</h2>
<form method="POST" action="/login">
    <input type="email" name="email" placeholder="Enter Email" required><br><br>
    <input type="password" name="password" placeholder="Enter Password" required><br><br>
    <button type="submit">Login</button>
</form>
"""

# ---------------- DASHBOARD PAGE ----------------
dashboard_page = """
<h2>Dashboard</h2>
<h3>Welcome {{user}}</h3>

<a href="/predict">Go to Prediction Page</a><br><br>
<a href="/logout">Logout</a>
"""

# ---------------- PREDICTION PAGE (dummy) ----------------
predict_page = """
<h2>Flower Prediction Page</h2>
<p>Upload image and predict here (add model later)</p>

<a href="/dashboard">Back</a>
"""

# ---------------- ROUTES ----------------

@app.route('/')
def home():
    return login_page

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    # simple check (replace with MongoDB later)
    if email == "admin@gmail.com" and password == "1234":
        session['user'] = email
        return redirect(url_for('dashboard'))
    else:
        return "Invalid Login ❌"

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        return dashboard_page
    return redirect(url_for('home'))

@app.route('/predict')
def predict():
    if 'user' in session:
        return render_template_string(predict_page)
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=True)

classes = [
    'daisy_downymildew',
    'daisy_healthy' ,
    'daisy_rust' ,
    'rose_affected_fungal',
    'rose_blackspot',
    'rose_healthy',
    'sunflower_aster_yellow',
    'sunflower_healthy',
    'sunflower_sclerotinia_headrot'
            ]

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def predict_image(image_path):
    img = Image.open(image_path)
    img = img.resize((224, 224))
    img_array = np.array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    prediction = model.predict(img_array)
    predicted_index = np.argmax(prediction)
    predicted_class = classes[predicted_index]
    return predicted_class
@app.route('/', methods=['GET', 'POST'])
def home():
    result = ""
    confidence = 0
    image_path = None

    if request.method == "POST":
        # 1. get uploaded file
        file = request.files["image"]

        # 2. save image
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(image_path)

        # 3. prediction
        result, confidence = predict_image(image_path)

        # 4. store in MongoDB
        collection.insert_one({
            "image": file.filename,
            "prediction": result,
            "confidence": confidence,
            "time": datetime.now()
        })

    return render_template(
        "index.html",
        result=result,
        confidence=confidence,
        image=image_path
    )

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)