from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def select_floor():
    floors = ["1층", "2층", "3층"]
    return render_template('select_floor.html', floors=floors)

@app.route('/floor/<int:floor_num>')
def floor_dashboard(floor_num):
    floor_name = f"{floor_num}층"
    # 예시: 101~104, 105~108
    left_rooms = [f"{floor_num}0{j}호" for j in range(1, 5)]
    right_rooms = [f"{floor_num}0{j}호" for j in range(5, 9)]
    return render_template('floor_dashboard.html',
                           floor_name=floor_name,
                           left_rooms=left_rooms,
                           right_rooms=right_rooms)


@app.route('/room/<room_number>')
def room_detail(room_number):
    # 예시: 8개 침대 좌우 배치
    beds = [f"{i}번 침대" for i in range(1, 9)]
    beds_left = beds[:4]
    beds_right = beds[4:]
    return render_template('room_detail.html',
                           room_number=room_number,
                           beds_left=beds_left,
                           beds_right=beds_right)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

