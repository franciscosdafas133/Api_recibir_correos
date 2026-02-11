from flask import Flask, request, jsonify
from flask_cors import CORS
import imaplib
import email
from email.header import decode_header
from datetime import datetime
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuración de servidores de correo
EMAIL_CONFIGS = {
    'gmail': {
        'imap': {'host': 'imap.gmail.com', 'port': 993}
    },
    'outlook': {
        'imap': {'host': 'outlook.office365.com', 'port': 993}
    },
    'yahoo': {
        'imap': {'host': 'imap.mail.yahoo.com', 'port': 993}
    }
}

def detect_provider(email_address):
    """Detecta el proveedor de correo automáticamente"""
    if '@gmail.com' in email_address:
        return 'gmail'
    elif '@outlook.com' in email_address or '@hotmail.com' in email_address:
        return 'outlook'
    elif '@yahoo.com' in email_address:
        return 'yahoo'
    return 'gmail'

@app.route('/', methods=['GET'])
def home():
    """Endpoint de prueba"""
    return jsonify({
        'status': 'ok',
        'message': 'API de Lectura de Correos de HOY para DIFY',
        'version': '1.0',
        'funcionalidad': 'Lee únicamente correos no leídos del día de hoy'
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/leer-correos-hoy', methods=['POST'])
def leer_correos_hoy():
    """
    Lee SOLO los correos no leídos del día de hoy
    
    Body JSON:
    {
        "email": "usuario@gmail.com",
        "password": "app_password",
        "cantidad": 20
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se enviaron datos'
            }), 400
        
        email_user = data.get('email')
        password = data.get('password')
        cantidad = data.get('cantidad', 20)
        
        if not email_user or not password:
            return jsonify({
                'success': False,
                'error': 'Email y password son requeridos'
            }), 400
        
        logger.info(f"Leyendo correos de HOY de {email_user}")
        
        # Detectar proveedor
        provider = detect_provider(email_user)
        config = EMAIL_CONFIGS[provider]['imap']
        
        # Conectar a IMAP
        mail = imaplib.IMAP4_SSL(config['host'], config['port'])
        mail.login(email_user, password)
        mail.select('inbox')
        
        # Obtener fecha de HOY
        today = datetime.now().strftime("%d-%b-%Y")
        
        # Buscar SOLO correos de HOY no leídos
        search_criteria = f'(SINCE {today} UNSEEN)'
        logger.info(f"Criterio de búsqueda: {search_criteria}")
        
        status, messages = mail.search(None, search_criteria)
        
        if status != 'OK':
            mail.close()
            mail.logout()
            return jsonify({
                'success': False,
                'error': 'No se pudieron buscar correos'
            }), 500
        
        email_ids = messages[0].split()
        
        # Si no hay correos de hoy
        if not email_ids:
            mail.close()
            mail.logout()
            return jsonify({
                'success': True,
                'cantidad': 0,
                'correos': [],
                'fecha_busqueda': today,
                'mensaje': f'No hay correos no leídos del día de hoy ({today})'
            })
        
        # Limitar cantidad
        email_ids = email_ids[-cantidad:] if len(email_ids) > cantidad else email_ids
        
        correos = []
        
        for email_id in email_ids:
            try:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    continue
                
                msg = email.message_from_bytes(msg_data[0][1])
                
                # Decodificar asunto
                subject_header = msg['Subject']
                if subject_header:
                    subject_parts = decode_header(subject_header)
                    subject = ''
                    for content, encoding in subject_parts:
                        if isinstance(content, bytes):
                            subject += content.decode(encoding if encoding else 'utf-8', errors='ignore')
                        else:
                            subject += str(content)
                else:
                    subject = '(Sin asunto)'
                
                from_email = msg.get('From', 'Desconocido')
                date = msg.get('Date', 'Fecha desconocida')
                
                # Extraer cuerpo
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        
                        if content_type == 'text/plain' and 'attachment' not in content_disposition:
                            try:
                                body = part.get_payload(decode=True).decode(errors='ignore')
                                break
                            except:
                                pass
                else:
                    try:
                        body = msg.get_payload(decode=True).decode(errors='ignore')
                    except:
                        body = "No se pudo leer el contenido"
                
                correos.append({
                    'id': email_id.decode(),
                    'de': from_email,
                    'asunto': subject,
                    'fecha': date,
                    'cuerpo': body[:1000]
                })
                
            except Exception as e:
                logger.error(f"Error procesando correo {email_id}: {str(e)}")
                continue
        
        mail.close()
        mail.logout()
        
        logger.info(f"Se leyeron {len(correos)} correos de HOY")
        
        return jsonify({
            'success': True,
            'cantidad': len(correos),
            'correos': correos,
            'fecha_busqueda': today,
            'mensaje': f'Se encontraron {len(correos)} correos no leídos de hoy'
        })
        
    except imaplib.IMAP4.error as e:
        logger.error(f"Error IMAP: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error de autenticación. Verifica email y App Password'
        }), 401
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error del servidor: {str(e)}'
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)