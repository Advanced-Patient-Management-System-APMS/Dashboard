# app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
# from flask_bcrypt import Bcrypt <-- Bcrypt 삭제

app = Flask(__name__)

# --- 1. 기본 설정 ---
app.secret_key = 'your_secret_key'

# --- 2. 새로운 통합 DB(AjouHospital_DB) 연결 설정 ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Kwangyeon404@' # 본인의 실제 DB 비밀번호
app.config['MYSQL_DB'] = 'AjouHospital_DB'      # 새로운 통합 DB 이름
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# --- 3. 객체 초기화 ---
mysql = MySQL(app)
# bcrypt = Bcrypt(app) <-- Bcrypt 삭제

# --- 4. 라우트 함수 정의 ---

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', full_name=session.get('full_name'))
    # [오타 수정] ruedirect(rl_for('login')) -> redirect(url_for('login'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM login_staff WHERE username = %s", [request.form['username']])
        user = cur.fetchone()
        cur.close()

        # ▼▼▼ [수정] 암호화 비교 대신, 단순 문자열 비교로 변경 ▼▼▼
        if user and user['password'] == request.form['password']:
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            flash(f"{user['full_name']}님, 환영합니다!")
            return redirect(url_for('index'))
        else:
            flash('사용자명 또는 비밀번호가 틀립니다.')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('full_name', None)
    flash('로그아웃 되었습니다.')
    return redirect(url_for('login'))


# ▼▼▼ [새로 추가] 특정 병실의 비어있는 침대 목록을 JSON으로 반환하는 API ▼▼▼
@app.route('/api/available_beds_in_room/<int:room_id>')
def api_available_beds_in_room(room_id):
    try:
        cur = mysql.connection.cursor()
        # 특정 room_id에 속하면서, 아직 환자에게 배정되지 않은 침대만 조회
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
        return jsonify(available_beds) # 조회된 침대 목록을 JSON으로 반환
    except Exception as e:
        print(f"Error fetching available beds in room: {e}")
        return jsonify({'error': '침대 정보 조회 중 오류 발생'}), 500

# ▼▼▼ [수정] 기존 register_patient 함수 ▼▼▼
@app.route('/register_patient', methods=['GET', 'POST'])
def register_patient():
    # --- [핵심] 폼 제출(POST 요청) 시, 환자 정보를 DB에 저장하는 로직 ---
    if request.method == 'POST':
        patient_name = request.form['patient_name']
        age = request.form.get('age') # 값이 없을 수도 있으므로 .get() 사용
        gender = request.form['gender']
        bed_id = request.form['bed_id']

        # bed_id가 선택되었는지 확인
        if not bed_id:
            flash("침대가 선택되지 않았습니다.")
            # GET 요청과 동일한 로직으로 폼을 다시 보여줘야 함
            # (이 부분은 아래 GET 로직에서 처리되므로 여기서는 넘어감)
        else:
            try:
                cur = mysql.connection.cursor()
                # patients 테이블에 새로운 환자 정보 INSERT
                cur.execute(
                    "INSERT INTO patients (patient_name, age, gender, bed_id) VALUES (%s, %s, %s, %s)",
                    (patient_name, age, gender, bed_id)
                )
                mysql.connection.commit()
                cur.close()
                flash(f"'{patient_name}' 환자 등록이 완료되었습니다.")
                return redirect(url_for('index')) # 등록 후 메인 페이지로 이동
            except Exception as e:
                # bed_id 중복 등 DB 오류 발생 시
                flash("환자 등록 중 오류가 발생했습니다. 다시 시도해주세요.")
                print(f"Patient registration error: {e}") # 터미널에서 상세 오류 확인

    # --- GET 요청 시, 폼에 필요한 병실 목록을 전달하는 로직 ---
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

@app.route('/api/floor_rooms/<int:floor_num>')
def api_floor_rooms(floor_num):
    try:
        cur = mysql.connection.cursor()
        
        # ▼▼▼ [핵심 수정] JOIN을 사용하여 해당 층의 모든 방과 환자 정보를 한번에 가져옵니다. ▼▼▼
        query = """
            SELECT 
                r.room_number,
                p.patient_name, p.age, p.gender, b.bed_number
            FROM rooms r
            LEFT JOIN beds b ON r.room_id = b.room_id
            LEFT JOIN patients p ON b.bed_id = p.bed_id
            WHERE r.floor = %s
            ORDER BY r.room_number, b.bed_number
        """
        cur.execute(query, [floor_num])
        results = cur.fetchall()
        cur.close()

        # 조회된 데이터를 방별로 그룹화합니다.
        rooms_dict = {}
        # 8개 방을 먼저 빈 상태로 초기화합니다.
        for i in range(1, 9):
            room_name_with_unit = f"{floor_num}0{i}호"
            rooms_dict[room_name_with_unit] = {'name': room_name_with_unit, 'patients': []}

        # DB에서 가져온 환자 정보를 해당 방에 추가합니다.
        for row in results:
            room_name_with_unit = f"{row['room_number']}호"
            if row['patient_name']:
                rooms_dict[room_name_with_unit]['patients'].append(row)
        
        # 템플릿에 전달할 최종 데이터 생성
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
        
        query = """
            SELECT 
                p.patient_name, p.age, p.gender, b.bed_number
            FROM patients p
            JOIN beds b ON p.bed_id = b.bed_id
            JOIN rooms r ON b.room_id = r.room_id
            WHERE r.room_number = %s
            ORDER BY b.bed_number ASC
        """
        cur.execute(query, [room_number_for_query])
        patients = cur.fetchall()
        cur.close()
        return jsonify(patients)
    except Exception as e:
        print(f"Error fetching patients in room: {e}")
        return jsonify({'error': '환자 정보 조회 중 오류 발생'}), 500
    
# --- 서버 실행 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

