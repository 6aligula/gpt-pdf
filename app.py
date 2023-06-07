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

openai.api_key = os.getenv("OPEN_API_KEY")
app = Flask(__name__)
CORS(app) 
socketio = SocketIO(app)

pdf_text = ""  # variable global para almacenar el texto del PDF

def generate_summary_with_retry(messages):
    wait_time = 5  # Tiempo de espera inicial
    while True:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
            )
            print("API request successful")  # Debug point
            print("Response:", response)  # New debug point

            return response
        except RateLimitError:
            print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            wait_time *= 2  # Aumenta el tiempo de espera para el próximo intento

@socketio.on('generate_summary')
def handle_generate_summary(prompt):
    summaries = []
    max_length = 1000  # ajusta este valor según sea necesario
    print('prompt: ', prompt)
    # divide el texto en secciones
    sections = [pdf_text[i:i + max_length] for i in range(0, len(pdf_text), max_length)]
    print(f"Number of sections: {len(sections)}")  # Debug point

    for i, section in enumerate(sections):
        messages = [
            {"role": "system", "content": "Tu eres un amable asistente"},
            {"role": "user", "content": f"{prompt} de : {section}"}
        ]
        print(messages)
        response = generate_summary_with_retry(messages)  # Usa la nueva función con reintento

        summary = response.choices[0].message["content"]
        summaries.append(summary)
        print(f"Generated summary for section {i + 1}")  # Debug point
        
        # emitir el resumen a medida que se genera
        emit('new_summary', summary)

    emit('new_summary', "Se ha completado con exito todo el proceso")
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
    if request.method == 'POST':
        pdf = request.files['pdf']
        filename = secure_filename(pdf.filename)
        print(f"File name: {filename}")  # Debug point
        pdf.save(filename)
        pdf_text = extract_text_from_pdf(filename)
        print(f"Text length: {len(pdf_text)}")  # Debug point
    return redirect(url_for('home'))

@app.route('/')
def home():
    return render_template('index.html')


if __name__ == '__main__':
    socketio.run(app, debug=True)

