const express = require('express');
const path = require('path');
const multer = require('multer');
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const app = express();
const PORT = 3000;

// 보안 헤더
app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    next();
});

app.use(express.json());
// HTML 파일이 있는 폴더 경로 (public 또는 현재 폴더)
app.use(express.static(path.join(__dirname, 'public')));

const upload = multer({
    dest: 'uploads/',
    limits: { fileSize: 10 * 1024 * 1024 }, // 10MB
    fileFilter: (req, file, cb) => {
        const allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp'];
        if (allowed.includes(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error('지원하지 않는 이미지 형식입니다.'), false);
        }
    }
});

app.post('/api/upload-floorplan', upload.single('floorplanImage'), async (req, res) => {
    if (!req.file) {
        return res.status(400).json({ success: false, message: '이미지 파일이 필요합니다.' });
    }

    try {
        console.log(`\n🤖 파이썬 AI 서버로 도면 분석 요청 중...`);

        const form = new FormData();
        form.append('file', fs.createReadStream(req.file.path), req.file.originalname);

        const pythonResponse = await axios.post('http://127.0.0.1:8000/analyze-floorplan', form, {
            headers: { ...form.getHeaders() }
        });

        console.log(`✅ 파이썬 분석 완료! 프론트로 데이터를 넘깁니다.`);
        res.json(pythonResponse.data);

    } catch (error) {
        console.error('❌ 파이썬 서버 통신 에러:', error.message);
        res.status(500).json({ success: false, message: 'AI 분석 중 오류가 발생했습니다.' });
    } finally {
        fs.unlink(req.file.path, (err) => {
            if (err) console.error("임시 파일 삭제 실패:", err);
        });
    }
});

app.listen(PORT, () => {
    console.log(`Node.js 서버 실행 됨 👉 http://localhost:${PORT}`);
});