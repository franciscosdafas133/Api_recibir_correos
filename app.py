from flask import Flask, request, jsonify
from flask_cors import CORS
import imaplib
import email
from email.header import decode_header
from datetime import datetime
import logging
import os

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "API Gmail IMAP funcionando",
    })


@app.route("/leer-correos-hoy", methods=["POST"])
def leer_correos_hoy():
    data = request.get_json()

    email_user = data.get("email")
    password = data.get("password")
    cantidad = data.get("cantidad", 5)

    if not email_user or not password:
        return jsonify({"success": False, "error": "Faltan credenciales"}), 400

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(email_user, password)
        mail.select("INBOX")

        today = datetime.now().strftime("%d-%b-%Y")
        status, messages = mail.search(None, f'(UNSEEN SINCE {today})')

        if status != "OK":
            return jsonify({"success": False, "error": "No se pudo buscar correos"}), 500

        email_ids = messages[0].split()[-cantidad:]
        correos = []

        for eid in email_ids:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            subject = ""
            if msg["Subject"]:
                for part, enc in decode_header(msg["Subject"]):
                    subject += part.decode(enc or "utf-8", errors="ignore") if isinstance(part, bytes) else part

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            correos.append({
                "from": msg.get("From"),
                "subject": subject,
                "date": msg.get("Date"),
                "body": body[:1000]
            })

        mail.logout()

        return jsonify({
            "success": True,
            "cantidad": len(correos),
            "correos": correos
        })

    except imaplib.IMAP4.error:
        return jsonify({
            "success": False,
            "error": "Autenticación IMAP fallida (App Password)"
        }), 401

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
