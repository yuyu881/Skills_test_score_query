-- 程式功能簡介：在 Supabase 建立 teachers_auth 資料表並新增第一筆預設的超級管理員帳號
-- 程式歷次修改簡說：2026-03-05/V1.0 - 初始建立
-- 建立者：User & Gemini
-- 最後一次修改日期：2026-03-05

-- 1. 建立教師帳號權限表
CREATE TABLE teachers_auth (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,      
    hashed_password VARCHAR(255) NOT NULL,    
    role VARCHAR(20) DEFAULT 'teacher',        -- 'admin' 或 'teacher'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('UTC', now())
);

-- 2. 新增預設超級管理員帳號
-- 預設帳號: admin
-- 預設密碼: admin123 (這是經過 bcrypt 洗出的 Hash，登入後請修改或建立新的 Admin)
INSERT INTO teachers_auth (username, hashed_password, role)
VALUES (
    'admin', 
    '$2b$12$R.S4R2H1D9qTQ30I1/gZGuA74Jv1Zk6E4c.E3cO45/74XqZzB.m1K', 
    'admin'
);
