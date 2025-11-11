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
  const [pendingNewChatAction, setPendingNewChatAction] = useState(null);
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

  useEffect(() => {
    const handleModelSelectionRequest = (event) => {
      const detail = event.detail || {};
      if (detail.onConfirm && typeof detail.onConfirm === 'function') {
        setPendingNewChatAction(() => detail.onConfirm);
      } else {
        setPendingNewChatAction(null);
      }
      setIsModelModalOpen(true);
    };

    window.addEventListener('open-model-selection', handleModelSelectionRequest);
    return () => {
      window.removeEventListener('open-model-selection', handleModelSelectionRequest);
    };
  }, []);

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

  const handleModelModalClose = () => {
    setIsModelModalOpen(false);
    setPendingNewChatAction(null);
  };

  const handleModelModalConfirm = (models) => {
    if (!models || models.length === 0) return;
    
    // pendingNewChatAction이 있으면 (왼쪽 사이드바 + 버튼) 그대로 실행
    if (pendingNewChatAction) {
      pendingNewChatAction(models);
      setPendingNewChatAction(null);
      setIsModelModalOpen(false);
      return;
    }
    
    // 오른쪽 위 + 버튼으로 모델 변경한 경우
    // 현재 대화의 모델과 비교하여 변경되었으면 새 대화 생성
    const params = new URLSearchParams(location.search);
    const currentCid = params.get('cid');
    
    if (currentCid) {
      try {
        const history = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]');
        const currentConversation = history.find(conv => conv.id === currentCid);
        
        if (currentConversation) {
          const historyModels = (currentConversation.selectedModels || []).sort();
          const newModels = [...models].sort();
          
          // 모델이 변경되었는지 확인
          const modelsChanged = JSON.stringify(historyModels) !== JSON.stringify(newModels);
          
          if (modelsChanged) {
            console.log('🔄 모델 변경 감지! 새 대화 생성');
            console.log('이전 모델:', historyModels);
            console.log('새 모델:', newModels);
            
            // 새 대화 생성
            const newId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
            const newItem = {
              id: newId,
              title: "새 대화",
              updatedAt: Date.now(),
              selectedModels: models
            };
            
            const updatedHistory = [newItem, ...history].slice(0, 100);
            sessionStorage.setItem(HISTORY_KEY, JSON.stringify(updatedHistory));
            
            // storage 이벤트 발생
            window.dispatchEvent(new StorageEvent('storage', {
              key: HISTORY_KEY,
              newValue: JSON.stringify(updatedHistory)
            }));
            
            // 메시지 복사 (모델 변경에 따라 optimal 메시지 처리)
            const allMessages = JSON.parse(sessionStorage.getItem('aiofai:messages') || '{}');
            const oldMessages = allMessages[currentCid] || {};
            const newMessages = {};
            
            // 공통 모델의 메시지만 복사
            const unchangedModels = historyModels.filter(model => newModels.includes(model));
            unchangedModels.forEach(modelId => {
              if (oldMessages[modelId]) {
                newMessages[modelId] = [...oldMessages[modelId]];
              }
            });
            
            // 모든 AI가 바뀌었는지 확인
            const allModelsChanged = unchangedModels.length === 0;
            
            // 모든 AI가 바뀌었을 때만 optimal 메시지 초기화
            // 일부 AI만 바뀌었을 때는 optimal 메시지 유지
            if (allModelsChanged) {
              console.log('🔄 모든 AI가 변경됨 - optimal 메시지 초기화');
              // optimal 메시지는 포함하지 않음 (초기화)
            } else {
              console.log('🔄 일부 AI만 변경됨 - optimal 메시지 유지');
              // optimal 메시지 유지 (기존 모델이 남아있으므로)
              if (oldMessages['optimal']) {
                newMessages['optimal'] = [...oldMessages['optimal']];
              }
              // 유사도 데이터도 유지
              if (oldMessages['_similarityData']) {
                newMessages['_similarityData'] = { ...oldMessages['_similarityData'] };
              }
            }
            
            allMessages[newId] = newMessages;
            sessionStorage.setItem('aiofai:messages', JSON.stringify(allMessages));
            
            // 모델 설정
            setSelectedModels(models);
            
            // 새 대화로 이동
            navigate(`/?cid=${newId}`);
            
            console.log('✅ 새 대화 생성 완료:', {
              newId,
              unchangedModels,
              allModelsChanged,
              newMessagesKeys: Object.keys(newMessages),
              hasOptimal: !!newMessages['optimal'],
              note: allModelsChanged ? '모든 AI 변경 - optimal 초기화' : '일부 AI 변경 - optimal 유지'
            });
          } else {
            // 모델이 변경되지 않았으면 그냥 모델만 업데이트
            setSelectedModels(models);
          }
        } else {
          // 현재 대화를 찾을 수 없으면 새 대화 생성
          const newId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
          const newItem = {
            id: newId,
            title: "새 대화",
            updatedAt: Date.now(),
            selectedModels: models
          };
          
          const updatedHistory = [newItem, ...history].slice(0, 100);
          sessionStorage.setItem(HISTORY_KEY, JSON.stringify(updatedHistory));
          
          window.dispatchEvent(new StorageEvent('storage', {
            key: HISTORY_KEY,
            newValue: JSON.stringify(updatedHistory)
          }));
          
          setSelectedModels(models);
          navigate(`/?cid=${newId}`);
        }
      } catch (error) {
        console.error('모델 변경 처리 중 오류:', error);
        setSelectedModels(models);
      }
    } else {
      // cid가 없으면 그냥 모델만 업데이트
      setSelectedModels(models);
    }
    
    setIsModelModalOpen(false);
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
                onClick={() => {
                  setPendingNewChatAction(null);
                  setIsModelModalOpen(true);
                }}
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
                onClick={() => {
                  setPendingNewChatAction(null);
                  setIsModelModalOpen(true);
                }}
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
        onClose={handleModelModalClose}
        onConfirm={handleModelModalConfirm}
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