# -*- coding: utf-8 -*-
"""
[Dynamo Python Script Node 용 템플릿 코드]
이 스크립트는 Revit 내 Dynamo의 Python Script 노드에 복사해 넣는 코드입니다.
로컬 AI 대시보드(http://localhost:3000)와 Revit 모델링 매개변수를 실시간 브릿지 연동합니다.
"""

import sys
import clr

# Revit API 라이브러리 로드
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *

clr.AddReference('RevitServices')
import RevitServices
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

# 시스템 기본 모듈 로드 (Python 2/3 호환 처리)
try:
    # Python 3 (CPython)
    import urllib.request as urllib_req
    import urllib.error as urllib_err
except ImportError:
    # Python 2 (IronPython)
    import urllib2 as urllib_req
import json

doc = DocumentManager.Instance.CurrentDBDocument

# ─── Dynamo 입력 매개변수 ────────────────────────────
# IN[0]: 최적화 대상 Revit 매스 패밀리 인스턴스 (Element)
# IN[1]: 버티포트 후보 점 목록 (Points)
mass_element = UnwrapElement(IN[0]) if IN[0] else None
candidate_points = IN[1] if IN[1] else []

# 로컬 Flask 대시보드 API 주소
API_BASE = "http://localhost:3000"

def send_to_dashboard(endpoint, data):
    """로컬 대시보드 API로 POST 요청 전송"""
    try:
        url = API_BASE + endpoint
        json_data = json.dumps(data).encode('utf-8')
        req = urllib_req.Request(url, data=json_data)
        req.add_header('Content-Type', 'application/json')
        response = urllib_req.urlopen(req)
        res_read = response.read()
        # bytes형태 디코딩 대응
        if not isinstance(res_read, str):
            res_read = res_read.decode('utf-8')
        return json.loads(res_read)
    except Exception as e:
        return {"error": str(e)}

def get_from_dashboard(endpoint):
    """로컬 대시보드 API로부터 GET 요청 수신"""
    try:
        url = API_BASE + endpoint
        response = urllib_req.urlopen(url)
        res_read = response.read()
        if not isinstance(res_read, str):
            res_read = res_read.decode('utf-8')
        return json.loads(res_read)
    except Exception as e:
        return {"error": str(e)}

# ─── 1. 현재 매스 매개변수 및 버티포트 좌표 읽기 ──────
result_msg = "Revit 연결 준비 완료"

# 파라미터 강제 검출기 (대소문자 및 한글/영어 완벽 지원)
def find_parameter(elem, names):
    for p in elem.Parameters:
        if p.Definition.Name in names:
            return p
    return None

if mass_element:
    try:
        # 매칭되는 치수 매개변수 검출
        height_param = find_parameter(mass_element, ["높이", "Height", "H"])
        width_param = find_parameter(mass_element, ["폭", "Width", "W"])
        depth_param = find_parameter(mass_element, ["깊이", "Depth", "D"])
        corner_radius_param = find_parameter(mass_element, ["모서리반경", "CornerRadius", "Radius", "곡률", "Corner Radius"])
        
        # 피트 ➔ 미터 변환 (1 ft = 0.3048 m)
        height = height_param.AsDouble() * 0.3048 if height_param else 0.0
        width = width_param.AsDouble() * 0.3048 if width_param else 0.0
        depth = depth_param.AsDouble() * 0.3048 if depth_param else 0.0
        corner_radius = corner_radius_param.AsDouble() * 0.3048 if corner_radius_param else 0.0
        
        # 1. 연결 확인 및 현재 매스 속성 전송
        params_data = {
            "params": {
                "height": round(height, 2),
                "width": round(width, 2),
                "depth": round(depth, 2),
                "corner_radius": round(corner_radius, 2)
            }
        }
        send_to_dashboard("/api/dynamo/connect", params_data)
        
        # 2. 버티포트 후보 좌표 전송
        candidates_data = {"candidates": []}
        for i, pt in enumerate(candidate_points):
            # Dynamo Point의 X, Y, Z 좌표를 미터 단위로 전송
            candidates_data["candidates"].append({
                "id": "V{}".format(i+1),
                "name": "후보지 {}".format(i+1),
                "x": pt.X,
                "y": pt.Y,
                "z": pt.Z
            })
        
        send_to_dashboard("/api/dynamo/candidates", candidates_data)
        result_msg = "✅ 대시보드로 버티포트 및 곡률 매스 속성 전송 완료!"
        
        # 3. 대시보드로부터 AI의 매스 제어 명령이 있는지 확인 (폴링)
        next_data = get_from_dashboard("/api/dynamo/next_params")
        if next_data.get("status") == "optimizing":
            new_params = next_data.get("params", {})
            
            # Revit 트랜잭션 시작 (모델 변경 승인)
            TransactionManager.Instance.EnsureInTransaction(doc)
            
            # 각각의 매개변수를 개별 안전망(try-except)으로 감싸 오류 파급 최소화
            if height_param and "height" in new_params:
                try:
                    if not height_param.IsReadOnly:
                        height_param.Set(new_params["height"] / 0.3048)
                    else:
                        send_to_dashboard("/api/dynamo/error", {"error": "높이 매개변수가 읽기 전용입니다."})
                except Exception as e:
                    send_to_dashboard("/api/dynamo/error", {"error": "높이 반영 실패: " + str(e)})
                    
            if width_param and "width" in new_params:
                try:
                    if not width_param.IsReadOnly:
                        width_param.Set(new_params["width"] / 0.3048)
                    else:
                        send_to_dashboard("/api/dynamo/error", {"error": "폭 매개변수가 읽기 전용입니다."})
                except Exception as e:
                    send_to_dashboard("/api/dynamo/error", {"error": "폭 반영 실패: " + str(e)})
                    
            if depth_param and "depth" in new_params:
                try:
                    if not depth_param.IsReadOnly:
                        depth_param.Set(new_params["depth"] / 0.3048)
                    else:
                        send_to_dashboard("/api/dynamo/error", {"error": "깊이 매개변수가 읽기 전용입니다."})
                except Exception as e:
                    send_to_dashboard("/api/dynamo/error", {"error": "깊이 반영 실패: " + str(e)})
                    
            if corner_radius_param and "corner_radius" in new_params:
                try:
                    if not corner_radius_param.IsReadOnly:
                        corner_radius_param.Set(new_params["corner_radius"] / 0.3048)
                    else:
                        send_to_dashboard("/api/dynamo/error", {"error": "모서리반경 매개변수가 읽기 전용입니다."})
                except Exception as e:
                    send_to_dashboard("/api/dynamo/error", {"error": "모서리반경 반영 실패: " + str(e)})
                
            TransactionManager.Instance.TransactionTaskDone()
            
            # ─── 대시보드에 변형 적용 완료 신호 쏘기 (Handshake) ───
            send_to_dashboard("/api/dynamo/applied", {"ok": True})
            
            result_msg = "🤖 AI 최적화 매개변수 적용 완료 (높이: {}m, 곡면 반경: {}m)".format(
                new_params.get("height", height),
                new_params.get("corner_radius", corner_radius)
            )
            
    except Exception as ex:
        result_msg = "⚠️ 오류 발생: " + str(ex)
        send_to_dashboard("/api/dynamo/error", {"error": "Dynamo 스크립트 실행 오류: " + str(ex)})

# Dynamo 출력 노드로 결과 전송
OUT = result_msg



