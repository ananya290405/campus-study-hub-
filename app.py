"""CampusNotes - enhanced notes-sharing portal.

Local demo mode is the default. Optional cloud mode uses Amazon S3 + DynamoDB
when BUCKET and TABLE environment variables are configured with valid AWS credentials.
"""
import json, os, socket, time, uuid
from datetime import datetime
from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

BUCKET = os.environ.get("BUCKET")
TABLE = os.environ.get("TABLE")
REGION = os.environ.get("AWS_REGION", "ap-south-1")
CLOUD = bool(BUCKET and TABLE)
ALLOWED = {"pdf", "doc", "docx", "ppt", "pptx", "txt", "png", "jpg", "jpeg", "zip"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

if CLOUD:
    import boto3
    s3 = boto3.client("s3", region_name=REGION)
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)
else:
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_data")
    FILES_DIR = os.path.join(DATA_DIR, "files")
    DB_FILE = os.path.join(DATA_DIR, "notes.json")
    os.makedirs(FILES_DIR, exist_ok=True)

def list_notes():
    if CLOUD:
        resp = table.scan()
        items = resp.get("Items", [])
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
            items += resp.get("Items", [])
        return items
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return []

def save_note(item, fileobj):
    if CLOUD:
        s3.upload_fileobj(fileobj, BUCKET, item["s3_key"],
                          ExtraArgs={"ServerSideEncryption": "AES256",
                                     "ContentType": fileobj.mimetype or "application/octet-stream"})
        table.put_item(Item=item)
    else:
        fileobj.save(os.path.join(FILES_DIR, os.path.basename(item["s3_key"])))
        notes = list_notes()
        notes.append(item)
        with open(DB_FILE, "w", encoding="utf-8") as fh:
            json.dump(notes, fh, ensure_ascii=False, indent=2)

def get_note(note_id):
    if CLOUD:
        return table.get_item(Key={"note_id": note_id}).get("Item")
    return next((n for n in list_notes() if n["note_id"] == note_id), None)

@app.template_filter("datefmt")
def datefmt(ts):
    return datetime.fromtimestamp(int(ts)).strftime("%d %b %Y")

def allowed(name):
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED

@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    subject = request.args.get("subject", "").strip().lower()
    all_notes = list_notes()
    seen = {}
    for n in all_notes:
        seen.setdefault(n["subject"].strip().lower(), n["subject"].strip())
    subjects = sorted(seen.values(), key=str.lower)
    notes = all_notes
    if subject:
        notes = [n for n in notes if n["subject"].strip().lower() == subject]
    if q:
        notes = [n for n in notes if q in n["title"].lower() or q in n["subject"].lower()
                 or q in n.get("uploader", "").lower() or q in n.get("filename", "").lower()]
    notes.sort(key=lambda n: int(n.get("created", 0)), reverse=True)
    return render_template("index.html", notes=notes, subjects=subjects, q=q, subject=subject,
                           host=socket.gethostname(), mode="Amazon S3 + DynamoDB" if CLOUD else "local disk (demo mode)",
                           total_count=len(all_notes), subject_count=len(subjects))

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    uploader = request.form.get("uploader", "").strip()
    if not (f and f.filename and title and subject and uploader):
        flash("Please complete every field and choose a file.", "error")
        return redirect(url_for("index"))
    if not allowed(f.filename):
        flash("File type not supported. Use PDF, Office files, TXT, PNG, JPG or ZIP.", "error")
        return redirect(url_for("index"))
    note_id = str(uuid.uuid4())
    ext = f.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f.filename) or f"note.{ext}"
    if "." not in filename:
        filename = f"note.{ext}"
    item = {"note_id": note_id, "title": title[:100], "subject": subject[:50],
            "uploader": uploader[:50], "filename": filename,
            "s3_key": f"notes/{note_id}-{filename}", "created": int(time.time())}
    try:
        save_note(item, f)
    except Exception:
        app.logger.exception("Could not save uploaded note")
        flash("Upload failed. Please try again.", "error")
        return redirect(url_for("index"))
    flash(f'Uploaded "{item["title"]}" successfully.', "ok")
    return redirect(url_for("index"))

@app.route("/download/<note_id>")
def download(note_id):
    item = get_note(note_id)
    if not item:
        abort(404)
    if CLOUD:
        url = s3.generate_presigned_url("get_object",
            Params={"Bucket": BUCKET, "Key": item["s3_key"],
                    "ResponseContentDisposition": f'attachment; filename="{item["filename"]}"'},
            ExpiresIn=300)
        return redirect(url)
    return send_from_directory(FILES_DIR, os.path.basename(item["s3_key"]),
                               as_attachment=True, download_name=item["filename"])

@app.errorhandler(413)
def too_large(_):
    flash("That file is larger than the 10 MB upload limit.", "error")
    return redirect(url_for("index"))

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=not CLOUD)
