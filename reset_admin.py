import bcrypt
from utils import init_supabase

supabase = init_supabase()

# 重設 admin 帳號密碼為 admin123
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw("admin123".encode('utf-8'), salt)

print("正在更新帳號 admin 的密碼...")
result = supabase.table("teachers_auth").update({"hashed_password": hashed.decode('utf-8')}).eq("username", "admin").execute()
print("更新結果:", result.data)
