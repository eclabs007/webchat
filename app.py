from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room
import threading
import time
import uuid  # For generating unique session IDs
import requests  # For LLM API calls (replace with your chosen LLM)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Important for sessions
socketio = SocketIO(app)

# Replace with your actual LLM API endpoint and key
LLM_API_URL = "YOUR_LLM_API_URL"
LLM_API_KEY = "YOUR_LLM_API_KEY"

# Dummy data retrieval function (replace with your actual data query)
def query_data(query):
    # Simulate a data query
    time.sleep(1)  # Simulate some processing time
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
            "max_tokens": 150,  # Adjust as needed
            # Add other LLM parameters as needed
        }
        response = requests.post(LLM_API_URL, headers=headers, json=data, stream=True) # stream response for live output

        if response.status_code == 200:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    decoded_chunk = chunk.decode("utf-8")
                    yield decoded_chunk # yield chunks of text to send to frontend
        else:
            yield f"Error: LLM API returned status code {response.status_code}"

    except Exception as e:
        yield f"Error: {e}"

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4()) # create unique session id for each user
    return render_template('index.html', session_id=session['session_id'])

@socketio.on('connect')
def handle_connect():
    session_id = session.get('session_id')
    if session_id:
        join_room(session_id) # Join a unique room for each session

@socketio.on('message')
def handle_message(data):
    user_message = data['message']
    session_id = session.get('session_id')
    emit('loading', room=session_id) # Send loading signal

    def process_and_send():
        data_result = query_data(user_message)
        prompt = f"{user_message}\nData: {data_result}\nResponse:"

        for chunk in get_llm_response(prompt):
            socketio.emit('stream', {'data': chunk}, room=session_id)

        socketio.emit('done_loading', room=session_id) # Send done loading signal

    threading.Thread(target=process_and_send).start()

if __name__ == '__main__':
    socketio.run(app, debug=True)