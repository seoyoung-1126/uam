# UAM AI Optimizer

Forma 3D 매스 데이터를 Gemini AI로 최적화하고, Revit Dynamo와 연동해 매스 매개변수를 자동 갱신하는 도구입니다.

## 구성

| 파일 | 역할 |
|------|------|
| `forma_extension/index.html` | Forma 확장 패널 (데이터 추출, AI 최적화, Dynamo 전송) |
| `local_server.py` | 로컬 중계 서버 (Gemini API 호출 + Dynamo 데이터 중계) |
| `dynamo_bridge.py` | Revit Dynamo Python Script 노드용 브릿지 코드 |
| `.env` | API 키 등 환경 변수 (Git에 포함되지 않음) |

## 사전 준비

- Python 3
- Autodesk Forma (확장 패널 로드)
- Revit + Dynamo
- [Google AI Studio](https://aistudio.google.com/apikey)에서 발급한 Gemini API 키

## 설치

```bash
cd uam
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

`.env` 파일을 열어 API 키를 입력합니다.

```env
GEMINI_API_KEY=발급받은_키
```

## 사용 방법

### 1. 로컬 서버 실행

```bash
python local_server.py
```

`3000` 포트에서 서버가 실행됩니다. 시작 시 `GEMINI_API_KEY 로드 완료` 메시지가 보이면 정상입니다.

### 2. Forma 확장 패널

1. Forma 확장 설정 URL에 `http://localhost:3000` 입력
2. **실시간 지형/바람 데이터 로드** — 3D 뷰포트에서 매스를 선택한 뒤 클릭
3. 설계 컨셉 입력 후 **Gemini AI 최적화 요청** 클릭
4. **Dynamo DaaS로 모델 갱신하기** 클릭

### 3. Revit Dynamo 연동

1. Dynamo Python Script 노드에 `dynamo_bridge.py` 내용을 붙여넣기
2. 입력 연결:
   - `IN[0]`: 최적화 대상 매스 패밀리 인스턴스
   - `IN[1]`: 버티포트 후보 점 목록
3. 스크립트 실행 → AI가 제안한 높이·폭·깊이·모서리반경이 Revit 매스에 반영됨

## 데이터 흐름

```
Forma (매스 선택)
  → Gemini AI (최적화 수치 생성)
  → local_server.py (3000)
  → Dynamo (Revit 매스 갱신)
```

## 문제 해결

| 증상 | 확인 사항 |
|------|-----------|
| Gemini 호출 실패 | `local_server.py` 실행 여부, `.env`의 `GEMINI_API_KEY` |
| Dynamo 전송 실패 | 로컬 서버 3000 포트 실행 여부 |
| 매개변수 미반영 | Revit 매스에 높이/폭/깊이/모서리반경 매개변수 존재 여부 |
