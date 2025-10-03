import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Upload, Loader2, CheckCircle, XCircle, AlertCircle, Clock, FileVideo, RefreshCw } from 'lucide-react';
import { api } from '../utils/api';

const VideoChatPage = () => {
  const { videoId } = useParams();
  const navigate = useNavigate();
  // const user = useSelector(state => state.auth.user);
  
  // 상태 관리
  const [videoList, setVideoList] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [analysisStatus, setAnalysisStatus] = useState('unknown');
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisMessage, setAnalysisMessage] = useState('');
  const [showVideoList, setShowVideoList] = useState(!videoId);
  const [isDragOver, setIsDragOver] = useState(false);
  
  // 프레임 이미지 모달 상태
  const [selectedFrame, setSelectedFrame] = useState(null);
  const [isFrameModalOpen, setIsFrameModalOpen] = useState(false);
  
  // bbox 오버레이 상태
  const [showBboxOverlay, setShowBboxOverlay] = useState(true);
  const canvasRef = useRef(null);
  
  const messagesEndRef = useRef(null);
  // 각 LLM별 스크롤 ref
  const scrollRefs = useRef({
    gpt: null,
    claude: null,
    mixtral: null,
    optimal: null
  });
  const loadingText = isLoading ? "분석중…" : "";

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 각 LLM별 스크롤 함수
  const scrollToBottomForModel = (modelId) => {
    const scrollRef = scrollRefs.current[modelId];
    if (scrollRef) {
      scrollRef.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    // 모든 모델의 스크롤을 맨 아래로
    ['gpt', 'claude', 'mixtral', 'optimal'].forEach(modelId => {
      scrollToBottomForModel(modelId);
    });
  }, [messages]);

  // bbox 오버레이 토글 시 캔버스 다시 그리기
  useEffect(() => {
    if (showBboxOverlay && selectedFrame) {
      const img = document.getElementById('modal-frame-image');
      if (img && img.complete) {
        drawBboxOnCanvas(img, selectedFrame);
      }
    }
  }, [showBboxOverlay, selectedFrame]);

  // bbox를 그리는 함수
  const drawBboxOnCanvas = (imageElement, frame) => {
    if (!canvasRef.current || !imageElement) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // 캔버스 크기를 이미지에 맞게 조정
    canvas.width = imageElement.naturalWidth;
    canvas.height = imageElement.naturalHeight;
    
    // 이미지 그리기
    ctx.drawImage(imageElement, 0, 0);
    
    // bbox 그리기
    if (frame.persons && frame.persons.length > 0) {
      frame.persons.forEach((person, index) => {
        const bbox = person.bbox || [];
        if (bbox.length === 4) {
          const [x1, y1, x2, y2] = bbox;
          const x = x1 * canvas.width;
          const y = y1 * canvas.height;
          const width = (x2 - x1) * canvas.width;
          const height = (y2 - y1) * canvas.height;
          
          // bbox 그리기
          ctx.strokeStyle = '#8B4513'; // 보라색
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, width, height);
          
          // 라벨 배경
          const label = `사람 ${index + 1} (${(person.confidence * 100).toFixed(1)}%)`;
          ctx.font = '16px Arial';
          const textWidth = ctx.measureText(label).width;
          ctx.fillStyle = '#8B4513';
          ctx.fillRect(x, y - 25, textWidth + 10, 25);
          
          // 라벨 텍스트
          ctx.fillStyle = '#FFFFFF';
          ctx.fillText(label, x + 5, y - 7);
        }
      });
    }
    
    // 객체 bbox 그리기
    if (frame.objects && frame.objects.length > 0) {
      frame.objects.forEach((obj, index) => {
        const bbox = obj.bbox || [];
        if (bbox.length === 4) {
          const [x1, y1, x2, y2] = bbox;
          const x = x1 * canvas.width;
          const y = y1 * canvas.height;
          const width = (x2 - x1) * canvas.width;
          const height = (y2 - y1) * canvas.height;
          
          // bbox 그리기
          ctx.strokeStyle = '#FF8C00'; // 주황색
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, width, height);
          
          // 라벨 배경
          const label = `${obj.class} (${(obj.confidence * 100).toFixed(1)}%)`;
          ctx.font = '16px Arial';
          const textWidth = ctx.measureText(label).width;
          ctx.fillStyle = '#FF8C00';
          ctx.fillRect(x, y - 25, textWidth + 10, 25);
          
          // 라벨 텍스트
          ctx.fillStyle = '#FFFFFF';
          ctx.fillText(label, x + 5, y - 7);
        }
      });
    }
  };

  // 비디오 목록 로드
  const loadVideoList = async () => {
    try {
      const response = await api.get('/api/video/list/');
      setVideoList(response.data.videos || []);
    } catch (error) {
      console.error('비디오 목록 로드 실패:', error);
    }
  };

  // 비디오 데이터 로드
  const loadVideoData = async (id) => {
    try {
      const response = await api.get(`/api/video/${id}/analysis/`);
      setSelectedVideo(response.data);
      setAnalysisStatus(response.data.analysis_status);
      
      if (response.data.analysis_status === 'pending') {
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
        
        // 진행률 정보 업데이트
        if (response.data.progress) {
          setAnalysisProgress(response.data.progress.analysis_progress || 0);
          setAnalysisMessage(response.data.progress.analysis_message || '');
        }
        
        if (response.data.analysis_status === 'completed') {
          clearInterval(interval);
          setAnalysisProgress(100);
          setAnalysisMessage('분석 완료');
          loadChatHistory(id);
          loadVideoList(); // 목록 새로고침
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
    }, 2000); // 2초마다 확인 (서버 부하 감소)
  };

  // 분석 시작하기
  const startAnalysis = async (videoId) => {
    try {
      setIsLoading(true);
      
      // 진행률 초기화
      setAnalysisProgress(0);
      setAnalysisMessage('분석을 시작합니다...');
      
      // 백엔드에 분석 시작 요청
      const response = await api.post(`/api/video/${videoId}/analysis/`);
      
      if (response.data.status === 'pending') {
        // 분석 상태를 pending으로 변경하고 폴링 시작
        setAnalysisStatus('pending');
        checkAnalysisStatus(videoId);
        loadVideoList(); // 목록 새로고침
        
        // 영상 목록으로 이동
        setShowVideoList(true);
        setSelectedVideo(null);
        navigate('/video-chat');
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

  // 파일 유효성 검사
  const validateFile = (file) => {
    // 파일 크기 제한 (50MB - 백엔드와 일치)
    if (file.size > 50 * 1024 * 1024) {
      alert(`파일 크기가 너무 큽니다. 최대 50MB까지 업로드 가능합니다. (현재: ${(file.size / (1024*1024)).toFixed(1)}MB)`);
      return false;
    }

    // 파일명 길이 제한 (200자)
    if (file.name.length > 200) {
      alert('파일명이 너무 깁니다. 200자 이하로 제한됩니다.');
      return false;
    }

    // 파일 형식 확인
    const allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/mkv', 'video/webm'];
    if (!allowedTypes.includes(file.type)) {
      alert('지원하지 않는 파일 형식입니다. MP4, AVI, MOV, MKV, WEBM 파일을 업로드해주세요.');
      return false;
    }

    return true;
  };

  // 파일 업로드 처리
  const processFileUpload = async (file) => {
    if (!validateFile(file)) return;

    setUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('video', file);
    formData.append('title', file.name);

    try {
      const response = await api.post('/api/video/upload/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        }
      });

      if (response.data.video_id) {
        // 업로드 성공 후 영상 목록으로 돌아가기
        alert('영상이 성공적으로 업로드되었습니다! 분석이 시작됩니다.');
        loadVideoList(); // 목록 새로고침
        // 채팅 페이지로 이동하지 않고 목록에 머물기
      }
    } catch (error) {
      console.error('영상 업로드 실패:', error);
      
      // 서버에서 반환된 오류 메시지 사용
      let errorMessage = '영상 업로드에 실패했습니다.';
      
      if (error.response && error.response.data && error.response.data.error) {
        errorMessage = error.response.data.error;
      } else if (error.message) {
        errorMessage = `업로드 오류: ${error.message}`;
      }
      
      alert(errorMessage);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  // 파일 업로드 (클릭)
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    await processFileUpload(file);
  };

  // 드래그 앤 드롭 이벤트 핸들러
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    // 첫 번째 파일만 처리
    const file = files[0];
    await processFileUpload(file);
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
      const response = await api.post(`/api/video/${selectedVideo.video_id}/chat/`, {
        message: inputMessage
      });

      if (response.data.ai_responses) {
        const aiMessages = [];
        
        // 개별 AI 응답들
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
        
        // 통합 응답
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
      console.error('메시지 전송 실패:', error);
      alert('메시지 전송에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // 비디오 선택
  const selectVideo = (video) => {
    setSelectedVideo(video);
    setShowVideoList(false);
    navigate(`/video-chat/${video.id}`);
    loadVideoData(video.id);
  };

  // 비디오 목록으로 돌아가기
  const backToVideoList = () => {
    setShowVideoList(true);
    setSelectedVideo(null);
    setMessages([]);
    navigate('/video-chat');
  };

  // 컴포넌트 마운트 시 초기화
  useEffect(() => {
    loadVideoList();
    if (videoId) {
      loadVideoData(videoId);
    }
  }, [videoId]);

  // 분석 상태에 따른 UI 렌더링
  const renderAnalysisStatus = () => {
    switch (analysisStatus) {
      case 'pending':
        return (
          <div className="flex flex-col items-center justify-center h-64 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
            <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
            <h3 className="text-xl font-semibold text-gray-700 mb-2">영상 분석 중</h3>
            <p className="text-gray-600 text-center mb-4 max-w-md">
              {analysisMessage || '영상을 분석하고 있습니다...'}
            </p>
            <div className="w-full max-w-sm mb-4">
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span className="font-medium">진행률</span>
                <span className="font-semibold text-blue-600">{analysisProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 shadow-inner">
                <div 
                  className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-500 ease-out shadow-sm" 
                  style={{ width: `${analysisProgress}%` }}
                ></div>
              </div>
            </div>
            <div className="flex items-center text-sm text-gray-500">
              <Clock className="w-4 h-4 mr-1" />
              <span>분석이 완료되면 자동으로 채팅이 시작됩니다</span>
            </div>
          </div>
        );
      case 'failed':
        return (
          <div className="flex flex-col items-center justify-center h-64 bg-gradient-to-br from-red-50 to-pink-50 rounded-lg border border-red-200">
            <XCircle className="w-12 h-12 text-red-500 mb-4" />
            <h3 className="text-xl font-semibold text-red-700 mb-2">분석 실패</h3>
            <div className="text-center mb-6 max-w-md">
              <p className="text-red-600 mb-2">
                {analysisMessage || '영상 분석에 실패했습니다.'}
              </p>
              <p className="text-sm text-gray-600">
                가능한 원인:
                <br />• 파일 형식이 지원되지 않음 (MP4, AVI, MOV, MKV, WEBM만 지원)
                <br />• 파일 크기가 너무 큼 (최대 50MB)
                <br />• 파일이 손상되었거나 읽을 수 없음
                <br />• 서버 처리 중 오류 발생
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => startAnalysis(selectedVideo?.id)}
                className="px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors flex items-center"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                다시 분석
              </button>
              <button
                onClick={backToVideoList}
                className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              >
                새 영상 업로드
              </button>
            </div>
          </div>
        );
      case 'completed':
        return null; // 채팅 인터페이스 표시
      default:
        return null; // 기본적으로는 아무것도 표시하지 않음
    }
  };

  // 비디오 목록 UI
  const renderVideoList = () => (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">영상 채팅</h1>
        <p className="text-gray-600">영상을 업로드하고 AI와 채팅해보세요</p>
      </div>

      {/* 업로드 영역 */}
      <div className="mb-8">
        <div 
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-all duration-300 ${
            isDragOver 
              ? 'border-blue-500 bg-blue-50 scale-105' 
              : uploading 
                ? 'border-gray-300 bg-gray-50' 
                : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept="video/*"
            onChange={handleFileUpload}
            className="hidden"
            id="video-upload"
            disabled={uploading}
          />
          <label
            htmlFor="video-upload"
            className={`flex flex-col items-center ${uploading ? 'cursor-not-allowed' : 'cursor-pointer'}`}
          >
            {uploading ? (
              <>
                <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
                <h3 className="text-lg font-semibold text-gray-700 mb-2">업로드 중...</h3>
                <div className="w-full max-w-xs bg-gray-200 rounded-full h-2 mb-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
                <p className="text-gray-500">{uploadProgress}% 완료</p>
              </>
            ) : (
              <>
                <Upload className={`w-12 h-12 mb-4 ${isDragOver ? 'text-blue-500' : 'text-gray-400'}`} />
                <h3 className={`text-lg font-semibold mb-2 ${isDragOver ? 'text-blue-600' : 'text-gray-700'}`}>
                  {isDragOver ? '영상을 여기에 놓으세요' : '영상 업로드'}
                </h3>
                <p className={`mb-4 ${isDragOver ? 'text-blue-500' : 'text-gray-500'}`}>
                  {isDragOver ? '마우스를 놓으면 업로드됩니다' : '클릭하거나 드래그하여 영상 파일을 선택하세요'}
                </p>
                <p className="text-sm text-gray-400">MP4, AVI, MOV, MKV, WEBM 지원 (최대 100MB)</p>
              </>
            )}
          </label>
        </div>
      </div>

      {/* 비디오 목록 */}
      {videoList.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold text-gray-800 mb-4">업로드된 영상</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {videoList.map((video) => (
              <div
                key={video.id}
                onClick={() => selectVideo(video)}
                className="bg-white rounded-lg shadow-md p-4 hover:shadow-lg transition-shadow cursor-pointer border"
              >
                <div className="flex items-center mb-3">
                  <FileVideo className="w-8 h-8 text-blue-500 mr-3" />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-gray-800 truncate">
                      {video.original_name}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {new Date(video.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center justify-between text-sm mb-3">
                  <span className="text-gray-500">
                    {(video.file_size / (1024 * 1024)).toFixed(1)}MB
                  </span>
                  <div className="flex items-center">
                    {video.analysis_status === 'completed' && (
                      <CheckCircle className="w-4 h-4 text-green-500 mr-1" />
                    )}
                    {video.analysis_status === 'pending' && (
                      <Clock className="w-4 h-4 text-yellow-500 mr-1" />
                    )}
                    {video.analysis_status === 'failed' && (
                      <XCircle className="w-4 h-4 text-red-500 mr-1" />
                    )}
                    <span className={`text-xs font-medium ${
                      video.analysis_status === 'completed' ? 'text-green-600' :
                      video.analysis_status === 'pending' ? 'text-yellow-600' :
                      'text-red-600'
                    }`}>
                      {video.analysis_status === 'completed' ? '분석 완료' :
                       video.analysis_status === 'pending' ? '분석 중' :
                       '분석 실패'}
                    </span>
                  </div>
                </div>
                
                {/* 액션 버튼들 */}
                <div className="flex gap-2">
                  {video.analysis_status === 'completed' && (
                    <button
                      onClick={() => selectVideo(video)}
                      className="flex-1 px-3 py-2 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600 transition-colors"
                    >
                      채팅하기
                    </button>
                  )}
                  {video.analysis_status === 'pending' && (
                    <div className="flex-1">
                      <button
                        disabled
                        className="w-full px-3 py-2 bg-gray-300 text-gray-500 text-sm rounded-lg cursor-not-allowed"
                      >
                        분석 중... ({video.analysis_progress || 0}%)
                      </button>
                      {video.analysis_message && (
                        <p className="text-xs text-gray-500 mt-1 text-center">
                          {video.analysis_message}
                        </p>
                      )}
                    </div>
                  )}
                  {video.analysis_status === 'failed' && (
                    <div className="flex-1">
                      <button
                        onClick={() => startAnalysis(video.id)}
                        className="w-full px-3 py-2 bg-yellow-500 text-white text-sm rounded-lg hover:bg-yellow-600 transition-colors"
                      >
                        다시 분석
                      </button>
                      {video.analysis_message && (
                        <p className="text-xs text-red-500 mt-1 text-center">
                          {video.analysis_message}
                        </p>
                      )}
                    </div>
                  )}
                  {(!video.analysis_status || video.analysis_status === 'uploaded') && (
                    <button
                      onClick={() => startAnalysis(video.id)}
                      className="flex-1 px-3 py-2 bg-green-500 text-white text-sm rounded-lg hover:bg-green-600 transition-colors"
                    >
                      분석 시작
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // Optimal Response Renderer Component (기본 채팅과 동일)
  const OptimalResponseRenderer = ({ content, relevantFrames }) => {
    const parseOptimalResponse = (text) => {
      if (!text || typeof text !== 'string') {
        return {};
      }
      
      const sections = {};
      const lines = text.split('\n');
      let currentSection = '';
      let currentContent = [];
      
      for (const line of lines) {
        if (line.startsWith('## 통합 답변') || line.startsWith('## 🎯 통합 답변')) {
          if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
          currentSection = 'integrated';
          currentContent = [];
        } else if (line.startsWith('## 각 AI 분석') || line.startsWith('## 📊 각 AI 분석')) {
          if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
          currentSection = 'analysis';
          currentContent = [];
        } else if (line.startsWith('## 분석 근거') || line.startsWith('## 🔍 분석 근거')) {
          if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
          currentSection = 'rationale';
          currentContent = [];
        } else if (line.startsWith('## 최종 추천') || line.startsWith('## 🏆 최종 추천')) {
          if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
          currentSection = 'recommendation';
          currentContent = [];
        } else if (line.startsWith('## 추가 인사이트') || line.startsWith('## 💡 추가 인사이트')) {
          if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
          currentSection = 'insights';
          currentContent = [];
        } else if (line.trim() !== '') {
          currentContent.push(line);
        }
      }
      
      if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
      return sections;
    };

    const parseAIAnalysis = (analysisText) => {
      const analyses = {};
      const lines = analysisText.split('\n');
      let currentAI = '';
      let currentAnalysis = { pros: [], cons: [] };
      
      for (const line of lines) {
        if (line.startsWith('### ')) {
          if (currentAI) {
            analyses[currentAI] = currentAnalysis;
          }
          currentAI = line.replace('### ', '').trim();
          currentAnalysis = { pros: [], cons: [] };
        } else if (line.includes('- 장점:')) {
          currentAnalysis.pros.push(line.replace('- 장점:', '').trim());
        } else if (line.includes('- 단점:')) {
          currentAnalysis.cons.push(line.replace('- 단점:', '').trim());
        }
      }
      
      if (currentAI) {
        analyses[currentAI] = currentAnalysis;
      }
      
      return analyses;
    };

    if (!content || typeof content !== 'string') {
      return (
        <div className="optimal-response-container">
          <div className="optimal-section integrated-answer">
            <h3 className="section-title">최적 답변</h3>
            <div className="section-content">최적의 답변을 생성 중입니다...</div>
          </div>
        </div>
      );
    }

    const sections = parseOptimalResponse(content);
    const analysisData = sections.analysis ? parseAIAnalysis(sections.analysis) : {};

    return (
      <div className="optimal-response-container">
        {sections.integrated && (
          <div className="optimal-section integrated-answer">
            <h3 className="section-title">최적 답변</h3>
            <div className="section-content">{sections.integrated}</div>
          </div>
        )}
        
        {sections.analysis && (
          <div className="optimal-section analysis-section">
            <h3 className="section-title">각 AI 분석</h3>
            <div className="analysis-grid">
              {Object.entries(analysisData).map(([aiName, analysis]) => (
                <div key={aiName} className="analysis-item">
                  <h4 className="analysis-ai-name">{aiName}</h4>
                  {analysis.pros.length > 0 && (
                    <div className="analysis-pros">
                      <strong>장점:</strong>
                      <ul>
                        {analysis.pros.map((pro, index) => (
                          <li key={index}>{pro}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {analysis.cons.length > 0 && (
                    <div className="analysis-cons">
                      <strong>단점:</strong>
                      <ul>
                        {analysis.cons.map((con, index) => (
                          <li key={index}>{con}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {sections.rationale && (
          <div className="optimal-section rationale-section">
            <h3 className="section-title">분석 근거</h3>
            <div className="section-content">{sections.rationale}</div>
          </div>
        )}
        
        {sections.recommendation && (
          <div className="optimal-section recommendation-section">
            <h3 className="section-title">최종 추천</h3>
            <div className="section-content">{sections.recommendation}</div>
          </div>
        )}
        
        {sections.insights && (
          <div className="optimal-section insights-section">
            <h3 className="section-title">추가 인사이트</h3>
            <div className="section-content">{sections.insights}</div>
          </div>
        )}

        {/* 관련 프레임 이미지 표시 */}
        {relevantFrames && relevantFrames.length > 0 && (
          <div className="optimal-section frames-section">
            <h3 className="section-title">📸 관련 프레임</h3>
            <div className="frames-grid">
              {relevantFrames.map((frame, index) => (
                <div key={index} className="frame-card">
                  <div className="frame-info">
                    <span className="frame-timestamp">⏰ {frame.timestamp.toFixed(1)}초</span>
                    <span className="frame-score">🎯 {frame.relevance_score}점</span>
                  </div>
                  <img
                    src={`${api.defaults.baseURL}${frame.image_url}`}
                    alt={`프레임 ${frame.image_id}`}
                    className="frame-image"
                    onError={(e) => {
                      console.error(`프레임 이미지 로드 실패: ${frame.image_url}`);
                      e.target.style.display = 'none';
                    }}
                  />
                  <div className="frame-tags">
                    {frame.persons && frame.persons.length > 0 && (
                      <span className="frame-tag person-tag">
                        👤 사람 {frame.persons.length}명
                      </span>
                    )}
                    {frame.objects && frame.objects.length > 0 && (
                      <span className="frame-tag object-tag">
                        📦 객체 {frame.objects.length}개
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  // 채팅 인터페이스 UI (기본 채팅과 동일한 구조)
  const renderChatInterface = () => (
    <div className="min-h-screen bg-gray-50">
      <style jsx>{`
        .chat-header {
          background: rgba(245, 242, 234, 0.4);
          backdrop-filter: blur(10px);
          border-bottom: 1px solid rgba(139, 168, 138, 0.15);
          height: 60px;
        }
        .chat-column {
          background: rgba(255, 255, 255, 0.3);
          backdrop-filter: blur(5px);
          min-height: 0; /* flexbox에서 스크롤이 작동하도록 */
        }
        .chat-container {
          height: calc(100vh - 200px); /* 상단 영역을 제외한 가시 높이 */
          min-height: 0; /* flexbox에서 스크롤이 작동하도록 */
        }
        .chat-column .overflow-y-auto {
          scrollbar-width: thin;
          scrollbar-color: rgba(139, 168, 138, 0.3) transparent;
        }
        .chat-column .overflow-y-auto::-webkit-scrollbar {
          width: 6px;
        }
        .chat-column .overflow-y-auto::-webkit-scrollbar-track {
          background: transparent;
        }
        .chat-column .overflow-y-auto::-webkit-scrollbar-thumb {
          background: rgba(139, 168, 138, 0.3);
          border-radius: 3px;
        }
        .chat-column .overflow-y-auto::-webkit-scrollbar-thumb:hover {
          background: rgba(139, 168, 138, 0.5);
        }
        .aiofai-input-area {
          background: rgba(245, 242, 234, 0.4);
          backdrop-filter: blur(10px);
          border-top: 1px solid rgba(139, 168, 138, 0.15);
          padding: 0.75rem 1.2rem;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 0.3rem;
          position: sticky; /* 하단에 고정 */
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
          position: relative;
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
          position: relative;
        }
        .optimal-response {
          background: rgba(255, 255, 255, 0.95) !important;
          border: 2px solid rgba(139, 168, 138, 0.3) !important;
          padding: 1.5rem !important;
          border-radius: 16px !important;
          max-width: 95% !important;
          box-shadow: 0 8px 32px rgba(139, 168, 138, 0.15) !important;
        }
        .optimal-response-container {
          width: 100%;
        }
        .optimal-section {
          margin-bottom: 1.5rem;
          padding: 1rem;
          border-bottom: 1px solid #e5e7eb;
        }
        .optimal-section:last-child {
          margin-bottom: 0;
          border-bottom: none;
        }
        .section-title {
          margin: 0 0 1rem 0;
          font-size: 1rem;
          font-weight: 600;
          color: #374151;
          text-transform: uppercase;
          letter-spacing: 0.05em;
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
        .analysis-pros, .analysis-cons {
          margin-bottom: 0.5rem;
        }
        .analysis-pros ul, .analysis-cons ul {
          margin: 0.25rem 0 0 1rem;
          padding: 0;
        }
        .analysis-pros li, .analysis-cons li {
          margin-bottom: 0.25rem;
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
          flex-wrap: wrap;
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

      {/* 메시지 영역 - 여러 컬럼 구조 (기본 채팅과 동일) */}
      <div className="chat-container flex overflow-hidden h-full">
        {['gpt', 'claude', 'mixtral', 'optimal'].map((modelId) => (
          <div key={modelId} className="border-r flex-1 flex flex-col chat-column">
            {/* 헤더 */}
            <div className="flex-shrink-0 px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
              <div className="text-center text-sm font-medium text-gray-600 flex-1">
                {modelId === 'optimal' ? '🤖 통합 응답' : `🤖 ${modelId.toUpperCase()}`}
              </div>
              {/* 스크롤 버튼 */}
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
            
            {/* 스크롤 가능한 메시지 영역 */}
            <div className="flex-1 overflow-y-auto px-4 py-3" style={{ height: 'calc(100vh - 260px)' }}>
              
              {messages.map((message, index) => {
                const isUser = message.type === 'user';
                const isOptimal = modelId === 'optimal' && message.type === 'ai_optimal';
                const isModelMessage = modelId !== 'optimal' && message.ai_model === modelId;
                
                if (!isUser && !isOptimal && !isModelMessage) return null;
                
                return (
                  <div key={`${modelId}-${index}`} className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
                    <div className={`${isUser ? "aiofai-user-message" : "aiofai-bot-message"} ${isOptimal ? "optimal-response" : ""}`}>
                      {isOptimal ? (
                        <OptimalResponseRenderer 
                          content={message.content} 
                          relevantFrames={message.relevant_frames}
                        />
                      ) : (
                        <div>
                          <div className="whitespace-pre-wrap">{message.content}</div>
                          
                          {/* 관련 프레임 이미지 표시 (개선된 UI) */}
                          {message.relevant_frames && message.relevant_frames.length > 0 && (
                            <div className="mt-4">
                              <div className="flex items-center mb-3">
                                <div className="text-sm font-semibold text-gray-700 flex items-center">
                                  <svg className="w-4 h-4 mr-2 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                  </svg>
                                  관련 프레임 ({message.relevant_frames.length}개)
                                </div>
                              </div>
                              <div className="grid grid-cols-1 gap-3">
                                {message.relevant_frames.map((frame, frameIndex) => (
                                  <div 
                                    key={frameIndex} 
                                    className="group relative bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-lg hover:border-blue-300 transition-all duration-300 cursor-pointer"
                                    onClick={() => {
                                      setSelectedFrame(frame);
                                      setIsFrameModalOpen(true);
                                    }}
                                  >
                                    {/* 이미지 */}
                                    <div className="relative">
                                      <img
                                        src={`${api.defaults.baseURL}${frame.image_url}`}
                                        alt={`프레임 ${frame.image_id}`}
                                        className="w-full h-32 object-cover group-hover:scale-105 transition-transform duration-300"
                                        onError={(e) => {
                                          console.error(`프레임 이미지 로드 실패: ${frame.image_url}`);
                                          e.target.style.display = 'none';
                                        }}
                                      />
                                      {/* 호버 오버레이 */}
                                      <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-300 flex items-center justify-center">
                                        <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                                          <div className="bg-white rounded-full p-2 shadow-lg">
                                            <svg className="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                                            </svg>
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                    
                                    {/* 정보 패널 */}
                                    <div className="p-3">
                                      <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center space-x-2">
                                          <div className="flex items-center bg-blue-50 text-blue-700 px-2 py-1 rounded-full text-xs font-medium">
                                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            {frame.timestamp.toFixed(1)}초
                                          </div>
                                          <div className="flex items-center bg-green-50 text-green-700 px-2 py-1 rounded-full text-xs font-medium">
                                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            {frame.relevance_score}점
                                          </div>
                                        </div>
                                        <div className="text-xs text-gray-500">
                                          프레임 #{frame.image_id}
                                        </div>
                                      </div>
                                      
                                      {/* 감지된 객체 정보 */}
                                      {frame.persons && frame.persons.length > 0 && (
                                        <div className="flex items-center space-x-2">
                                          <div className="flex items-center bg-purple-50 text-purple-700 px-2 py-1 rounded-full text-xs font-medium">
                                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                            </svg>
                                            사람 {frame.persons.length}명
                                          </div>
                                          {frame.objects && frame.objects.length > 0 && (
                                            <div className="flex items-center bg-orange-50 text-orange-700 px-2 py-1 rounded-full text-xs font-medium">
                                              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                                              </svg>
                                              객체 {frame.objects.length}개
                                            </div>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          
                          <div className="text-xs opacity-60 mt-2">
                            {new Date(message.created_at).toLocaleTimeString()}
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
              {/* 각 모델별 스크롤 끝점 */}
              <div ref={(el) => { scrollRefs.current[modelId] = el; }} />
            </div>
          </div>
        ))}
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
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {showVideoList ? (
        renderVideoList()
      ) : analysisStatus === 'completed' ? (
        renderChatInterface()
      ) : (
        <div className="max-w-2xl mx-auto p-6">
          {renderAnalysisStatus()}
        </div>
      )}
      
      {/* 프레임 이미지 모달 */}
      {isFrameModalOpen && selectedFrame && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-4xl max-h-[90vh] overflow-hidden shadow-2xl">
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between p-4 border-b bg-gray-50">
              <div className="flex items-center space-x-3">
                <div className="flex items-center bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm font-medium">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {selectedFrame.timestamp.toFixed(1)}초
                </div>
                <div className="flex items-center bg-green-50 text-green-700 px-3 py-1 rounded-full text-sm font-medium">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {selectedFrame.relevance_score}점
                </div>
                <div className="text-sm text-gray-600">
                  프레임 #{selectedFrame.image_id}
                </div>
              </div>
              <button
                onClick={() => setIsFrameModalOpen(false)}
                className="p-2 hover:bg-gray-200 rounded-full transition-colors"
              >
                <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            {/* 모달 내용 */}
            <div className="p-6">
              <div className="flex flex-col lg:flex-row gap-6">
                {/* 이미지 */}
                <div className="flex-1">
                  <div className="relative">
                    {/* bbox 오버레이 토글 버튼 */}
                    <div className="absolute top-2 right-2 z-10 flex gap-2">
                      <button
                        onClick={() => setShowBboxOverlay(!showBboxOverlay)}
                        className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                          showBboxOverlay
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                      >
                        {showBboxOverlay ? '🎯 bbox ON' : '🎯 bbox OFF'}
                      </button>
                    </div>
                    
                    {showBboxOverlay ? (
                      <canvas
                        ref={canvasRef}
                        className="w-full h-auto max-h-[60vh] object-contain rounded-lg shadow-lg"
                      />
                    ) : (
                      <img
                        src={`${api.defaults.baseURL}${selectedFrame.image_url}`}
                        alt={`프레임 ${selectedFrame.image_id}`}
                        className="w-full h-auto max-h-[60vh] object-contain rounded-lg shadow-lg"
                        onError={(e) => {
                          console.error(`프레임 이미지 로드 실패: ${selectedFrame.image_url}`);
                          e.target.style.display = 'none';
                        }}
                      />
                    )}
                    
                    {/* 숨겨진 이미지 (캔버스 그리기용) */}
                    <img
                      id="modal-frame-image"
                      src={`${api.defaults.baseURL}${selectedFrame.image_url}`}
                      alt={`프레임 ${selectedFrame.image_id}`}
                      style={{ display: 'none' }}
                      onLoad={(e) => {
                        if (showBboxOverlay) {
                          drawBboxOnCanvas(e.target, selectedFrame);
                        }
                      }}
                      onError={(e) => {
                        console.error(`프레임 이미지 로드 실패: ${selectedFrame.image_url}`);
                      }}
                    />
                  </div>
                </div>
                
                {/* 정보 패널 */}
                <div className="lg:w-80 space-y-4">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800 mb-3">프레임 정보</h3>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-gray-600">타임스탬프:</span>
                        <span className="font-medium">{selectedFrame.timestamp.toFixed(1)}초</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">관련도 점수:</span>
                        <span className="font-medium text-green-600">{selectedFrame.relevance_score}점</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">프레임 ID:</span>
                        <span className="font-medium">#{selectedFrame.image_id}</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* 감지된 객체 상세 정보 */}
                  {selectedFrame.persons && selectedFrame.persons.length > 0 && (
                    <div>
                      <h4 className="text-md font-semibold text-gray-800 mb-2 flex items-center">
                        <svg className="w-4 h-4 mr-2 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        감지된 사람 ({selectedFrame.persons.length}명)
                      </h4>
                      <div className="space-y-2">
                        {selectedFrame.persons.map((person, index) => (
                          <div key={index} className="bg-purple-50 rounded-lg p-3">
                            <div className="flex justify-between items-center mb-2">
                              <span className="text-sm font-medium text-purple-800">사람 {index + 1}</span>
                              <span className="text-xs bg-purple-200 text-purple-800 px-2 py-1 rounded-full">
                                신뢰도 {(person.confidence * 100).toFixed(1)}%
                              </span>
                            </div>
                            {person.attributes && (
                              <div className="text-xs text-gray-600 space-y-1">
                                {person.attributes.gender && (
                                  <div>성별: {person.attributes.gender.value}</div>
                                )}
                                {person.attributes.age && (
                                  <div>나이: {person.attributes.age.value}</div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {selectedFrame.objects && selectedFrame.objects.length > 0 && (
                    <div>
                      <h4 className="text-md font-semibold text-gray-800 mb-2 flex items-center">
                        <svg className="w-4 h-4 mr-2 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                        </svg>
                        감지된 객체 ({selectedFrame.objects.length}개)
                      </h4>
                      <div className="space-y-2">
                        {selectedFrame.objects.map((obj, index) => (
                          <div key={index} className="bg-orange-50 rounded-lg p-3">
                            <div className="flex justify-between items-center">
                              <span className="text-sm font-medium text-orange-800">{obj.class}</span>
                              <span className="text-xs bg-orange-200 text-orange-800 px-2 py-1 rounded-full">
                                신뢰도 {(obj.confidence * 100).toFixed(1)}%
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoChatPage;