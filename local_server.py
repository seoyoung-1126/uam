import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "forma_extension")

# 메모리에 제미나이 데이터를 임시 대기시킬 공간
current_params = {"status": "waiting", "params": {}}


def load_dotenv(env_path=None):
    """외부 패키지 없이 .env 파일을 로드합니다."""
    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def call_gemini_api(user_prompt, geometry_preview):
    """Gemini API를 서버 측에서 호출합니다 (.env의 API 키 사용)."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY가 설정되지 않았습니다. "
            "uam/.env.example을 참고해 uam/.env 파일을 생성하세요."
        )

    prompt_text = (
        "당신은 세계 최고의 UAM 버티포트 B.I.M 설계자입니다.\n"
        f'사용자의 설계 컨셉: "{user_prompt}"\n'
        f"현재 Forma 3D 매스 좌표 일부: {json.dumps(geometry_preview, ensure_ascii=False)}\n"
        "위 컨셉과 공기역학을 반영하여, 다이나모(Dynamo as a Service)에서 매스를 생성할 때 "
        "사용할 이상적인 수치 4가지(폭, 깊이, 높이, 유선형 모서리 반경)를 JSON 형태로만 제안해 주세요."
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}]
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_data = json.loads(error_body)
            message = error_data.get("error", {}).get("message", error_body)
        except json.JSONDecodeError:
            message = error_body
        raise ValueError(f"Gemini API 오류: {message}") from e


class CORSRequestHandler(BaseHTTPRequestHandler):
    def _read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode("utf-8"))

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_static(self, filename):
        filepath = os.path.join(STATIC_DIR, filename)
        if not os.path.isfile(filepath):
            self._send_json(404, {"error": "Not found"})
            return

        content_type, _ = mimetypes.guess_type(filepath)
        if content_type is None:
            content_type = "application/octet-stream"

        with open(filepath, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.end_headers()
        self.wfile.write(content)

    # 어떤 포트(3000번 등)에서 날아오든 CORS 에러 없이 100% 문을 열어주는 마법의 헤더
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    # 사전 요청(Preflight) 완벽 승인
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        global current_params

        if self.path == "/api/gemini/generate":
            try:
                body = self._read_json_body()
                user_prompt = body.get("userPrompt", "")
                geometry_preview = body.get("geometryPreview", [])

                if not user_prompt.strip():
                    self._send_json(400, {"error": "userPrompt가 비어 있습니다."})
                    return

                gemini_response = call_gemini_api(user_prompt, geometry_preview)
                if gemini_response.get("error"):
                    raise ValueError(gemini_response["error"].get("message", "알 수 없는 오류"))

                gemini_text = gemini_response["candidates"][0]["content"]["parts"][0]["text"]
                print("\n[서버] 🌟 Gemini AI 응답 수신 완료")
                self._send_json(200, {"text": gemini_text})
            except (ValueError, KeyError, IndexError) as e:
                print(f"\n[서버] ⚠️ Gemini API 오류: {e}")
                self._send_json(500, {"error": str(e)})
            return

        if self.path == "/api/dynamo/next_params":
            body = self._read_json_body()
            current_params = body
            print("\n[서버] 🌟 제미나이 데이터 수신 완료:", current_params)
            self._send_json(200, {"msg": "success"})
            return

        if self.path.startswith("/api/dynamo/"):
            # connect, candidates, error, applied 등 Dynamo 브릿지 부가 엔드포인트
            self._send_json(200, {"msg": "ok"})
            return

        self._send_json(404, {"error": "Not found"})

    def do_GET(self):
        global current_params
        path = urllib.parse.urlparse(self.path).path

        if path in ("/", "/index.html"):
            self._serve_static("index.html")
            return

        if path == "/api/dynamo/next_params":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            self.wfile.write(json.dumps(current_params).encode("utf-8"))

            if current_params["status"] == "optimizing":
                print("\n[서버] 🚀 Dynamo로 데이터 전송 완료! (Revit 매스 자동 갱신됨)")
                current_params = {"status": "waiting", "params": {}}
            return

        self._send_json(404, {"error": "Not found"})


if __name__ == "__main__":
    server_address = ("", 3000)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    print("==================================================")
    print("🚀 UAM 최적화 다이나모 중계 서버가 3000 포트에서 켜졌습니다!")
    print("   📋 Forma 확장 URL: http://localhost:3000")
    if GEMINI_API_KEY:
        print(f"   ✅ GEMINI_API_KEY 로드 완료 (모델: {GEMINI_MODEL})")
    else:
        print("   ⚠️  GEMINI_API_KEY 미설정 — .env.example을 참고해 .env 파일을 생성하세요.")
    print("   1. 웹 패널에서 'Gemini AI 최적화 요청' 버튼을 누르세요.")
    print("   2. 웹 패널에서 'Dynamo DaaS로 전송' 버튼을 누르세요.")
    print("   3. 레빗(Revit)에서 Dynamo 스크립트를 '실행'하세요.")
    print("==================================================")
    httpd.serve_forever()
