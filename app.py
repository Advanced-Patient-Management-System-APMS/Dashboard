from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from flask_bcrypt import Bcrypt
import os # ⭐️ 1. import os
from werkzeug.utils import secure_filename # ⭐️ 2. import secure_filename

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
                b.bed_number,
                COALESCE(p.patient_name, '') AS patient_name,
                COALESCE(p.age, 0)          AS age,
                COALESCE(p.gender, '')       AS gender
            FROM rooms r
            LEFT JOIN beds b ON r.room_id = b.room_id
            LEFT JOIN patients p ON p.bed_id = b.bed_id
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

# --- 서버 실행 ---
if __name__ == '__main__':
    print("=" * 60)
    print("통합 대시보드 애플리케이션을 시작합니다. (Debug Mode)")
    print(f"업로드 폴더: {os.path.abspath(app.config['UPLOAD_FOLDER'])}")
    print(f"서버 주소: http://<라즈베리파이_IP>:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
