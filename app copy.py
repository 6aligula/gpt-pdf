from flask import Flask, render_template, request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from werkzeug.utils import secure_filename
import PyPDF2
from wtforms import SubmitField
import openai
import os
# esta version resume el texto cada 1000 tokens ya que el modelo solo acepta 4000 tokens como maximo
openai.api_key = os.getenv("OPEN_API_KEY")

def get_summary(text):
    summaries = []
    max_length = 1000  # ajusta este valor según sea necesario

    # divide el texto en secciones
    sections = [text[i:i + max_length] for i in range(0, len(text), max_length)]

    for section in sections:
        messages = [
            {"role": "system", "content": "Tu eres un amable asistente"},
            {"role": "user", "content": f"Necesito resumir este texto: {section}"}
        ]

        response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=messages,
          temperature=0.3,
        )

        summaries.append(response.choices[0].message["content"])

    return " ".join(summaries)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Cambia esto a una clave secreta real en producción

class UploadForm(FlaskForm):
    file = FileField(validators=[FileRequired()])
    submit = SubmitField('Upload')

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    form = UploadForm()
    text = ''
    summary = ''

    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        file.save(filename)

        text = extract_text_from_pdf(filename)
        summary = get_summary(text)

    #return render_template('upload.html', form=form, text=summary)
        os.remove(filename)

    return render_template('index.html', form=form, text=summary)

def extract_text_from_pdf(file_path):
    pdf_file_obj = open(file_path, 'rb')
    pdf_reader = PyPDF2.PdfFileReader(pdf_file_obj)
    text = ""
    for page_num in range(pdf_reader.numPages):
        page_obj = pdf_reader.getPage(page_num)
        text += page_obj.extractText()
    pdf_file_obj.close()
    return text

if __name__ == '__main__':
    app.run(debug=True)
