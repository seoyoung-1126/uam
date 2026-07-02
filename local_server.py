import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# 메모리에 제미나이 데이터를 임시 대기시킬 공간
current_params = {"status": "waiting", "params": {}}

class CORSRequestHandler(BaseHTTPRequestHandler):
    # 어떤 포트(3000번 등)에서 날아오든 CORS 에러 없이 100% 문을 열어주는 마법의 헤더
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    # 사전 요청(Preflight) 완벽 승인
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    # 1. 웹 패널에서 제미나이 수치를 쏴줄 때 (POST)
    def do_POST(self):
        global current_params
        if self.path == '/api/dynamo/next_params':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # 웹 패널에서 날아온 데이터 저장
            current_params = json.loads(post_data.decode('utf-8'))
            print("\n[서버] 🌟 제미나이 데이터 수신 완료:", current_params)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"msg": "success"}).encode('utf-8'))

    # 2. 다이나모(Revit)에서 수치를 가져갈 때 (GET)
    def do_GET(self):
        global current_params
        if self.path == '/api/dynamo/next_params':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # 다이나모에게 현재 가지고 있는 데이터를 뱉어줌
            self.wfile.write(json.dumps(current_params).encode('utf-8'))
            
            # 한 번 빼가면 다음번을 위해 다시 대기 상태로 초기화
            if current_params["status"] == "optimizing":
                print("\n[서버] 🚀 Dynamo로 데이터 전송 완료! (Revit 매스 자동 갱신됨)")
                current_params = {"status": "waiting", "params": {}}

if __name__ == '__main__':
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    print("==================================================")
    print("🚀 UAM 최적화 다이나모 중계 서버가 8080 포트에서 켜졌습니다!")
    print("   1. 웹 패널에서 'Dynamo DaaS로 전송' 버튼을 누르세요.")
    print("   2. 레빗(Revit)에서 Dynamo 스크립트를 '실행'하세요.")
    print("==================================================")
    httpd.serve_forever()
