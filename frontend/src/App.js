// src/App.js
import React, { useMemo, useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import WelcomePage from './pages/WelcomePage';
import MainPage from './pages/MainPage';
import OCRToolPage from './pages/OCRToolPage';
// 👇 기존 단일 페이지 import 제거하고 아래 두 개로 교체
import VideoListPage from './pages/VideoListPage';
import VideoChatDetailPage from './pages/VideoChatDetailPage';

import KakaoCallback from './components/KakaoCallback';
import NaverCallback from './components/NaverCallback';
import { ChatProvider } from './context/ChatContext';
import { loginSuccess } from './store/authSlice';

const HISTORY_KEY = "aiofai:conversations";

function App() {
  const dispatch = useDispatch();

  const [showWelcome, setShowWelcome] = useState(true);
  const [selectedModels, setSelectedModels] = useState([]);

  useEffect(() => {
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
      try {
        const userData = JSON.parse(savedUser);
        dispatch(loginSuccess(userData));
      } catch (error) {
        console.error('사용자 정보 복원 실패:', error);
        localStorage.removeItem('user');
      }
    }
  }, [dispatch]);

  const handleStartChat = (models) => {
    setSelectedModels(models || []);
    setShowWelcome(false);
  };

  // 홈 라우트 컴포넌트
  const HomeRoute = () => {
    const navigate = useNavigate();
    const location = useLocation();

    // URL에 cid가 있으면 MainPage 표시, 없으면 WelcomePage 표시
    const params = new URLSearchParams(location.search);
    const cid = params.get('cid');

    const handleStartChatWithHistory = (models) => {
      // 새 대화 ID 생성
      const newId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
      const newConversation = {
        id: newId,
        title: "새 대화",
        updatedAt: Date.now(),
        selectedModels: models || [] // 선택한 AI 모델 저장
      };
      
      try {
        // 히스토리에 저장 (한 번만)
        const history = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]');
        const updatedHistory = [newConversation, ...history].slice(0, 100);
        sessionStorage.setItem(HISTORY_KEY, JSON.stringify(updatedHistory));
        
        // storage 이벤트 발생
        window.dispatchEvent(new StorageEvent('storage', {
          key: HISTORY_KEY,
          newValue: JSON.stringify(updatedHistory)
        }));
      } catch (error) {
        console.error('히스토리 저장 실패:', error);
      }
      
      // 모델 설정 및 MainPage로 이동
      setSelectedModels(models || []);
      navigate(`/?cid=${newId}`, { replace: true });
    };

    if (!cid) {
      // cid가 없으면 WelcomePage 표시
      return <WelcomePage onStartChat={handleStartChatWithHistory} />;
    }

    // cid가 있으면 MainPage 표시
    return (
      <ChatProvider initialModels={selectedModels}>
        <MainPage />
      </ChatProvider>
    );
  };

  return (
    <Routes>
      {/* 홈 */}
      <Route path="/" element={<HomeRoute />} />

      {/* OCR 페이지는 Provider 필요 */}
      <Route
        path="/ocr-tool"
        element={
          <ChatProvider initialModels={[]}>
            <OCRToolPage />
          </ChatProvider>
        }
      />


      <Route path="/video-chat" element={<VideoListPage />} />
      <Route path="/video-chat/:videoId" element={<VideoChatDetailPage />} />

      {/* 소셜 로그인 콜백 */}
      <Route path="/auth/kakao/callback" element={<KakaoCallback />} />
      <Route path="/auth/naver/callback" element={<NaverCallback />} />

      {/* 그 외 경로는 홈으로 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;