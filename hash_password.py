# hash_password.py
from flask import Flask
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)

# ▼▼▼ 여기에 암호화하고 싶은 비밀번호를 입력하세요 ▼▼▼
password_to_hash = 'admin123' 

hashed_password = bcrypt.generate_password_hash(password_to_hash).decode('utf-8')

print("\n암호화된 비밀번호:")
print(hashed_password)
print("\n위 문자열을 복사해서 DB에 저장하세요.\n")