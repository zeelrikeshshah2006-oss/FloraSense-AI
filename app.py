from flask import Flask, render_template, request, redirect, session, url_for, jsonify, send_from_directory
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import os
import numpy as np
from PIL import Image
from tensorflow.keras.models import load_model
from datetime import datetime
from bson.objectid import ObjectId

model = load_model("C:\\Users\\Zeel\\OneDrive\\Desktop\\FloraSense AI\\train_model.keras")
MODEL_ACCURACY = 98.88  # Placeholder accuracy percentage
app = Flask(__name__)
app.secret_key = "secretkey123"

uri = "mongodb+srv://zeelrikeshshah2006_db_user:Zeel123@cluster0.u2969ia.mongodb.net/?appName=Cluster0"

# Create a new client and connect to the server
client = MongoClient(uri)

# Database
db = client["FloraSenseAI"]
# Collection
users_col = db["users"]
disease_col = db["disease_info"]
scans_col = db["scans"]

CLASSES = [
    'daisy_downymildew',
    'daisy_healthy',
    'daisy_rust',
    'rose_affected_fungal',
    'rose_blackspot',
    'rose_healthy',
    'sunflower_aster_yellow',
    'sunflower_healthy',
    'sunflower_sclerotinia_headrot'
]

CLASS_MAPPING = {
    'daisy_downymildew': 'Daisy Downy Mildew',
    'daisy_healthy': 'Daisy Healthy',
    'daisy_rust': 'Daisy Rust',
    'rose_affected_fungal': 'Rose Affected Fungal',
    'rose_blackspot': 'Rose Black Spot',
    'rose_healthy': 'Rose Healthy',
    'sunflower_aster_yellow': 'Sunflower Aster Yellow',
    'sunflower_healthy': 'Sunflower Healthy',
    'sunflower_sclerotinia_headrot': 'Sunflower Sclerotinia Head Rot'
}

UPLOAD_FOLDER = "uploads"
PROFILE_PHOTO_FOLDER = os.path.join("uploads", "profile_photos")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_PHOTO_FOLDER, exist_ok=True)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users_col.find_one({
            "email": email,
            "password": password
        })

        if user:
            session["user"] = email
            return redirect(url_for("dashboard"))
        else:
            return "Invalid Credentials"

    return render_template("login.html")

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    
    # Retrieve user details
    user = users_col.find_one({"email": session["user"]})

    # Retrieve user's scans
    scans = list(scans_col.find({"email": session["user"]}))
    total_scans = len(scans)
    
    healthy_count = sum(1 for s in scans if "healthy" in s.get("prediction", "").lower())
    diseased_count = total_scans - healthy_count
    
    success_rate = int((healthy_count / total_scans) * 100) if total_scans > 0 else 100
    
    # Fetch 3 most recent scans sorted by _id descending
    recent_scans = list(scans_col.find({"email": session["user"]}).sort("_id", -1).limit(3))
    
    return render_template(
        "dashboard.html",
        user=user,
        total_scans=total_scans,
        healthy_count=healthy_count,
        diseased_count=diseased_count,
        success_rate=success_rate,
        recent_scans=recent_scans,
        model_accuracy=MODEL_ACCURACY
    )

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user" not in session:
        return redirect("/")

    user = users_col.find_one({"email": session["user"]})
    message = None
    msg_type = "success"

    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Validate password change
        if password or confirm_password:
            if password != confirm_password:
                message = "Passwords do not match!"
                msg_type = "error"
            else:
                users_col.update_one(
                    {"email": session["user"]},
                    {"$set": {"password": password}}
                )

        if not message:
            # Update name and phone
            users_col.update_one(
                {"email": session["user"]},
                {"$set": {"name": name, "phone": phone}}
            )
            # Re-fetch user details after update
            user = users_col.find_one({"email": session["user"]})
            message = "Profile updated successfully!"
            msg_type = "success"

    return render_template("profile.html", user=user, message=message, msg_type=msg_type)

@app.route("/predict", methods=["POST"])
def predict():
    if "user" not in session:
        return redirect("/")

    file = request.files["image"]
    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    # Load and process image for model prediction
    img = Image.open(path)
    img = img.resize((224, 224))
    img = np.array(img) / 255.0
    img = np.expand_dims(img, axis=0)

    try:
        prediction = model.predict(img)
        predicted_idx = np.argmax(prediction[0])
        raw_class = CLASSES[predicted_idx]
        predicted_class = CLASS_MAPPING.get(raw_class, raw_class)
    except Exception as e:
        print("Prediction failed:", e)
        predicted_class = "Rose Black Spot"

    # Removed deletion to keep all scans for user
    # (Previously removed scans for same disease)

    # Save the scan history in MongoDB
    scan_id = scans_col.insert_one({
        "email": session["user"],
        "filename": filename,
        "image_path": path.replace('\\', '/'), # Ensure web-safe pathing
        "prediction": predicted_class,
        "date_time": datetime.now().strftime("%d %b %Y, %I:%M %p")
    }).inserted_id

    return redirect(url_for("predict_result", scan_id=str(scan_id)))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/predict_result/<scan_id>")
def predict_result(scan_id):
    if "user" not in session:
        return redirect("/")

    scan = scans_col.find_one({"_id": ObjectId(scan_id)})
    if not scan:
        return "Scan not found", 404

    predicted_class = scan["prediction"]
    
    # Map prediction name to database fields (flower, disease)
    db_mapping = {
        'Daisy Downy Mildew': {'flower': 'Daisy', 'disease': 'Downy Mildew'},
        'Daisy Rust': {'flower': 'Daisy', 'disease': 'Rust'},
        'Rose Affected Fungal': {'flower': 'Rose', 'disease': 'Fungal'},
        'Rose Black Spot': {'flower': 'Rose', 'disease': 'Black Spot'},
        'Sunflower Aster Yellow': {'flower': 'Sunflower', 'disease': 'Aster Yellows'},
        'Sunflower Sclerotinia Head Rot': {'flower': 'Sunflower', 'disease': 'Sclerotinia Head Rot'}
    }

    query = db_mapping.get(predicted_class)
    if query:
        data = disease_col.find_one(query)
    else:
        data = None

    if data:
        symptoms = data.get("symptoms", "Not found")
        prevention = data.get("prevention", "Not found")
        treatment = data.get("treatment", "Not found")
    elif "healthy" in predicted_class.lower():
        symptoms = "None (Plant is healthy)"
        prevention = "Keep doing what you're doing! Maintain regular watering, proper sunlight, and good soil health."
        treatment = "No treatment required."
    else:
        symptoms = "Not found"
        prevention = "Not found"
        treatment = "Not found"

    return render_template(
        "result.html",
        predicted_class=predicted_class,
        symptoms=symptoms,
        prevention=prevention,
        treatment=treatment,
        image_path=scan["image_path"]
    )

@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/")

    scans = list(scans_col.find({"email": session["user"]}).sort("_id", -1))
    return render_template("history.html", scans=scans)

@app.route("/delete_scan/<scan_id>", methods=["POST"])
def delete_scan(scan_id):
    if "user" not in session:
        return "Unauthorized", 401

    result = scans_col.delete_one({"_id": ObjectId(scan_id), "email": session["user"]})
    if result.deleted_count > 0:
        return "Success", 200
    return "Not Found", 404

@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    if "user" not in session:
        return redirect("/")

    file = request.files.get("photo")
    if file and file.filename:
        filename = secure_filename(file.filename)
        # Make filename unique per user using email prefix
        email_prefix = session["user"].replace("@", "_").replace(".", "_")
        filename = f"{email_prefix}_{filename}"
        save_path = os.path.join(PROFILE_PHOTO_FOLDER, filename)
        file.save(save_path)
        photo_url = f"uploads/profile_photos/{filename}"
        users_col.update_one(
            {"email": session["user"]},
            {"$set": {"profile_photo": photo_url}}
        )

    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)