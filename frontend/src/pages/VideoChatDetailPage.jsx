import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, CheckCircle, RefreshCw } from 'lucide-react';
import { api } from '../utils/api';
import OptimalResponseRenderer from '../components/OptimalResponseRenderer';
import FrameModal from '../components/FrameModal';
import AnalysisStatusView from '../components/AnalysisStatusView';

const FRAME_PREVIEW_LIMIT = 3;

const MessageFramePreview = ({ frames = [], onFrameClick, maxInitial = FRAME_PREVIEW_LIMIT }) => {
  const sortedFrames = useMemo(() => {
    if (!Array.isArray(frames)) return [];
    return [...frames].sort((a, b) => {
      const scoreDiff = (b?.relevance_score ?? 0) - (a?.relevance_score ?? 0);
      if (scoreDiff !== 0) return scoreDiff;
      return (a?.timestamp ?? 0) - (b?.timestamp ?? 0);
    });
  }, [frames]);

  const totalFrames = Math.min(sortedFrames.length, maxInitial ?? sortedFrames.length);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (totalFrames === 0) {
      setCurrentIndex(0);
    } else if (currentIndex >= totalFrames) {
      setCurrentIndex(0);
    }
  }, [totalFrames, currentIndex]);

  if (totalFrames === 0) {
    return null;
  }

  const limitedFrames = sortedFrames.slice(0, totalFrames);
  const total = limitedFrames.length;
  const safeIndex = ((currentIndex % total) + total) % total;
  const currentFrame = limitedFrames[safeIndex];
  
  const goPrev = () => setCurrentIndex((prev) => (prev - 1 + total) % total);
  const goNext = () => setCurrentIndex((prev) => (prev + 1) % total);
  
  return (
    <div className="relative">
      <div 
        className="group relative bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-lg hover:border-blue-300 transition-all duration-300 cursor-pointer"
        onClick={() => onFrameClick && onFrameClick(currentFrame)}
      >
        <div className="relative">
          <img
            src={`${api.defaults.baseURL}${currentFrame.image_url}`}
            alt={`프레임 ${currentFrame.image_id}`}
            className="w-full h-32 object-cover group-hover:scale-105 transition-transform duration-300"
            onError={(e) => {
              console.error(`프레임 이미지 로드 실패: ${currentFrame.image_url}`);
              e.target.style.display = 'none';
            }}
          />
          {total > 1 && (
            <>
              <button
                type="button"
                className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-700 rounded-full p-1 shadow transition"
                onClick={(e) => {
                  e.stopPropagation();
                  goPrev();
                }}
              >
                ‹
              </button>
              <button
                type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-700 rounded-full p-1 shadow transition"
                onClick={(e) => {
                  e.stopPropagation();
                  goNext();
                }}
              >
                ›
              </button>
            </>
          )}
        </div>
        
        {/* 프레임 정보 숨김 처리 */}
        {/* <div className="p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <div className="flex items-center bg-blue-50 text-blue-700 px-2 py-1 rounded-full text-xs font-medium">
                <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {currentFrame.timestamp.toFixed(1)}초
              </div>
              <div className="flex items-center bg-green-50 text-green-700 px-2 py-1 rounded-full text-xs font-medium">
                <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {currentFrame.relevance_score}점
              </div>
            </div>
            <div className="text-xs text-gray-500">
              #{currentFrame.image_id} · {safeIndex + 1}/{total}
            </div>
          </div>
          
          {currentFrame.persons && currentFrame.persons.length > 0 && (
            <div className="flex items-center space-x-2">
              <div className="flex items-center bg-purple-50 text-purple-700 px-2 py-1 rounded-full text-xs font-medium">
                <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                사람 {currentFrame.persons.length}명
              </div>
              {currentFrame.objects && currentFrame.objects.length > 0 && (
                <div className="flex items-center bg-orange-50 text-orange-700 px-2 py-1 rounded-full text-xs font-medium">
                  <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  객체 {currentFrame.objects.length}개
                </div>
              )}
            </div>
          )}
        </div> */}
      </div>
    </div>
  );
};

const VideoChatDetailPage = () => {
  const { videoId } = useParams();
  const navigate = useNavigate();
  
  // 상태 관리
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState('unknown');
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisMessage, setAnalysisMessage] = useState('');
  
  // 프레임 모달 상태
  const [selectedFrame, setSelectedFrame] = useState(null);
  const [isFrameModalOpen, setIsFrameModalOpen] = useState(false);
  const [showBboxOverlay, setShowBboxOverlay] = useState(true);
  
  // 스크롤 ref
  const scrollRefs = useRef({
    gpt: null,
    claude: null,
    mixtral: null,
    optimal: null
  });

  const loadingText = isLoading ? "분석중…" : "";

  // 스크롤 함수
  const scrollToBottomForModel = (modelId) => {
    const scrollRef = scrollRefs.current[modelId];
    if (scrollRef) {
      scrollRef.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // 비디오 데이터 로드
  const loadVideoData = async (id) => {
    try {
      const response = await api.get(`/api/video/${id}/analysis/`);
      const videoData = {
        ...response.data,
        id: response.data.video_id || response.data.id
      };
      setSelectedVideo(videoData);
      setAnalysisStatus(videoData.analysis_status);
      
      if (response.data.analysis_status === 'pending' || response.data.analysis_status === 'analyzing') {
        checkAnalysisStatus(id);
      } else if (response.data.analysis_status === 'completed') {
        loadChatHistory(id);
      }
    } catch (error) {
      console.error('비디오 데이터 로드 실패:', error);
    }
  };

  // 분석 상태 확인
  const checkAnalysisStatus = async (id) => {
    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/api/video/${id}/analysis/`);
        setAnalysisStatus(response.data.analysis_status);
        
        if (response.data.progress) {
          setAnalysisProgress(response.data.progress.analysis_progress || 0);
          setAnalysisMessage(response.data.progress.analysis_message || '');
        }
        
        if (response.data.analysis_status === 'completed') {
          clearInterval(interval);
          setAnalysisProgress(100);
          setAnalysisMessage('분석 완료');
          loadChatHistory(id);
        } else if (response.data.analysis_status === 'failed') {
          clearInterval(interval);
          setAnalysisProgress(0);
          setAnalysisMessage(response.data.progress?.analysis_message || '분석 실패');
        }
      } catch (error) {
        console.error('분석 상태 확인 실패:', error);
        clearInterval(interval);
        setAnalysisMessage('분석 상태 확인 실패');
      }
    }, 2000);
  };

  // 분석 시작
  const startAnalysis = async () => {
    try {
      setIsLoading(true);
      setAnalysisProgress(0);
      setAnalysisMessage('분석을 시작합니다...');
      
      const response = await api.post(`/api/video/${selectedVideo?.id}/analysis/`);
      
      if (response.data.status === 'pending') {
        setAnalysisStatus('pending');
        checkAnalysisStatus(selectedVideo.id);
      }
    } catch (error) {
      console.error('분석 시작 실패:', error);
      alert('분석 시작에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // 채팅 히스토리 로드
  const loadChatHistory = async (id) => {
    try {
      const response = await api.get(`/api/video/${id}/chat/`);
      setMessages(response.data.messages || []);
    } catch (error) {
      console.error('채팅 히스토리 로드 실패:', error);
    }
  };

  // 메시지 전송
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !selectedVideo) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await api.post(`/api/video/${selectedVideo.id}/chat/`, {
        message: inputMessage,
        session_id: null
      });

      if (response.data.message_type === 'special_command') {
        const aiMessage = {
          id: `special_${Date.now()}`,
          type: 'ai_optimal',
          content: response.data.message,
          created_at: new Date().toISOString(),
          relevant_frames: []
        };
        setMessages(prev => [...prev, aiMessage]);
      } else if (response.data.ai_responses) {
        // 순차적으로 답변 표시
        const aiMessages = [];
        
        console.log('📋 백엔드 응답 데이터:', response.data.ai_responses);
        if (response.data.ai_responses.individual) {
          console.log('✅ 개별 AI 응답 수신:', response.data.ai_responses.individual.length, '개');
          response.data.ai_responses.individual.forEach(aiResponse => {
            console.log(`  - ${aiResponse.model}: ${aiResponse.content?.substring(0, 50)}...`);
            aiMessages.push({
              id: aiResponse.id,
              type: 'ai',
              ai_model: aiResponse.model,
              content: aiResponse.content,
              created_at: aiResponse.created_at,
              relevant_frames: response.data.relevant_frames || []
            });
          });
        } else {
          console.log('⚠️ 개별 AI 응답이 없습니다:', response.data.ai_responses);
        }
        
        // 개별 AI 답변들을 순차적으로 표시
        for (let i = 0; i < aiMessages.length; i++) {
          setMessages(prev => [...prev, aiMessages[i]]);
          // 각 답변 사이에 0.5초 대기
          if (i < aiMessages.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 500));
          }
        }
        
        // 통합 응답 표시
        if (response.data.ai_responses.optimal) {
          console.log('통합 응답 생성 중...', response.data.ai_responses.optimal);
          await new Promise(resolve => setTimeout(resolve, 1000)); // 1초 대기
          
          const optimalMessage = {
            id: `optimal_${Date.now()}`,
            type: 'ai_optimal',
            content: response.data.ai_responses.optimal.content,
            created_at: response.data.ai_responses.optimal.created_at,
            relevant_frames: response.data.relevant_frames || []
          };
          console.log('통합 응답 메시지 추가:', optimalMessage);
          setMessages(prev => {
            const newMessages = [...prev, optimalMessage];
            console.log('전체 메시지 목록:', newMessages);
            return newMessages;
          });
        } else {
          console.log('통합 응답 없음:', response.data.ai_responses);
        }
      }
    } catch (error) {
      console.error('메시지 전송 실패:', error);
      alert('메시지 전송에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };


  // 빠른 액션
  const handleQuickAction = async (message) => {
    if (!selectedVideo) return;
    
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: message,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await api.post(`/api/video/${selectedVideo.id}/chat/`, {
        message: message
      });

      if (response.data.message_type === 'special_command') {
        const aiMessage = {
          id: `special_${Date.now()}`,
          type: 'ai_optimal',
          content: response.data.message,
          created_at: new Date().toISOString(),
          relevant_frames: []
        };
        setMessages(prev => [...prev, aiMessage]);
      } else if (response.data.ai_responses) {
        const aiMessages = [];
        
        if (response.data.ai_responses.individual) {
          response.data.ai_responses.individual.forEach(aiResponse => {
            aiMessages.push({
              id: aiResponse.id,
              type: 'ai',
              ai_model: aiResponse.model,
              content: aiResponse.content,
              created_at: aiResponse.created_at,
              relevant_frames: response.data.relevant_frames || []
            });
          });
        }
        
        if (response.data.ai_responses.optimal) {
          aiMessages.push({
            id: `optimal_${Date.now()}`,
            type: 'ai_optimal',
            content: response.data.ai_responses.optimal.content,
            created_at: response.data.ai_responses.optimal.created_at,
            relevant_frames: response.data.relevant_frames || []
          });
        }
        
        setMessages(prev => [...prev, ...aiMessages]);
      }
    } catch (error) {
      console.error('빠른 액션 실행 실패:', error);
      alert('빠른 액션 실행에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // 목록으로 돌아가기
  const backToVideoList = () => {
    navigate('/video-chat');
  };

  // 프레임 클릭 핸들러
  const handleFrameClick = (frame) => {
    setSelectedFrame(frame);
    setIsFrameModalOpen(true);
  };

  // 컴포넌트 마운트 시 초기화
  useEffect(() => {
    if (videoId) {
      loadVideoData(videoId);
    }
  }, [videoId]);

  // 메시지 변경 시 스크롤
  useEffect(() => {
    ['gpt', 'claude', 'mixtral', 'optimal'].forEach(modelId => {
      scrollToBottomForModel(modelId);
    });
  }, [messages]);

  // 분석 중인 경우 주기적으로 상태 업데이트
  useEffect(() => {
    if (selectedVideo && (selectedVideo.analysis_status === 'pending' || selectedVideo.analysis_status === 'analyzing')) {
      const interval = setInterval(() => {
        loadVideoData(selectedVideo.id);
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [selectedVideo]);

  // 분석 상태에 따른 렌더링
  if (analysisStatus !== 'completed') {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-2xl mx-auto p-6">
          <AnalysisStatusView
            status={analysisStatus}
            progress={analysisProgress}
            message={analysisMessage}
            onRetry={startAnalysis}
            onBackToList={backToVideoList}
          />
        </div>
      </div>
    );
  }

  // 채팅 인터페이스 렌더링
  return (
    <div className="min-h-screen bg-gray-50">
      <style>{`
        .chat-header {
          background: rgba(245, 242, 234, 0.4);
          backdrop-filter: blur(10px);
          border-bottom: 1px solid rgba(139, 168, 138, 0.15);
          height: 60px;
        }
        .chat-column {
          background: rgba(255, 255, 255, 0.3);
          backdrop-filter: blur(5px);
          min-height: 0;
        }
        .chat-container {
          height: calc(100vh - 200px);
          min-height: 0;
        }
        .chat-column .overflow-y-auto::-webkit-scrollbar {
          width: 6px;
        }
        .chat-column .overflow-y-auto::-webkit-scrollbar-thumb {
          background: rgba(139, 168, 138, 0.3);
          border-radius: 3px;
        }
        .aiofai-input-area {
          background: rgba(245, 242, 234, 0.4);
          backdrop-filter: blur(10px);
          border-top: 1px solid rgba(139, 168, 138, 0.15);
          padding: 0.75rem 1.2rem;
          position: sticky;
          bottom: 0;
          z-index: 20;
        }
        .aiofai-user-message {
          background: linear-gradient(135deg, #5d7c5b, #8ba88a);
          color: #ffffff;
          padding: 1.2rem 1.5rem;
          border-radius: 24px 24px 8px 24px;
          max-width: 85%;
          box-shadow: 0 8px 32px rgba(93, 124, 91, 0.3);
          font-weight: 500;
          line-height: 1.5;
        }
        .aiofai-bot-message {
          background: rgba(255, 255, 255, 0.8);
          backdrop-filter: blur(10px);
          color: #2d3e2c;
          border: 1px solid rgba(139, 168, 138, 0.2);
          padding: 1.2rem 1.5rem;
          border-radius: 24px 24px 24px 8px;
          max-width: 85%;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
          line-height: 1.6;
        }
        .optimal-response {
          background: rgba(255, 255, 255, 0.95) !important;
          border: 2px solid rgba(139, 168, 138, 0.3) !important;
          padding: 1.5rem !important;
          border-radius: 16px !important;
          max-width: 95% !important;
          box-shadow: 0 8px 32px rgba(139, 168, 138, 0.15) !important;
        }
        .optimal-section {
          margin-bottom: 1.5rem;
          padding: 1rem;
          border-bottom: 1px solid #e5e7eb;
        }
        .section-title {
          margin: 0 0 1rem 0;
          font-size: 1rem;
          font-weight: 600;
          color: #374151;
        }
        .section-content {
          color: #374151;
          line-height: 1.6;
          font-size: 0.95rem;
        }
        .analysis-grid {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        .analysis-item {
          padding: 1rem;
          background: rgba(139, 168, 138, 0.05);
          border-radius: 8px;
          border: 1px solid rgba(139, 168, 138, 0.2);
        }
        .analysis-ai-name {
          font-weight: 600;
          color: #2d3e2c;
          margin-bottom: 0.5rem;
        }
        .frames-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem;
        }
        .frame-card {
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          padding: 0.75rem;
          background: rgba(255, 255, 255, 0.8);
        }
        .frame-info {
          display: flex;
          justify-content: space-between;
          margin-bottom: 0.5rem;
        }
        .frame-timestamp, .frame-score {
          font-size: 0.75rem;
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          background: #f3f4f6;
        }
        .frame-image {
          width: 100%;
          height: 120px;
          object-fit: cover;
          border-radius: 4px;
          margin-bottom: 0.5rem;
        }
        .frame-tags {
          display: flex;
          gap: 0.25rem;
        }
        .frame-tag {
          font-size: 0.75rem;
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
        }
        .person-tag {
          background: #dcfce7;
          color: #166534;
        }
        .object-tag {
          background: #dbeafe;
          color: #1e40af;
        }
      `}</style>

      {/* 헤더 */}
      <div className="chat-header flex items-center justify-between px-6">
        <div className="flex items-center">
          <button
            onClick={backToVideoList}
            className="mr-4 p-2 hover:bg-white/20 rounded-lg transition-colors"
          >
            <RefreshCw className="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <h1 className="text-lg font-semibold text-gray-800">
              {selectedVideo?.original_name || '영상 채팅'}
            </h1>
            <p className="text-sm text-gray-600">
              {selectedVideo && `${(selectedVideo.file_size / (1024 * 1024)).toFixed(1)}MB`}
            </p>
          </div>
        </div>
        <div className="flex items-center text-sm text-green-600">
          <CheckCircle className="w-4 h-4 mr-1" />
          분석 완료
        </div>
      </div>

      {/* 메시지 영역 */}
      <div className="chat-container flex overflow-hidden h-full">
        {['gpt', 'claude', 'mixtral', 'optimal'].map((modelId) => (
          <div key={modelId} className="border-r flex-1 flex flex-col chat-column">
            <div className="flex-shrink-0 px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
              <div className="text-center text-sm font-medium text-gray-600 flex-1">
                {modelId === 'optimal' ? '통합 응답' : 
                 modelId === 'gpt' ? 'GPT' :
                 modelId === 'claude' ? 'CLAUDE' :
                 modelId === 'mixtral' ? 'GEMINI' : modelId.toUpperCase()}
              </div>
              <button
                onClick={() => scrollToBottomForModel(modelId)}
                className="ml-2 p-1 text-gray-400 hover:text-gray-600 transition-colors"
                title="맨 아래로 스크롤"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                </svg>
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto px-4 py-3" style={{ height: 'calc(100vh - 260px)' }}>
              {messages.map((message, index) => {
                const isUser = message.type === 'user';
                const isOptimal = modelId === 'optimal' && message.type === 'ai_optimal';
                
                // 디버깅 로그
                if (modelId === 'optimal') {
                  console.log(`통합 응답 탭 - 메시지 ${index}:`, {
                    messageType: message.type,
                    isOptimal,
                    messageId: message.id,
                    content: message.content?.substring(0, 50) + '...'
                  });
                }
                // 모델 ID 매핑
                const getModelKey = (aiModel) => {
                  if (!aiModel) return null;
                  const modelLower = aiModel.toLowerCase();
                  if (modelLower.includes('gpt')) return 'gpt';
                  if (modelLower.includes('claude')) return 'claude';
                  if (modelLower.includes('gemini')) return 'mixtral'; // Gemini를 Mixtral 탭에 표시
                  return aiModel;
                };
                const isModelMessage = modelId !== 'optimal' && getModelKey(message.ai_model) === modelId;
                
                // 디버깅: 모델 매칭 확인
                if (message.type === 'ai' && !isUser) {
                  console.log(`🔍 모델 매칭 체크 [${modelId}]:`, {
                    ai_model: message.ai_model,
                    getModelKey: getModelKey(message.ai_model),
                    modelId,
                    isModelMessage,
                    messageType: message.type
                  });
                }
                const isSpecialCommand = message.type === 'ai_optimal' && message.id && message.id.startsWith('special_');
                
                if (isSpecialCommand) {
                  return (
                    <div key={`${modelId}-${index}`} className="flex justify-start mb-4">
                      <div className="aiofai-bot-message optimal-response">
                        <div className="whitespace-pre-wrap">{message.content}</div>
                        <div className="text-xs opacity-60 mt-2">
                          {message.created_at 
                            ? (() => {
                                const date = new Date(message.created_at);
                                // UTC 시간을 KST로 변환 (UTC+9)
                                const kstDate = new Date(date.getTime() + (9 * 60 * 60 * 1000));
                                return kstDate.toLocaleString('ko-KR', { 
                                  hour: '2-digit',
                                  minute: '2-digit',
                                  second: '2-digit',
                                  hour12: true
                                });
                              })()
                            : new Date().toLocaleString('ko-KR', { 
                                timeZone: 'Asia/Seoul',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                                hour12: true
                              })
                          }
                        </div>
                      </div>
                    </div>
                  );
                }
                
                if (!isUser && !isOptimal && !isModelMessage) return null;
                
                return (
                  <div key={`${modelId}-${index}`} className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
                    <div className={`${isUser ? "aiofai-user-message" : "aiofai-bot-message"} ${isOptimal || isSpecialCommand ? "optimal-response" : ""}`}>
                      {isOptimal || isSpecialCommand ? (
                        <div>
                          <OptimalResponseRenderer 
                            content={message.content} 
                            relevantFrames={message.relevant_frames}
                            onFrameClick={handleFrameClick}
                            similarityData={message.similarityData}
                          />
                          <div className="text-xs opacity-60 mt-2">
                            {message.created_at 
                              ? (() => {
                                  const date = new Date(message.created_at);
                                  // UTC 시간을 KST로 변환 (UTC+9)
                                  const kstDate = new Date(date.getTime() + (9 * 60 * 60 * 1000));
                                  return kstDate.toLocaleString('ko-KR', { 
                                    hour: '2-digit',
                                    minute: '2-digit',
                                    second: '2-digit',
                                    hour12: true
                                  });
                                })()
                              : new Date().toLocaleString('ko-KR', { 
                                  timeZone: 'Asia/Seoul',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                  second: '2-digit',
                                  hour12: true
                                })
                            }
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div className="whitespace-pre-wrap">{message.content}</div>
                          
                          {message.relevant_frames && message.relevant_frames.length > 0 && (
                            <div className="mt-4">
                              <div className="text-sm font-semibold text-gray-700 mb-3 flex items-center">
                                <svg className="w-4 h-4 mr-2 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                                관련 프레임 ({message.relevant_frames.length}개)
                              </div>
                              <MessageFramePreview
                                frames={message.relevant_frames}
                                onFrameClick={handleFrameClick}
                              />
                            </div>
                          )}
                          
                          <div className="text-xs opacity-60 mt-2">
                            {message.created_at 
                              ? (() => {
                                  const date = new Date(message.created_at);
                                  // UTC 시간을 KST로 변환 (UTC+9)
                                  const kstDate = new Date(date.getTime() + (9 * 60 * 60 * 1000));
                                  return kstDate.toLocaleString('ko-KR', { 
                                    hour: '2-digit',
                                    minute: '2-digit',
                                    second: '2-digit',
                                    hour12: true
                                  });
                                })()
                              : new Date().toLocaleString('ko-KR', { 
                                  timeZone: 'Asia/Seoul',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                  second: '2-digit',
                                  hour12: true
                                })
                            }
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isLoading && (
                <div className="flex justify-start mb-4">
                  <div className="bg-gray-100 text-gray-800 p-4 rounded-2xl">
                    {loadingText || "입력 중..."}
                  </div>
                </div>
              )}

              <div className="h-3" />
              <div ref={(el) => { scrollRefs.current[modelId] = el; }} />
            </div>
          </div>
        ))}
      </div>

      {/* 빠른 액션 버튼들 */}
      <div className="px-6 py-3 bg-white/50 backdrop-blur-sm border-t border-gray-200">
        <div className="flex space-x-3 mb-3">
          <button
            onClick={() => handleQuickAction('영상 요약해줘')}
            className="px-4 py-2 text-white text-sm rounded-lg hover:opacity-90 transition-all duration-200 shadow-sm hover:shadow-md flex items-center font-medium"
            style={{ backgroundColor: 'rgb(139, 168, 138)' }}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            영상 요약
          </button>
          <button
            onClick={() => handleQuickAction('영상 하이라이트 알려줘')}
            className="px-4 py-2 text-white text-sm rounded-lg hover:opacity-90 transition-all duration-200 shadow-sm hover:shadow-md flex items-center font-medium"
            style={{ backgroundColor: 'rgb(139, 168, 138)' }}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            하이라이트
          </button>
        </div>
      </div>

      {/* 입력 영역 */}
      <div className="aiofai-input-area">
        <div className="flex space-x-3">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="영상에 대해 질문해보세요..."
            className="flex-1 px-4 py-3 bg-white/80 backdrop-blur-sm border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-transparent transition-all duration-200"
            disabled={isLoading}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || isLoading}
            className="px-6 py-3 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-2xl hover:from-green-600 hover:to-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* 프레임 모달 */}
      <FrameModal
        frame={selectedFrame}
        isOpen={isFrameModalOpen}
        onClose={() => setIsFrameModalOpen(false)}
        showBboxOverlay={showBboxOverlay}
        setShowBboxOverlay={setShowBboxOverlay}
      />
    </div>
  );
};

export default VideoChatDetailPage;