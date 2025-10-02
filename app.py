import mysql.connector as login_db
from mysql.connector import Error
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
# from flask_bcrypt import Bcrypt # <-- Bcrypt 삭제

app = Flask(__name__)
app.secret_key = 'your_secret_key'
# bcrypt = Bcrypt(app) # <-- Bcrypt 삭제

# --- 기본 DB (patient_info) 연결 설정 ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Kwangyeon404@'
app.config['MYSQL_DB'] = 'patient_info'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app) # patient_info DB를 위한 기본 연결 객체

# --- 라우트 함수 정의 ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        hospital_name = request.form['hospital_name']
        username = request.form['username']
        password = request.form['password']
        
        connection = None
        try:
            # 로그인 전용 DB(login_data)에 직접 연결
            connection = login_db.connect(
                host='localhost',
                user='root',
                password='Kwangyeon404@',
                database='login_data' # 로그인 DB 이름
            )
            
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM login_staff WHERE username = %s AND hospital = %s"
            cursor.execute(query, (username, hospital_name))
            user = cursor.fetchone()

            # ▼▼▼ [핵심 수정] 암호화 비교 대신, 단순 문자열 비교로 변경 ▼▼▼
            if user and user['password'] == password:
                session['username'] = user['username']
                session['full_name'] = user['full_name'] 
                session['hospital_name'] = user['hospital']
                flash(f"{user['full_name']}님, 환영합니다!")
                return redirect(url_for('index'))
            else:
                flash('병원, 사용자명 또는 비밀번호가 일치하지 않습니다.')

        except Error as e:
            print(f"로그인 DB 연결 오류: {e}")
            flash('데이터베이스 연결에 실패했습니다.')
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('로그아웃 되었습니다.')
    return redirect(url_for('login'))

@app.route('/')
def index():
    # ▼▼▼ [수정] index.html 템플릿으로 full_name 전달 ▼▼▼
    if 'username' in session:
        # 세션에 저장된 full_name을 템플릿으로 넘겨줍니다.
        return render_template('index.html', full_name=session.get('full_name'))
    return redirect(url_for('login'))

@app.route('/api/floor_rooms/<int:floor_num>')
def api_floor_rooms(floor_num):
    try:
        cur = mysql.connection.cursor()
        
        rooms_data = []
        # 해당 층의 모든 방(1~8호실)을 순회하며 환자 정보 조회
        for i in range(1, 9):
            room_name = f"{floor_num}0{i}" # 예: 101, 102, ...
            
            # SQL 쿼리 실행: 각 방에 배정된 환자 이름을 조회
            query = "SELECT patient_name FROM patient_info WHERE room_name = %s LIMIT 1"
            cur.execute(query, [room_name])
            patient = cur.fetchone()
            
            # 환자가 있으면 환자 이름을, 없으면 "환자 없음"을 저장
            patient_info = patient['patient_name'] if patient else "환자 없음"
            
            rooms_data.append({'name': room_name, 'patient': patient_info})
            
        cur.close()

        # 데이터를 템플릿에 전달하기 위해 윗줄/아랫줄로 나눔
        top_row_rooms = rooms_data[0:4]
        bottom_row_rooms = rooms_data[4:8]

        return render_template(
            'floor_rooms.html', 
            top_row_rooms=top_row_rooms, 
            bottom_row_rooms=bottom_row_rooms
        )

    except Exception as e:
        print(f"Error fetching floor data: {e}")
        return "데이터 조회 중 오류 발생", 500

@app.route('/api/room_beds/<room_name>')
def api_room_beds(room_name):
    try:
        cur = mysql.connection.cursor()

        # SQL 쿼리: 특정 호실의 환자 정보를 침대 번호(bed_number) 순으로 조회
        query = "SELECT patient_name, `bed_number` as bed_no FROM patient_info WHERE room_name = %s ORDER BY `bed_number`"
        cur.execute(query, [room_name])
        patients_in_room = cur.fetchall()
        cur.close()

        # 전체 침대(1~8번) 상태를 '빈 침대'로 초기화
        all_beds = {i: None for i in range(1, 9)} 

        # DB에서 가져온 환자 정보로 침대 상태 업데이트
        for patient in patients_in_room:
            all_beds[patient['bed_no']] = patient['patient_name']

        # 템플릿에 전달할 최종 데이터 생성
        left_beds = [{'num': i, 'patient': all_beds[i]} for i in range(1, 5)]
        right_beds = [{'num': i, 'patient': all_beds[i]} for i in range(5, 9)]

        return render_template('room_beds.html', room_number=room_name, beds_left=left_beds, beds_right=right_beds)
    
    except Exception as e:
        print(f"Error fetching bed data: {e}")
        return "침대 정보 조회 중 오류 발생", 500
    
# ▼▼▼ [새로 추가] 특정 방의 '모든' 환자 목록을 JSON으로 반환하는 API ▼▼▼
@app.route('/api/patients_in_room/<room_name>')
def api_patients_in_room(room_name):
    try:
        cur = mysql.connection.cursor()
        # 스크린샷에 있던 컬럼 이름들을 사용합니다. (테이블 이름은 실제 이름으로 변경)
        # bed number 순으로 정렬합니다.
        query = "SELECT `patient_name`, age, gender, `bed_number` FROM patient_info WHERE `room_name` = %s ORDER BY `bed_number` ASC"
        cur.execute(query, [room_name])
        patients = cur.fetchall()
        cur.close()
        # 조회된 환자 목록을 JSON 형태로 반환합니다.
        return jsonify(patients)
    except Exception as e:
        print(f"Error fetching patients in room: {e}")
        return jsonify({'error': '환자 정보 조회 중 오류 발생'}), 500
    

# --- 서버 실행 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)