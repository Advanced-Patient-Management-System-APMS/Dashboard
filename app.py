from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from flask_bcrypt import Bcrypt
import os # ⭐️ 1. import os
from werkzeug.utils import secure_filename # ⭐️ 2. import secure_filename
from datetime import datetime

app = Flask(__name__)

# --- 1. 기본 설정 ---
app.secret_key = 'your_secret_key'

# [업로드 설정]
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov'}

# --- 2. MySQL 연결 설정 ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'dashboard_user'
app.config['MYSQL_PASSWORD'] = 'Kwangyeon404@'
app.config['MYSQL_DB'] = 'AjouHospital_DB'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER # ⭐️ 3. 업로드 폴더 설정

# ⭐️ 4. [중요] gunicorn을 위해 'uploads' 폴더를 앱 시작 시 생성
# (if __name__ == '__main__' 안에 있으면 gunicorn이 실행 안 함)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- 3. bcrypt 초기화 ---
bcrypt = Bcrypt(app)

# --- 4. DB 연결 헬퍼 함수 ---
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB'],
            connect_timeout=10
        )
        return conn, conn.cursor(dictionary=True)
    except mysql.connector.Error as err:
        print(f"DB Connection Error: {err}")
        return None, None

def close_db_connection(conn, cur):
    if cur: cur.close()
    if conn: conn.close()

# ⭐️ 5. [중요] allowed_file 함수 (올바른 들여쓰기)
def allowed_file(filename):
    """파일 확장자 확인 함수"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 5. 라우트 시작 ---
# (기존의 / , /login, /logout 등등 ... 코드는 여기에 그대로 둡니다)
@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', full_name=session.get('full_name'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn, cur = get_db_connection()
        if not conn:
            flash("데이터베이스 연결 실패")
            return render_template('login.html')

        try:
            cur.execute("SELECT * FROM login_staff WHERE username = %s", (username,))
            user = cur.fetchone()

            if user and user['password'] == password:  # 평문 비교
                session['username'] = user['username']
                session['full_name'] = user.get('full_name', user['username'])
                flash(f"{session['full_name']}님, 환영합니다!")
                return redirect(url_for('index'))
            else:
                flash('사용자명 또는 비밀번호가 일치하지 않습니다.')
        except Exception as e:
            print(f"Login Error: {e}")
            flash("로그인 중 오류 발생")
        finally:
            close_db_connection(conn, cur)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('로그아웃 되었습니다.')
    return redirect(url_for('login'))

@app.route('/register_patient', methods=['GET', 'POST'])
def register_patient():
    conn, cur = get_db_connection()
    if not conn:
        flash("DB 연결 실패")
        return render_template('register_patient.html', all_rooms=[])

    if request.method == 'POST':
        patient_name = request.form['patient_name']
        disease = request.form.get('disease')
        age = request.form.get('age')
        gender = request.form['gender']
        bed_id = request.form['bed_id']

        if not all([patient_name, age, gender, bed_id]):
            flash("모든 항목을 입력해주세요.", 'error')
            close_db_connection(conn, cur)
            return redirect(url_for('register_patient'))

        try:
            cur.execute("SELECT patient_id FROM patients WHERE bed_id = %s", (bed_id,))
            if cur.fetchone():
                flash("이미 사용 중인 침대입니다.")
            else:
                cur.execute(
                    "INSERT INTO patients (patient_name, disease, age, gender, bed_id) VALUES (%s, %s, %s, %s, %s)",
                    (patient_name, disease, age, gender, bed_id)
                )
                conn.commit()
                flash(f"'{patient_name}' 환자 등록 완료")
                close_db_connection(conn, cur)
                return redirect(url_for('index'))
        except Exception as e:
            conn.rollback()
            print(f"Patient registration error: {e}")
            flash("등록 중 오류 발생")
        finally:
            close_db_connection(conn, cur)
        return redirect(url_for('register_patient'))

    try:
        cur.execute("SELECT room_id, room_number, floor FROM rooms ORDER BY floor, room_number")
        all_rooms = cur.fetchall()
    except Exception as e:
        print(e)
        all_rooms = []
    finally:
        close_db_connection(conn, cur)
    return render_template('register_patient.html', all_rooms=all_rooms)

@app.route('/api/available_beds_in_room/<int:room_id>')
def api_available_beds_in_room(room_id):
    conn, cur = get_db_connection()
    if not conn:
        return jsonify({'error': 'DB 연결 실패'}), 500
    try:
        cur.execute("""
            SELECT b.bed_id, b.bed_number
            FROM beds b
            LEFT JOIN patients p ON b.bed_id = p.bed_id
            WHERE b.room_id = %s AND p.patient_id IS NULL
            ORDER BY b.bed_number
        """, [room_id])
        data = cur.fetchall()
        return jsonify(data)
    except Exception as e:
        print(e)
        return jsonify({'error': '조회 오류'}), 500
    finally:
        close_db_connection(conn, cur)

@app.route('/api/floor_rooms/<int:floor_num>')
def api_floor_rooms(floor_num):
    conn, cur = get_db_connection()
    if not conn:
        return "DB 연결 실패", 500
    try:
        cur.execute("""
            SELECT 
                r.room_number, 
                p.patient_id, 
                p.patient_name, 
                p.age, 
                p.gender, 
                b.bed_number,
                
                -- (추가) events 테이블에서 최신 이벤트를 가져옵니다.
                (SELECT e.event_type 
                 FROM events e 
                 WHERE e.patient_id = p.patient_id
                 ORDER BY e.event_timestamp DESC 
                 LIMIT 1
                ) AS latest_event_type

            FROM rooms r
            LEFT JOIN beds b ON r.room_id = b.room_id
            LEFT JOIN patients p ON b.bed_id = p.bed_id 
            WHERE r.floor = %s
            ORDER BY r.room_number, b.bed_number
        """, [floor_num])
        results = cur.fetchall()
        rooms_dict = {}
        for i in range(1, 9):
            rn = f"{floor_num}0{i}"
            rooms_dict[rn] = {'name': f"{rn}호", 'patients': []}
        for r in results:
            rn = str(r['room_number'])

            if rn in rooms_dict:
                rooms_dict[rn]['patients'].append(r)
        data = list(rooms_dict.values())
        return render_template('floor_rooms.html', top_row_rooms=data[0:4], bottom_row_rooms=data[4:8])
    except Exception as e:
        print(e)
        return "조회 오류", 500
    finally:
        close_db_connection(conn, cur)

@app.route('/api/patients_in_room/<room_name>')
def api_patients_in_room(room_name):
    rn = room_name.replace('호','')
    conn, cur = get_db_connection()
    if not conn:
        return jsonify([]), 500
    try:
        cur.execute("""
            SELECT b.bed_id, b.bed_number,
                   p.patient_id,
                   COALESCE(p.patient_name,'') AS patient_name,
                   COALESCE(p.age,0)          AS age,
                   COALESCE(p.gender,'')       AS gender,
                   COALESCE(p.disease,'')      AS disease
            FROM rooms r
            JOIN beds b ON r.room_id = b.room_id
            LEFT JOIN patients p ON p.bed_id = b.bed_id
            WHERE r.room_number = %s
            ORDER BY b.bed_number
        """, (rn,))
        return jsonify(cur.fetchall())
    finally:
        close_db_connection(conn, cur)

# ---------------------------------------------------
# ⭐️ 6. [추가] Pi 4로부터 영상 파일을 받는 엔드포인트
# ---------------------------------------------------
@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        print("❌ [Upload] 'video' part가 form에 없습니다.")
        return jsonify({'error': 'No video file part'}), 400

    file = request.files['video']

    if file.filename == '':
        print("❌ [Upload] 파일이 선택되지 않았습니다.")
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(save_path)
            print(f"✅ [Upload] 영상 저장 성공: {save_path}")
            return jsonify({'status': 'success', 'filename': filename}), 200
        
        except Exception as e:
            print(f"❌ [Upload] 파일 저장 중 오류: {e}")
            return jsonify({'error': 'File save error'}), 500
    else:
        print(f"❌ [Upload] 허용되지 않는 파일 형식: {file.filename}")
        return jsonify({'error': 'Invalid file type'}), 400

# ---------------------------------------------------
# ⭐️ 7. [최종 수정] 환자 상세 정보 (HR/SPO2) API
# (DDL에 맞춰 'heartrate' 및 'timestamp' 컬럼 사용)
# ---------------------------------------------------
@app.route('/api/patient_detail/<int:patient_id>')
def api_patient_detail(patient_id):
    """
    특정 환자의 기본 정보와 최근 스마트링 로그(HR, SPO2)를 반환합니다.
    (DDL 스키마에 맞춰 'timestamp' 컬럼을 사용하도록 수정됨)
    """
    conn, cur = get_db_connection()
    if not conn:
        return jsonify({'error': 'DB 연결 실패'}), 500
    
    try:
        # 1. 환자 기본 정보 조회
        cur.execute("""
            SELECT patient_name, disease, age, gender 
            FROM patients 
            WHERE patient_id = %s
        """, (patient_id,))
        patient_info = cur.fetchone()

        if not patient_info:
            close_db_connection(conn, cur)
            return jsonify({'error': '해당 환자 정보를 찾을 수 없습니다.'}), 404

        # 2. 스마트링 최근 로그 조회 (최근 20개)
        # ▼▼▼ [수정] DDL에 맞게 'log_timestamp' -> 'timestamp'로 변경 ▼▼▼
        cur.execute("""
            SELECT heartrate, spo2, timestamp
            FROM smartring_logs
            WHERE patient_id = %s
            ORDER BY timestamp DESC
            LIMIT 20
        """, (patient_id,))
        smartring_logs = cur.fetchall()
        
        # 3. 날짜/시간 객체(datetime)를 JSON이 읽을 수 있는 문자열로 변환
        logs_list = []
        for log in smartring_logs:
            logs_list.append({
                'heart_rate': log['heartrate'], # (JS를 위해 'heart_rate'로 별칭 부여)
                'spo2': log['spo2'],
                # ▼▼▼ [수정] DDL에 맞게 log['log_timestamp'] -> log['timestamp']로 변경 ▼▼▼
                # (JS를 위해 'log_timestamp'로 별칭 부여)
                'log_timestamp': log['timestamp'].isoformat() if log['timestamp'] else None
            })

        return jsonify({
            'info': patient_info,
            'logs': logs_list  # 변환된 리스트 반환
        })

    except Exception as e:
        print(f"❌ Error fetching patient detail for ID {patient_id}: {e}")
        return jsonify({'error': '환자 상세 정보 조회 중 오류 발생'}), 500
    finally:
        close_db_connection(conn, cur)

# ---------------------------------------------------
# ⭐️ 8. [추가] 긴급 상황 확인 API (이게 404의 원인!)
# ---------------------------------------------------
@app.route('/api/check_emergencies')
def api_check_emergencies():
    # (이전 답변에 드렸던 코드 내용...)
    # (긴 코드 생략)
    conn, cur = get_db_connection()
    if not conn:
        return jsonify({'error': 'DB 연결 실패'}), 500
    try:
        query = """
            WITH LatestEvents AS (
                SELECT patient_id, event_type, event_value,
                       ROW_NUMBER() OVER(PARTITION BY patient_id ORDER BY event_timestamp DESC) as rn
                FROM events
            )
            SELECT p.patient_name, r.room_number, le.event_value
            FROM LatestEvents le
            JOIN patients p ON le.patient_id = p.patient_id
            JOIN beds b ON p.bed_id = b.bed_id
            JOIN rooms r ON b.room_id = r.room_id
            WHERE le.rn = 1 AND le.event_type = 'emergency';
        """
        cur.execute(query)
        emergencies = cur.fetchall()
        return jsonify({'emergencies': emergencies})
    except Exception as e:
        print(f"❌ Error checking emergencies: {e}")
        return jsonify({'error': '긴급 호출 확인 중 오류 발생'}), 500
    finally:
        close_db_connection(conn, cur)


# ---------------------------------------------------
# ⭐️ 9. [추가] '낙상 감지 이력' API 
# (fall_detection_log.html이 호출하는 API)
# ---------------------------------------------------
@app.route('/api/fall_events')
def api_fall_events():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    # 1. JavaScript에서 보낸 날짜 파라미터(start, end) 받기
    start_date_str = request.args.get('start')
    end_date_str = request.args.get('end')

    if not start_date_str or not end_date_str:
        return jsonify({"error": "날짜 범위를 입력해주세요"}), 400

    # 2. 날짜 문자열을 datetime 객체로 변환
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        return jsonify({"error": "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)"}), 400

    conn, cur = get_db_connection()
    if not conn:
        return jsonify({'error': 'DB 연결 실패'}), 500
    
    try:
        # 3. DB에서 '낙상 감지' 이력 조회 (event_status 컬럼 없이 수정됨)
        query = """
            SELECT 
                e.event_timestamp,
                r.room_number,
                p.patient_name
            FROM events e
            JOIN patients p ON e.patient_id = p.patient_id
            JOIN beds b ON p.bed_id = b.bed_id
            JOIN rooms r ON b.room_id = r.room_id
            WHERE 
                e.event_value = '낙상 감지' 
                AND e.event_timestamp BETWEEN %s AND %s
            ORDER BY 
                e.event_timestamp DESC
        """
        cur.execute(query, (start_date, end_date))
        raw_events = cur.fetchall()
        
        # 4. 결과를 JSON 형식에 맞게 가공
        events_list = []
        for event in raw_events:
            events_list.append({
                'time': event['event_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'room': f"{event['room_number']}호",
                'patient': event['patient_name'],
                # DB에 status 컬럼이 없으므로, 'pending'으로 고정
                'status': 'pending' 
            })
        
        return jsonify(events_list)

    except Exception as e:
        print(f"❌ Error fetching fall events: {e}")
        return jsonify({'error': '낙상 이력 조회 중 오류 발생'}), 500
    finally:
        close_db_connection(conn, cur)




@app.route('/fall_log')
def fall_log_page():
    if 'username' not in session:
        flash("로그인이 필요합니다.")
        return redirect(url_for('login'))

    return render_template('fall_detection_log.html')

# --- 서버 실행 ---
if __name__ == '__main__':
    print("=" * 60)
    print("통합 대시보드 애플리케이션을 시작합니다. (Debug Mode)")
    print(f"업로드 폴더: {os.path.abspath(app.config['UPLOAD_FOLDER'])}")
    print(f"서버 주소: http://<라즈베리파이_IP>:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)