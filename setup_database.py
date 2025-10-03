import mysql.connector
from mysql.connector import Error

# --- 1. DB 연결 정보 (app.py와 동일하게 설정) ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Kwangyeon404@', # 본인의 DB 비밀번호
    'database': 'AjouHospital_DB'
}

# --- 2. 생성할 데이터 설정 ---
FLOORS = [1, 2, 3]  # 생성할 층
ROOMS_PER_FLOOR = 8 # 층별 병실 수 (1호 ~ 8호)
BEDS_PER_ROOM = 8   # 병실별 침대 수 (1번 ~ 8번)

def setup_database():
    """데이터베이스에 병실과 침대 데이터를 자동으로 추가합니다."""
    try:
        # DB 연결
        db_connection = mysql.connector.connect(**DB_CONFIG)
        cursor = db_connection.cursor()
        print("✅ 데이터베이스에 성공적으로 연결되었습니다.")

        # --- 3. 데이터 삽입 ---
        for floor in FLOORS:
            for room_num in range(1, ROOMS_PER_FLOOR + 1):
                room_number_str = f"{floor}0{room_num}"
                
                # A. 병실(room) 추가
                insert_room_query = "INSERT INTO rooms (room_number, floor) VALUES (%s, %s)"
                cursor.execute(insert_room_query, (room_number_str, floor))
                
                room_id = cursor.lastrowid
                print(f"-> {room_number_str}호 병실 생성 (ID: {room_id})")

                # B. 해당 병실에 침대(bed) 추가
                bed_data = []
                for bed_num in range(1, BEDS_PER_ROOM + 1):
                    bed_data.append((bed_num, room_id))
                
                insert_bed_query = "INSERT INTO beds (bed_number, room_id) VALUES (%s, %s)"
                cursor.executemany(insert_bed_query, bed_data)
                print(f"   - {BEDS_PER_ROOM}개의 침대 추가 완료.")

        db_connection.commit()
        print("\n🎉 모든 데이터가 성공적으로 생성되었습니다!")

    except Error as e:
        print(f"❌ 데이터 생성 중 오류 발생: {e}")
    finally:
        if 'db_connection' in locals() and db_connection.is_connected():
            cursor.close()
            db_connection.close()
            print("🔌 데이터베이스 연결이 종료되었습니다.")

# ▼▼▼ [수정] 질문 없이 바로 실행되도록 변경 ▼▼▼
if __name__ == '__main__':
    print("⚠️ 경고: 기존의 rooms와 beds 테이블 데이터가 모두 삭제됩니다.")
    
    # (선택사항) 실행 전 기존 데이터 삭제
    try:
        db_connection = mysql.connector.connect(**DB_CONFIG)
        cursor = db_connection.cursor()
        # 외래 키 제약 조건 때문에 beds를 먼저, rooms를 나중에 삭제해야 함
        print("\n🧹 기존 데이터를 삭제하는 중...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;") # 외래 키 체크 임시 비활성화
        cursor.execute("TRUNCATE TABLE beds;")
        cursor.execute("TRUNCATE TABLE rooms;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;") # 외래 키 체크 다시 활성화
        db_connection.commit()
        print("🧹 기존 데이터 삭제 완료.")
    except Error as e:
        # 테이블이 아직 없을 경우 오류가 날 수 있지만, 무시하고 진행합니다.
        print(f"-> 기존 데이터 삭제 중 오류 발생 (무시하고 진행): {e}")
    finally:
        if 'db_connection' in locals() and db_connection.is_connected():
            cursor.close()
            db_connection.close()
    
    # 메인 함수 실행
    setup_database()

