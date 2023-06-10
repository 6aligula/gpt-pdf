from flask import Flask, request, render_template, redirect, url_for
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from werkzeug.utils import secure_filename
import PyPDF2
from wtforms import SubmitField
import openai
import time 
from openai.error import RateLimitError
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os

openai.api_key = os.getenv("OPENAI_API_KEY")
app = Flask(__name__)
CORS(app) 
socketio = SocketIO(app)

app.debug = False
if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler

    file_handler = RotatingFileHandler('flask_app.log', maxBytes=1024 * 1024 * 100, backupCount=20)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

pdf_text = ""

def generate_summary_with_retry(messages):
    wait_time = 5
    while True:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )

            return response
        except RateLimitError:
            app.logger.warning(f"Se excedió el límite de tasa. Reintentando en {wait_time} segundos...") 
            time.sleep(wait_time)
            wait_time *= 2

@socketio.on('generate_summary')
def handle_generate_summary(prompt):
    summaries = []
    max_length = 1000
    sections = [pdf_text[i:i + max_length] for i in range(0, len(pdf_text), max_length)]

    for i, section in enumerate(sections):
        messages = [
            {"role": "system", "content": "Tu eres un amable asistente"},
            {"role": "user", "content": f"{prompt} de : {section}"}
        ]
        response = generate_summary_with_retry(messages)

        summary = response.choices[0].message["content"]
        summaries.append(summary)
        app.logger.info(f"Generando resumen para la sección {i + 1}") 
        
        emit('new_summary', summary)
    
    app.logger.info(f"Resumen finalizado") 
    emit('new_summary', "finish")
    return " ".join(summaries)

def extract_text_from_pdf(file_path):
    pdf_file_obj = open(file_path, 'rb')
    pdf_reader = PyPDF2.PdfReader(pdf_file_obj)
    text = ""
    for page_num in range(len(pdf_reader.pages)):
        page_obj = pdf_reader.pages[page_num]
        text += page_obj.extract_text()
    pdf_file_obj.close()
    return text

@app.route('/upload', methods=['POST'])
def upload():
    global pdf_text
    client_ip = request.headers.get('X-Real-IP', request.remote_addr)
    if request.method == 'POST':
        try: 
            pdf = request.files['pdf']
            filename = secure_filename(pdf.filename)
            app.logger.info(f"Guardando el archivo: {filename} del cliente: {client_ip}")
            pdf.save(filename)
            pdf_text = extract_text_from_pdf(filename)
            app.logger.info(f"Longitud del texto extraído: {len(pdf_text)}") 
            if pdf_text:
                socketio.emit('pdf_processing_done', "El PDF ha sido procesado correctamente. Ahora procede a escribir tu peticion a GPT3.5-Turbo")
        except Exception as e:
            socketio.emit('pdf_processing_error', str(e))
            app.logger.error(f"Error al procesar el PDF: {str(e)}")
    return redirect(url_for('home'))

@app.route('/')
def home():
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        ip_addresses = x_forwarded_for.split(',')
        client_ip = ip_addresses[0]
    else:
        client_ip = request.remote_addr

    app.logger.info(f"Rendering home page, cliente: {client_ip}")
    return render_template('index.html')

if __name__ == '__main__':
    app.logger.info('Starting Flask app')
    socketio.run(app, debug=False)