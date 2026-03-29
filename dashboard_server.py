from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
# Permitem conexiuni de oriunde pentru dashboard
socketio = SocketIO(app, cors_allowed_origins="*")

game_data = {
    "p1_score": 0, "p1_lives": 5, "p1_status": "ACTIVE",
    "p2_score": 0, "p2_lives": 5, "p2_status": "ACTIVE",
}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('update_game')
def handle_update(data):
    global game_data
    game_data.update(data)
    emit('render_dashboard', game_data, broadcast=True)

if __name__ == '__main__':
    # Ruleaza pe portul 5000
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
