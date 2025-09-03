from flask import Flask, render_template, request, jsonify, send_from_directory, abort
import os
import datetime
from translate import translate_pdf
import docx
import markdown
from weasyprint import HTML
import threading
import shutil
import logging
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/app.log') if os.path.exists('/app/logs') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'pdf'}

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# In-memory store for translation progress
translation_progress = {}

def allowed_file(filename):
    """Check if file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/health')
def health_check():
    """Health check endpoint for Docker."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()}), 200

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            logger.warning("Upload attempt with no file part")
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.warning("Upload attempt with empty filename")
            return jsonify({'error': 'No selected file'}), 400
        
        # Secure the filename
        filename = secure_filename(file.filename)
        
        # Validate file type
        if not allowed_file(filename):
            logger.warning(f"Upload attempt with invalid file type: {filename}")
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed.'}), 400
        
        # Check file size (this is handled by Flask's MAX_CONTENT_LENGTH, but we can add explicit check)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"Upload attempt with oversized file: {filename} ({file_size} bytes)")
            return jsonify({'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB'}), 400
        
        # Remove .pdf extension for directory name
        dir_name = os.path.splitext(filename)[0]
        pdf_dir = os.path.join(DATA_DIR, dir_name)
        
        # Create directory if it doesn't exist
        os.makedirs(pdf_dir, exist_ok=True)
        
        filepath = os.path.join(pdf_dir, filename)
        file.save(filepath)
        
        logger.info(f"File uploaded successfully: {filename} ({file_size} bytes)")
        
        # Start translation in a background thread
        thread = threading.Thread(target=translate_pdf, args=(filepath, translation_progress))
        thread.daemon = True  # Daemon thread for clean shutdown
        thread.start()
        
        return jsonify({'success': 'File uploaded and translation started', 'filename': filename}), 202
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'An error occurred during upload'}), 500

@app.route('/progress/<filename>')
def progress(filename):
    progress = translation_progress.get(filename, 0)
    return jsonify({'percentage': progress})

@app.route('/files')
def list_files():
    files = []
    for f in os.listdir(DATA_DIR):
        if os.path.isdir(os.path.join(DATA_DIR, f)):
            path = os.path.join(DATA_DIR, f)
            mtime = os.path.getmtime(path)
            files.append({
                'name': f,
                'timestamp': datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
    return jsonify(sorted(files, key=lambda x: x['timestamp'], reverse=True))

@app.route('/view/<dirname>')
def view_file(dirname):
    filepath = os.path.join(DATA_DIR, dirname, 'translated.md')
    if not os.path.exists(filepath):
        abort(404)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'content': content})

@app.route('/download/<dirname>/<format>')
def download_file(dirname, format):
    filepath = os.path.join(DATA_DIR, dirname, 'translated.md')
    if not os.path.exists(filepath):
        abort(404)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        md_content = f.read()

    if format == 'md':
        return send_from_directory(os.path.join(DATA_DIR, dirname), 'translated.md', as_attachment=True)
    elif format == 'txt':
        return md_content, {'Content-Disposition': f'attachment; filename={dirname}.txt'}
    elif format == 'doc':
        doc = docx.Document()
        doc.add_paragraph(md_content)
        doc_path = filepath.replace('.md', '.docx')
        doc.save(doc_path)
        return send_from_directory(os.path.dirname(filepath), os.path.basename(doc_path), as_attachment=True)
    elif format == 'pdf':
        html_content = markdown.markdown(md_content)
        pdf_path = filepath.replace('.md', '.pdf')
        HTML(string=html_content).write_pdf(pdf_path)
        return send_from_directory(os.path.dirname(filepath), os.path.basename(pdf_path), as_attachment=True)
    else:
        abort(400)

@app.route('/delete/<dirname>', methods=['POST'])
def delete_file(dirname):
    dir_path = os.path.join(DATA_DIR, dirname)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
        return jsonify({'success': 'File deleted'}), 200
    else:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
