# app.py

from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/floor_rooms/<int:floor_num>')
def api_floor_rooms(floor_num):
    # 'name' 키를 가진 딕셔너리 리스트를 반환합니다.
    left_rooms = [{'name': f"{floor_num}0{i}호"} for i in range(1, 5)]
    right_rooms = [{'name': f"{floor_num}0{i}호"} for i in range(5, 9)]
    return render_template('floor_rooms.html', left_rooms=left_rooms, right_rooms=right_rooms)

# ▼▼▼ [수정] 방 상세 정보를 위한 API (주소 확인!) ▼▼▼
@app.route('/api/room_beds/<room_name>')
def api_room_beds(room_name):
    # 예시 데이터로 8개의 침대를 생성합니다.
    left_beds = [f"침대 {i}" for i in range(1, 5)]
    right_beds = [f"침대 {i}" for i in range(5, 9)]
    return render_template('room_beds.html', room_number=room_name, beds_left=left_beds, beds_right=right_beds)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)