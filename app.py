from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os
import traceback
import logging
import tiktoken
import json
import zipfile
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Update CORS configuration
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding

# Ensure upload directory exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def health_check():
    return jsonify({"status": "ok"})

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        logger.debug("Received upload request")
        
        if 'file' not in request.files:
            logger.error("No file part in request")
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        logger.debug(f"Received file: {file.filename}")
        
        if file.filename == '':
            logger.error("No selected file")
            return jsonify({"error": "No selected file"}), 400
        
        if not file.filename.endswith('.txt'):
            logger.error(f"Invalid file type: {file.filename}")
            return jsonify({"error": "Only .txt files are allowed"}), 400

        # Read the file content
        content = file.read().decode('utf-8')
        lines = content.splitlines()
        
        logger.debug(f"Successfully read file with {len(lines)} lines")
        
        response_data = {
            "filename": file.filename,
            "lines": lines
        }
        logger.debug(f"Sending response: {json.dumps(response_data)[:100]}...")  # Log first 100 chars of response
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/tokens', methods=['POST'])
def count_tokens():
    try:
        data = request.get_json()
        if not data or 'lines' not in data or 'start' not in data or 'end' not in data:
            return jsonify({"error": "Missing required fields"}), 400

        lines = data['lines']
        start = data['start']
        end = data['end']

        # Validate indices
        if not (0 <= start <= end < len(lines)):
            return jsonify({"error": "Invalid line range"}), 400

        # Get the text for the selected range
        selected_text = '\n'.join(lines[start:end + 1])
        
        # Count tokens
        tokens = tokenizer.encode(selected_text)
        token_count = len(tokens)
        
        logger.debug(f"Counted {token_count} tokens for lines {start} to {end}")
        
        return jsonify({
            "token_count": token_count,
            "start_line": start,
            "end_line": end
        })
    except Exception as e:
        logger.error(f"Error counting tokens: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/export', methods=['POST'])
def export_sections():
    try:
        data = request.get_json()
        if not data or 'sections' not in data or 'lines' not in data:
            return jsonify({'error': 'Missing required data'}), 400

        sections = data['sections']
        lines = data['lines']

        # Create a BytesIO object to store the zip file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Export each section
            for i, section in enumerate(sections):
                section_text = '\n'.join(lines[section['start']:section['end'] + 1])
                section_filename = f'section_{i + 1}.txt'
                zip_file.writestr(section_filename, section_text)

            # Create metadata
            metadata = {
                'sections': [
                    {
                        'filename': f'section_{i + 1}.txt',
                        'index': i + 1,
                        'title': section.get('title', f'Section {i + 1}'),
                        'start_line': section['start'],
                        'end_line': section['end'],
                        'token_count': section.get('tokenCount', 0),
                        'should_summarize': section.get('shouldSummarize', True)
                    }
                    for i, section in enumerate(sections)
                ],
                'total_sections': len(sections)
            }
            
            # Add metadata to zip
            zip_file.writestr('metadata.json', json.dumps(metadata, indent=2))

        # Prepare the response
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='sections.zip'
        )

    except Exception as e:
        app.logger.error(f"Export error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/replace', methods=['POST'])
def replace_text():
    try:
        data = request.get_json()
        if not data or 'lines' not in data or 'search' not in data or 'replace' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        lines = data['lines']
        search = data['search']
        replace = data['replace']

        # Replace the text in each line
        replaced_lines = [line.replace(search, replace) for line in lines]
        
        return jsonify({
            'lines': replaced_lines,
            'replacements': sum(line.count(search) for line in lines)
        })
    except Exception as e:
        logger.error(f"Error replacing text: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port) 