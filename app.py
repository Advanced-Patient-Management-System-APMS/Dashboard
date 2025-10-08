# app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt

app = Flask(__name__)

# --- 1. 기본 설정 ---
app.secret_key = 'your_secret_key'

# --- 2. MySQL 연결 설정 (하나의 DB로 통일) ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Kwangyeon404@' # 본인의 실제 DB 비밀번호
app.config['MYSQL_DB'] = 'AjouHospital_DB'      # 사용할 메인 데이터베이스
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# --- 3. 객체 초기화 ---
mysql = MySQL(app)
bcrypt = Bcrypt(app) # 로그인 보안을 위해 사용

# --- 4. 라우트 함수 정의 ---

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', full_name=session.get('full_name'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'] # 사용자가 입력한 평문 비밀번호

        cur = mysql.connection.cursor()
        query = "SELECT * FROM login_staff WHERE username = %s"
        cur.execute(query, (username,)) 
        user = cur.fetchone()
        cur.close()

        # ⭐️ bcrypt.check_password_hash 대신 평문 비교를 사용
        if user and user['password'] == password: # DB에서 가져온 평문과 입력된 평문 비교
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            flash(f"{user['full_name']}님, 환영합니다!")
            return redirect(url_for('index'))
        else:
            flash('병원, 사용자명 또는 비밀번호가 일치하지 않습니다.')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('full_name', None)
    flash('로그아웃 되었습니다.')
    return redirect(url_for('login'))


# ▼▼▼ [핵심] 빠져있던 '환자 등록' 기능 전체를 다시 추가합니다. ▼▼▼
@app.route('/register_patient', methods=['GET', 'POST'])
def register_patient():
    if request.method == 'POST':
        # 폼에서 데이터 가져오기
        patient_name = request.form['patient_name']
        disease = request.form.get('disease') # [추가] disease 값 가져오기
        age = request.form.get('age')
        gender = request.form['gender']
        bed_id = request.form['bed_id']

        if not bed_id:
            flash("침대가 선택되지 않았습니다.")
        else:
            try:
                cur = mysql.connection.cursor()
                # ▼▼▼ [수정] INSERT 쿼리에 disease 추가 ▼▼▼
                cur.execute(
                    "INSERT INTO patients (patient_name, disease, age, gender, bed_id) VALUES (%s, %s, %s, %s, %s)",
                    (patient_name, disease, age, gender, bed_id)
                )
                mysql.connection.commit()
                cur.close()
                flash(f"'{patient_name}' 환자 등록이 완료되었습니다.")
                return redirect(url_for('index'))
            except Exception as e:
                flash("환자 등록 중 오류가 발생했습니다.")
                print(f"Patient registration error: {e}")

    all_rooms = []
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT room_id, room_number, floor FROM rooms ORDER BY floor, room_number")
        all_rooms = cur.fetchall()
        cur.close()
    except Exception as e:
        print(f"Error fetching all rooms: {e}")
        flash("병실 목록을 불러오는 중 오류가 발생했습니다.")

    return render_template('register_patient.html', all_rooms=all_rooms)

@app.route('/api/available_beds_in_room/<int:room_id>')
def api_available_beds_in_room(room_id):
    try:
        cur = mysql.connection.cursor()
        query = """
            SELECT b.bed_id, b.bed_number
            FROM beds b
            LEFT JOIN patients p ON b.bed_id = p.bed_id
            WHERE b.room_id = %s AND p.patient_id IS NULL
            ORDER BY b.bed_number;
        """
        cur.execute(query, [room_id])
        available_beds = cur.fetchall()
        cur.close()
        return jsonify(available_beds)
    except Exception as e:
        print(f"Error fetching available beds in room: {e}")
        return jsonify({'error': '침대 정보 조회 중 오류 발생'}), 500


@app.route('/api/floor_rooms/<int:floor_num>')
def api_floor_rooms(floor_num):
    try:
        cur = mysql.connection.cursor()
        
        # ▼▼▼ [핵심 수정] 빠져있던 latest_event_type 서브쿼리를 다시 추가합니다. ▼▼▼
        query = """
            SELECT 
                r.room_number,
                p.patient_id, p.patient_name, p.age, p.gender,
                b.bed_number,
                (SELECT e.event_type 
                 FROM events e 
                 WHERE e.patient_id = p.patient_id 
                 ORDER BY e.event_timestamp DESC 
                 LIMIT 1) AS latest_event_type
            FROM rooms r
            LEFT JOIN beds b ON r.room_id = b.room_id
            LEFT JOIN patients p ON b.bed_id = p.bed_id
            WHERE r.floor = %s
            ORDER BY r.room_number, b.bed_number
        """
        cur.execute(query, [floor_num])
        results = cur.fetchall()
        cur.close()

        # --- (이하 데이터 그룹화 로직은 이전과 동일하게 유지) ---
        rooms_dict = {}
        # 8개 방을 먼저 빈 상태로 초기화
        for i in range(1, 9):
            room_name_with_unit = f"{floor_num}0{i}호"
            rooms_dict[room_name_with_unit] = {'name': room_name_with_unit, 'patients': []}

        for row in results:
            room_name_with_unit = f"{row['room_number']}호"
            if row['patient_name']:
                rooms_dict[room_name_with_unit]['patients'].append(row)
        
        rooms_data = list(rooms_dict.values())
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


@app.route('/api/patients_in_room/<room_name>')
def api_patients_in_room(room_name):
    try:
        cur = mysql.connection.cursor()
        room_number_for_query = room_name.strip('호')
        
        # ▼▼▼ [핵심 수정] LEFT JOIN을 사용하여 환자가 없는 침대 정보까지 모두 가져옵니다. ▼▼▼
        query = """
            SELECT 
                b.bed_number,
                p.patient_name, p.age, p.gender, p.disease
            FROM beds b
            JOIN rooms r ON b.room_id = r.room_id
            LEFT JOIN patients p ON b.bed_id = p.bed_id
            WHERE r.room_number = %s 
            ORDER BY b.bed_number ASC
        """
        cur.execute(query, [room_number_for_query])
        beds_in_room = cur.fetchall() # 이제 '환자'가 아닌 '침대' 목록을 가져옵니다.
        cur.close()
        return jsonify(beds_in_room)
    except Exception as e:
        print(f"Error fetching patients in room: {e}")
        return jsonify({'error': '환자 정보 조회 중 오류 발생'}), 500
    
# --- 서버 실행 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

