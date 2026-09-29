import http.server
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

# -------------------------------------------------------------------
# Environment Loader (Python Standard Library Only)
# -------------------------------------------------------------------
def load_env(filepath=None, override=False):
    """
    Load key-value pairs from a .env file into os.environ.
    Uses Python standard library only.
    """
    if filepath is None:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    
    if not os.path.isfile(filepath):
        return

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Strip matching surrounding quotes if present
                if len(val) >= 2 and (
                    (val[0] == '"' and val[-1] == '"')
                    or (val[0] == "'" and val[-1] == "'")
                ):
                    val = val[1:-1]
                if key and (override or key not in os.environ):
                    os.environ[key] = val
    except Exception as e:
        print(f"[WARN] Error reading .env file: {e}", file=sys.stderr)


# Load environment variables on startup
load_env()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def get_candidate_models():
    primary = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()
    fallbacks = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "groq/compound-mini", "openai/gpt-oss-120b", "llama-3.1-8b-instant"]
    models = [primary]
    for m in fallbacks:
        if m not in models:
            models.append(m)
    return models

LENGTH_MAP = {
    "short": "approximately 100 words",
    "medium": "approximately 300 words",
    "long": "approximately 600 words",
}

def create_ssl_context():
    """
    Creates an SSL context. Disables VERIFY_X509_STRICT on Windows to prevent
    'Basic Constraints of CA cert not marked critical' errors on corporate/OS root certs.
    """
    ctx = ssl.create_default_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx

# -------------------------------------------------------------------
# Request Handler
# -------------------------------------------------------------------
class ClintFlowHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP Request Handler serving ClintFlow static frontend and
    handling secure server-side AI generation proxying.
    """

    def end_headers(self):
        # Basic security headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        super().end_headers()

    def do_GET(self):
        # Serve TechStartup.html as root
        if self.path == "/" or self.path == "":
            self.path = "/TechStartup.html"
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/generate":
            self.handle_generate()
        else:
            self.send_json_response(404, {"error": "Not Found"})

    def send_json_response(self, status_code, payload):
        response_data = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_data)))
        self.end_headers()
        self.wfile.write(response_data)

    def handle_generate(self):
        # Check environment variable; re-read .env to allow hot reload
        load_env(override=True)
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            self.send_json_response(500, {
                "error": "Server configuration error: GROQ_API_KEY environment variable is not set."
            })
            return

        # Read and parse JSON request body
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_json_response(400, {"error": "Empty request body."})
                return
            if content_length > 65536:  # 64KB max payload safety limit
                self.send_json_response(413, {"error": "Request body too large."})
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            self.send_json_response(400, {"error": "Invalid JSON format."})
            return

        prompt = str(data.get("prompt", "")).strip()
        if not prompt:
            self.send_json_response(400, {"error": "Prompt cannot be empty."})
            return

        content_type = str(data.get("contentType", "blog")).strip()
        tone_type = str(data.get("toneType", "professional")).strip()
        length_type = str(data.get("lengthType", "medium")).strip()
        language_type = str(data.get("languageType", "English")).strip()
        seo_boost = bool(data.get("seoBoost", False))

        length_desc = LENGTH_MAP.get(length_type, "approximately 300 words")

        # Correct spacing and punctuation in prompt construction
        user_message = (
            f"Write a {content_type} about: {prompt} in {language_type}. "
            f"Use a {tone_type} writing style. Make it {length_desc}."
        )

        if seo_boost:
            user_message += (
                " Optimize this content for SEO by naturally including "
                "the main keyword multiple times and using SEO best practices."
            )

        candidate_models = get_candidate_models()
        ssl_ctx = create_ssl_context()

        for model_name in candidate_models:
            groq_payload = json.dumps({
                "model": model_name,
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            }).encode("utf-8")

            req = urllib.request.Request(
                GROQ_API_URL,
                data=groq_payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 ClintFlow/1.0"
                },
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:
                    resp_data = resp.read().decode("utf-8")
                    groq_json = json.loads(resp_data)

                    choices = groq_json.get("choices", [])
                    if choices and "message" in choices[0] and "content" in choices[0]["message"]:
                        generated_content = choices[0]["message"]["content"]
                        self.send_json_response(200, {"content": generated_content})
                        return
                    else:
                        self.send_json_response(502, {"error": "Invalid response received from AI service."})
                        return

            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="replace")
                print(f"[ERROR] Groq API ({model_name}) HTTP {e.code}: {error_body}", file=sys.stderr)
                
                # If model is not found, attempt next fallback model
                if e.code == 404:
                    continue

                err_msg = f"AI service error (HTTP {e.code}). Please try again later."
                if e.code == 401:
                    err_msg = "Invalid Groq API Key. Please provide a valid GROQ_API_KEY in your .env file."
                elif e.code == 429:
                    err_msg = "Rate limit reached on Groq API. Please wait a moment and try again."
                else:
                    try:
                        err_json = json.loads(error_body)
                        if "error" in err_json and "message" in err_json["error"]:
                            err_msg = err_json["error"]["message"]
                    except Exception:
                        pass

                self.send_json_response(e.code, {"error": err_msg})
                return

            except urllib.error.URLError as e:
                print(f"[ERROR] Failed to reach Groq API: {e.reason}", file=sys.stderr)
                self.send_json_response(504, {
                    "error": "Network timeout or unable to reach AI service."
                })
                return
            except Exception as e:
                print(f"[ERROR] Unexpected server exception: {e}", file=sys.stderr)
                self.send_json_response(500, {
                    "error": "An unexpected server error occurred."
                })
                return

        self.send_json_response(502, {
            "error": "None of the configured AI models are available on this Groq account."
        })


# -------------------------------------------------------------------
# Server Runner
# -------------------------------------------------------------------
def run():
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    
    # Change working directory to this script's directory for proper static file serving
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, ClintFlowHandler)
    print(f"[INFO] ClintFlow backend server running at http://{host}:{port}/")
    print(f"[INFO] Serving frontend from: {base_dir}")
    print("[INFO] Press Ctrl+C to stop.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down ClintFlow server.")
        httpd.server_close()


if __name__ == "__main__":
    run()
