from flask import Flask, Response, render_template, request
import json

from services.pipeline import run_pipeline_optimized
from routes.auth import auth_bp
from config import DevelopmentConfig

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

app.register_blueprint(auth_bp)

# ✅ ADD THIS
@app.route("/")
def home():
    return render_template("CRITIC_OS_Landing_Page.html")

@app.route("/analysis")
def analysis():
    return render_template("CRITIC_OS_Analysis_Page.html")

@app.route("/dev-load")
def dev_load():
    """Bypass route to load mock data for rapid persona testing."""
    try:
        with open("lyrics.json", "r") as f:
            data = json.load(f)
        # We'll return a page that sets the session storage and redirects
        return f"""
        <html><body><script>
        sessionStorage.setItem('enrichedSongs', JSON.stringify({json.dumps(data['data'])}));
        sessionStorage.setItem('userName', 'DEV_USER');
        window.location.href = '/analysis';
        </script></body></html>
        """
    except Exception as e:
        return f"Failed to load lyrics.json: {str(e)}", 500

@app.route("/stream/<session_id>", methods=["POST"])
def stream(session_id):
    enriched_songs = request.json.get("songs", [])
    persona = request.json.get("persona", "normal") # Get persona from request
    custom_prompt = request.json.get("custom_prompt") # Get custom prompt from request
    profile_custom_prompt = request.json.get("profile_custom_prompt") # Get profile custom prompt
    collection_name = request.json.get("collection_name", "your collection")
    
    def event_stream():
        try:
            for e in run_pipeline_optimized(enriched_songs, persona, custom_prompt, profile_custom_prompt, collection_name):
                yield f"data: {json.dumps(e)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','msg':str(e)})}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/stream-answer", methods=["POST"])
def stream_answer():
    song = request.json.get("song", {})
    persona = request.json.get("persona", "normal")
    interaction_state = request.json.get("state", "")
    custom_prompt = request.json.get("custom_prompt")

    from services.roast import generate_roast_stream
    
    def event_stream():
        try:
            # We pass interaction_state to ground the roast
            for token in generate_roast_stream(song, persona, custom_prompt, interaction_state):
                yield f"data: {json.dumps({'type': 'roast_token', 'text': token})}\n\n"
            yield f"data: {json.dumps({'type': 'roast_end'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','msg':str(e)})}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True)
