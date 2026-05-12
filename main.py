from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PIXEL_TO_METER = 0.05
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@app.post("/analyze-floorplan")
async def analyze_floorplan(file: UploadFile = File(...)):
    contents = await file.read()

    # 파일 크기 제한
    if len(contents) > MAX_FILE_SIZE:
        return JSONResponse(status_code=400, content={"success": False, "message": "파일 크기가 10MB를 초과합니다."})

    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 이미지 디코딩 실패 처리
    if img is None:
        return JSONResponse(status_code=400, content={"success": False, "message": "이미지를 읽을 수 없습니다. 유효한 이미지 파일인지 확인하세요."})

    img_height, img_width = img.shape[:2]
    if img_height < 50 or img_width < 50:
        return JSONResponse(status_code=400, content={"success": False, "message": "이미지가 너무 작습니다. 최소 50x50 픽셀 이상이어야 합니다."})

    center_x, center_y = img_width / 2, img_height / 2

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=50, maxLineGap=15)

    horizontals = []
    verticals = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            
            is_horizontal = abs(angle) < 5 or abs(angle) > 175
            is_vertical = abs(abs(angle) - 90) < 5

            if is_horizontal:
                if x1 > x2: x1, x2 = x2, x1
                horizontals.append({'x1': x1, 'x2': x2, 'y': (y1+y2)/2})
            elif is_vertical:
                if y1 > y2: y1, y2 = y2, y1
                verticals.append({'y1': y1, 'y2': y2, 'x': (x1+x2)/2})

    # 병합(Merge) 로직 (이중 선 방지)
    MERGE_TOLERANCE = 25 

    horizontals.sort(key=lambda l: l['y'])
    merged_h = []
    for line in horizontals:
        merged = False
        for m in merged_h:
            if abs(line['y'] - m['y']) < MERGE_TOLERANCE:
                if max(line['x1'], m['x1']) <= min(line['x2'], m['x2']) + 15:
                    m['x1'] = min(m['x1'], line['x1'])
                    m['x2'] = max(m['x2'], line['x2'])
                    m['y'] = (m['y'] + line['y']) / 2 
                    merged = True
                    break
        if not merged:
            merged_h.append(line)

    verticals.sort(key=lambda l: l['x'])
    merged_v = []
    for line in verticals:
        merged = False
        for m in merged_v:
            if abs(line['x'] - m['x']) < MERGE_TOLERANCE:
                if max(line['y1'], m['y1']) <= min(line['y2'], m['y2']) + 15:
                    m['y1'] = min(m['y1'], line['y1'])
                    m['y2'] = max(m['y2'], line['y2'])
                    m['x'] = (m['x'] + line['x']) / 2
                    merged = True
                    break
        if not merged:
            merged_v.append(line)

    walls = []
    wall_id = 1
    
    for h in merged_h:
        walls.append({
            "id": f"w{wall_id}",
            "x1": round((h['x1'] - center_x) * PIXEL_TO_METER, 2),
            "z1": round((h['y'] - center_y) * PIXEL_TO_METER, 2),
            "x2": round((h['x2'] - center_x) * PIXEL_TO_METER, 2),
            "z2": round((h['y'] - center_y) * PIXEL_TO_METER, 2),
            "thickness": 0.15
        })
        wall_id += 1

    for v in merged_v:
        walls.append({
            "id": f"w{wall_id}",
            "x1": round((v['x'] - center_x) * PIXEL_TO_METER, 2),
            "z1": round((v['y1'] - center_y) * PIXEL_TO_METER, 2),
            "x2": round((v['x'] - center_x) * PIXEL_TO_METER, 2),
            "z2": round((v['y2'] - center_y) * PIXEL_TO_METER, 2),
            "thickness": 0.15
        })
        wall_id += 1

    return {
        "success": True,
        "data": {
            "floor": {
                "width": round(img_width * PIXEL_TO_METER, 2),
                "depth": round(img_height * PIXEL_TO_METER, 2),
                "tileType": "wood"
            },
            "walls": walls
        }
    }