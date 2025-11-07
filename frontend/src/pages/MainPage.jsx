// src/pages/MainPage.js
import React, { useState, useEffect } from "react";
import { useSelector, useDispatch } from "react-redux";
import Loginbar from "../components/Loginbar";
import Settingbar from "../components/Settingbar";
import Sidebar from "../components/Sidebar";
import ChatBox from "../components/ChatBox";
import { Menu, Settings, UserCircle, CirclePlus, Video } from "lucide-react";
import { logout } from "../store/authSlice";
import { useNavigate, useLocation } from "react-router-dom";
import ModelSelectionModal from "../components/ModelSelectionModal";
import { useChat } from "../context/ChatContext";
import HeaderLogo from "../components/HeaderLogo";

const HISTORY_KEY = "aiofai:conversations";

const MainPage = () => {
  const [isSidebarVisible, setIsSidebarVisible] = useState(false);
  const [isSettingVisible, setIsSettingVisible] = useState(false);
  const [isLoginVisible, setIsLoginVisible] = useState(false);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const { selectedModels, setSelectedModels } = useChat();

  const user = useSelector((state) => state.auth.user);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();

  // 페이지 로드 시 대화 ID 확인 (App.js에서 이미 생성되므로 여기서는 생성하지 않음)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const cid = params.get('cid');
    
    // cid가 없으면 루트(/)로 리다이렉트 (WelcomePage로 돌아감)
    if (!cid) {
      navigate('/', { replace: true });
    }
  }, [location.search, navigate]);

  // 로그인 성공 시 로그인 모달 자동 닫기
  useEffect(() => {
    if (user && isLoginVisible) {
      setIsLoginVisible(false);
    }
  }, [user, isLoginVisible]);

  const toggleSetting = () => {
    setIsSettingVisible((v) => !v);
    setIsLoginVisible(false);
  };

  const toggleLogin = () => {
    // 이미 로그인된 상태라면 로그인 모달을 열지 않음
    if (user) {
      return;
    }
    setIsLoginVisible((v) => !v);
    setIsSettingVisible(false);
  };

  const handleLogout = () => {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("user");
    dispatch(logout());
  };

  // 배경 애니메이션 스타일
  const backgroundOverlayStyle = {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100%",
    height: "100%",
    background: `
      radial-gradient(circle at 20% 50%, rgba(139, 168, 138, 0.05) 0%, transparent 50%),
      radial-gradient(circle at 80% 20%, rgba(93, 124, 91, 0.05) 0%, transparent 50%),
      radial-gradient(circle at 40% 80%, rgba(155, 181, 154, 0.05) 0%, transparent 50%)
    `,
    pointerEvents: "none",
    zIndex: -1,
  };

  // 사용자 이름 표시 로직 개선
  const displayName = user?.full_name || user?.first_name || user?.username || "";

  return (
    <div
      className="flex flex-col h-screen relative"
      style={{
        background: "linear-gradient(135deg, #fefefe 0%, #f8f6f0 100%)",
        color: "#2d3e2c",
        overflowX: "hidden",
      }}
    >
      {/* 배경 애니메이션 오버레이 */}
      <div style={backgroundOverlayStyle} />

      <nav
        className="border-b px-6 py-3 flex items-center justify-between sticky top-0 z-100"
        style={{
          background: "rgba(248, 246, 240, 0.8)",
          backdropFilter: "blur(20px)",
          borderBottomColor: "rgba(139, 168, 138, 0.2)",
          boxShadow: "0 8px 32px rgba(93, 124, 91, 0.1)",
        }}
      >
        <div className="flex items-center space-x-4">
          <Menu
            className="w-6 h-6 text-gray-600 cursor-pointer transition-all duration-300 hover:scale-110"
            onClick={() => setIsSidebarVisible((v) => !v)}
          />
          <HeaderLogo />
        </div>

        <div className="flex items-center space-x-4">
          {user ? (
            // 로그인된 상태
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span className="text-gray-700 font-medium">
                  {displayName}님
                </span>
              </div>

              <button
                onClick={handleLogout}
                className="text-sm text-gray-600 hover:text-gray-800 transition-colors px-2 py-1 rounded hover:bg-gray-100"
                title="로그아웃"
              >
                로그아웃
              </button>

              <Video
                className="w-6 h-6 text-gray-600 cursor-pointer transition-all duration-300 hover:scale-110"
                onClick={() => navigate('/video-chat')}
                title="영상 채팅"
              />
              <CirclePlus
                className="w-6 h-6 text-gray-600 cursor-pointer transition-all duration-300 hover:scale-110"
                onClick={() => setIsModelModalOpen(true)}
                title="AI 모델 선택"
              />
              <Settings
                className="w-6 h-6 text-gray-600 cursor-pointer transition-all duration-300 hover:scale-110"
                onClick={toggleSetting}
                title="설정"
              />
            </div>
          ) : (
            // 로그인되지 않은 상태
            <>
              <Video
                className="w-6 h-6 text-gray-600 cursor-pointer transition-all duration-300 hover:scale-110"
                onClick={() => navigate('/video-chat')}
                title="영상 채팅"
              />
              <CirclePlus
                className="w-6 h-6 text-gray-600 cursor-pointer transition-all duration-300 hover:scale-110"
                onClick={() => setIsModelModalOpen(true)}
                title="AI 모델 선택"
              />
              <UserCircle
                className="w-6 h-6 text-gray-600 cursor-pointer transition-all duration-300 hover:scale-110"
                onClick={toggleLogin}
                title="로그인"
              />
              <Settings
                className="w-6 h-6 text-gray-600 cursor-pointer transition-all duration-300 hover:scale-110"
                onClick={toggleSetting}
                title="설정"
              />
            </>
          )}
        </div>
      </nav>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {isSidebarVisible && <Sidebar />}
        <div className="flex-1 overflow-hidden">
          <ChatBox />
        </div>
      </div>

      <ModelSelectionModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
        selectedModels={selectedModels}
        onModelSelect={setSelectedModels}
      />

      {isLoginVisible && (
        <Loginbar onClose={() => setIsLoginVisible(false)} />
      )}
      <Settingbar
        isOpen={isSettingVisible}
        onClose={() => setIsSettingVisible(false)}
      />
    </div>
  );
};

export default MainPage;