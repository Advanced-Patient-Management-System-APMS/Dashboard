from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 세션 암호화용 키

# 하드코딩 사용자 예제
users = {'user1': 'password1', 'user2': 'password2'}

@app.route('/')
def index():
    # 로그인 상태에 따라 인덱스 페이지에서 안내문 출력 가능
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        hospital_name = request.form['hospital_name']
        username = request.form['username']
        password = request.form['password']

        # 예시로 단순히 병원 이름이 empty 아니면 통과시키고 로그인 검사 진행
        if not hospital_name.strip():
            flash('병원 이름을 입력하세요.')
            return render_template('login.html')

        if username in users and users[username] == password:
            session['username'] = username
            session['hospital_name'] = hospital_name  # 세션에 병원 이름 저장
            flash(f'{hospital_name} 로그인 성공!')
            return redirect(url_for('index'))
        else:
            flash('로그인 실패: 사용자명 또는 비밀번호가 틀립니다.')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('로그아웃 되었습니다.')
    return redirect(url_for('login'))

@app.route('/api/floor_rooms/<int:floor_num>')
def api_floor_rooms(floor_num):
    left_rooms = [{'name': f"{floor_num}0{i}호"} for i in range(1, 5)]
    right_rooms = [{'name': f"{floor_num}0{i}호"} for i in range(5, 9)]
    return render_template('floor_rooms.html', left_rooms=left_rooms, right_rooms=right_rooms)

@app.route('/api/room_beds/<room_name>')
def api_room_beds(room_name):
    left_beds = [f"침대 {i}" for i in range(1, 5)]
    right_beds = [f"침대 {i}" for i in range(5, 9)]
    return render_template('room_beds.html', room_number=room_name, beds_left=left_beds, beds_right=right_beds)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
