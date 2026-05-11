import os
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
load_dotenv()

from flask import Flask, Response, render_template, request
from flask_session import Session
import redis
import json

from services.pipeline import run_pipeline_optimized
from routes.auth import auth_bp

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# ==========================
# REDIS SESSION CONFIG
# ==========================
from services.cache import redis_client_raw
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = redis_client_raw

# Initialize Session
Session(app)

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
    
    from flask import session
    from services.cache import has_reached_limit, set_user_limit_spent
    user_id = session.get('user_id')

    # Guard: Check limit before streaming
    if user_id and has_reached_limit(user_id):
        return jsonify({
            "error": "limit_reached",
            "message": "You've already performed your one-time analysis."
        }), 403

    def event_stream():
        try:
            # Mark as spent once the stream actually starts
            if user_id:
                set_user_limit_spent(user_id)

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

@app.route("/stream-profile-answer", methods=["POST"])
def stream_profile_answer():
    songs = request.json.get("songs", [])
    persona = request.json.get("persona", "normal")
    interaction_state = request.json.get("state", "")
    profile_custom_prompt = request.json.get("profile_custom_prompt")

    from services.roast import generate_profile_roast_stream
    
    def event_stream():
        try:
            for token in generate_profile_roast_stream(songs, persona, profile_custom_prompt, interaction_state):
                yield f"data: {json.dumps({'type': 'profile_token', 'text': token})}\n\n"
            yield f"data: {json.dumps({'type': 'profile_end'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','msg':str(e)})}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/save-report", methods=["POST"])
def save_report():
    from flask import session
    from services.cache import save_user_report
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "No user ID"}), 401
    
    report_data = request.json
    save_user_report(user_id, report_data)
    return jsonify({"status": "success"})

@app.route("/dossier")
def dossier_page():
    from flask import session
    from services.cache import get_user_report
    user_id = session.get('user_id')
    
    # Optional: fetch user info for fallback if report doesn't exist
    from routes.auth import get_sp_client
    sp = get_sp_client()
    user_info = {}
    if sp:
        user = sp.current_user()
        images = user.get("images", [])
        user_info = {
            "display_name": user.get("display_name", "User"),
            "image": images[0]["url"] if images else None
        }

    report = get_user_report(user_id) if user_id else None
    
    return render_template("CRITIC_OS_Dossier_Page.html", report=report, user=user_info)

if __name__ == "__main__":
    app.run(debug=True)
