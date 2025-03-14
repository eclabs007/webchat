from flask import Flask, render_template, request, jsonify, session, url_for
from flask_socketio import SocketIO, emit, join_room
import threading
import time
import uuid,re
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

LLM_API_URL = "YOUR_LLM_API_URL"
LLM_API_KEY = "YOUR_LLM_API_KEY"

def query_data(query):
    time.sleep(1)
    if "weather" in query.lower():
        return "The weather is sunny."
    elif "stocks" in query.lower():
        return "Stock prices are fluctuating."
    else:
        return "No specific data found."

def get_llm_response(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "prompt": prompt,
            "max_tokens": 150,
        }
        response = requests.post(LLM_API_URL, headers=headers, json=data, stream=True)

        if response.status_code == 200:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    decoded_chunk = chunk.decode("utf-8")
                    yield decoded_chunk
        else:
            yield f"Error: LLM API returned status code {response.status_code}"

    except Exception as e:
        yield f"Error: {e}"
# Dictionary to store context variables for each session
session_contexts = {}
@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html', session_id=session['session_id'])
@socketio.on('connect')
def handle_connect():
    session_id = session.get('session_id')
    if session_id:
        join_room(session_id)
        # Initialize context variables for the session
        session_contexts[session_id] = {"context_ID": None} #initialize context id to none.

@socketio.on('disconnect')
def handle_disconnect():
    session_id = session.get('session_id')
    if session_id:
        # Clean up context variables when the session disconnects
        if session_id in session_contexts:
            del session_contexts[session_id]

    

@socketio.on('message')
def handle_message(data):
    user_message = data['message']
    session_id = session.get('session_id')
    emit('loading', room=session_id)
    emit('stream', {'data': '<div class="bot-message">Loading...</div>'}, room=session_id)

    def process_and_send():
        data_result = query_data(user_message)
        prompt = f"{user_message}\nData: {data_result}\nResponse:"

        socketio.emit('clear_last_message', room=session_id)

        for chunk in get_llm_response(prompt):
            socketio.emit('stream', {'data': chunk}, room=session_id)

        socketio.emit('done_loading', room=session_id)

    threading.Thread(target=process_and_send).start()

@socketio.on('issue_summary')
def handle_issue_summary(data):
    issue_id = data['issueId']
    session_id = session.get('session_id')
    emit('loading', room=session_id)
    emit('stream', {'data': '<div class="bot-message">Please be patient, working on summary...</div>'}, room=session_id)

    with app.app_context():
        # Access session context
        context = session_contexts.get(session_id)
        if context:
            context["context_ID"] = issue_id # Update Context ID.

        data_result = query_data(f"summary for issue {issue_id}")
        prompt = f"summary for issue {issue_id}\nData: {data_result}\nResponse:"
        socketio.emit('clear_last_message', room=session_id)

        response_chunks = []
        for chunk in get_llm_response(prompt):
            response_chunks.append(chunk)

        formatted_response = "".join(response_chunks)

        def format_bold(match):
            if match.group(1):
                return "<b>" + match.group(1) + "</b>"
            return ""

        formatted_response = re.sub(r'\*\*(.*?)\*\*', format_bold, formatted_response)
        formatted_response = formatted_response.replace("\n", "<br>")

        socketio.emit('stream', {'data': formatted_response}, room=session_id)
        socketio.emit('done_loading', room=session_id)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return url_for('static', filename=filename)

if __name__ == '__main__':
    socketio.run(app, debug=True)