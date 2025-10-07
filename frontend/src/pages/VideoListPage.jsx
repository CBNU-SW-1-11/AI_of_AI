import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, Loader2, CheckCircle, XCircle, Clock, FileVideo, RefreshCw, EllipsisVertical, Pencil, Trash2 } from 'lucide-react';
import { api } from '../utils/api';

const BRAND = '#5d7c5b';
const BRAND_BASE = '#8ba88a';            // 버튼 기본색
const BRAND_HOVER = '#5d7c5b';           // 버튼 hover
const BRAND_TINT_BG = 'rgba(139, 168, 138, 0.05)';   // 드롭존 hover 배경
const BRAND_TINT_BORDER = 'rgba(139, 168, 138, 0.4)';// 드롭존 hover 보더
const NEUTRAL_BORDER = '#e5e7eb';
const showToast = (message, type = 'success') => {
    try {
      const toast = document.createElement('div');
      const isSuccess = type === 'success';
      const bg = isSuccess ? '#16a34a' : '#ef4444';   // green-600 / red-500
      const iconPath = isSuccess
        ? 'M5 13l4 4L19 7'                            // check
        : 'M6 18L18 6M6 6l12 12';                    // x
  
      toast.className =
        'fixed top-4 right-4 text-white px-6 py-3 rounded-lg shadow-lg z-[9999] flex items-center max-w-md';
      toast.style.backgroundColor = bg;
      toast.innerHTML = `
        <svg class="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${iconPath}"></path>
        </svg>
        <span>${message}</span>
      `;
      document.body.appendChild(toast);
  
      setTimeout(() => {
        try { toast.remove(); } catch {}
      }, isSuccess ? 3000 : 5000);
    } catch {
      // DOM 사용 불가 환경 대비 폴백
      alert(message);
    }
  };
const VideoListPage = () => {
  const navigate = useNavigate();
  
  const [videoList, setVideoList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isHover, setIsHover] = useState(false);
const [menuOpenId, setMenuOpenId] = useState(null);
const menuRef = React.useRef(null);

// 바깥 클릭으로 메뉴 닫기
useEffect(() => {
  const onDocClick = (e) => {
    if (!menuRef.current) return;
    if (!menuRef.current.contains(e.target)) {
      setMenuOpenId(null);
    }
  };
  document.addEventListener('mousedown', onDocClick);
  return () => document.removeEventListener('mousedown', onDocClick);
}, []);

// 이름 수정
const handleRename = async (video) => {
    const current = video.original_name || '';
    const newName = window.prompt('새 이름을 입력하세요', current);
    if (!newName || newName.trim() === '' || newName === current) {
      setMenuOpenId(null);
      return;
    }
    
    try {
      await api.post(`/api/video/${video.id}/rename/`, { original_name: newName.trim() });
      showToast('이름이 변경되었습니다.', 'success');
      await loadVideoList();
    } catch (err) {
      console.error('이름 변경 실패:', err);
      const errorMsg = err?.response?.data?.error || err?.response?.data?.message || err?.message || '이름 변경에 실패했습니다.';
      showToast(errorMsg, 'error');
    } finally {
      setMenuOpenId(null);
    }
  };

// 영상 삭제
const handleDelete = async (video) => {
    if (!window.confirm('정말로 이 영상을 삭제하시겠습니까? 되돌릴 수 없습니다.')) {
      setMenuOpenId(null);
      return;
    }
    
    try {
      await api.delete(`/api/video/${video.id}/delete/`);
      showToast('영상이 삭제되었습니다.', 'success');
      await loadVideoList();
    } catch (err) {
      console.error('영상 삭제 실패:', err);
      const errorMsg = err?.response?.data?.error || err?.response?.data?.message || err?.message || '영상 삭제에 실패했습니다.';
      showToast(errorMsg, 'error');
    } finally {
      setMenuOpenId(null);
    }
  };
  const loadVideoList = async () => {
    try {
      console.log('비디오 목록 로드 시작...');
      const response = await api.get('/api/video/list/');
      console.log('비디오 목록 응답:', response.data);
      setVideoList(response.data.videos || []);
    } catch (error) {
      console.error('비디오 목록 로드 실패:', error);
      
      // 더 자세한 에러 정보 표시
      let errorMessage = '비디오 목록을 불러오는데 실패했습니다.';
      
      if (error.code === 'ECONNABORTED') {
        errorMessage = '요청 시간이 초과되었습니다. 서버가 응답하지 않습니다.';
      } else if (error.response) {
        // 서버가 응답했지만 에러 상태 코드
        errorMessage = `서버 오류 (${error.response.status}): ${error.response.data?.message || error.response.statusText}`;
      } else if (error.request) {
        // 요청이 전송되었지만 응답을 받지 못함
        errorMessage = '서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.';
      } else {
        // 요청 설정 중 오류
        errorMessage = `요청 오류: ${error.message}`;
      }
      
      // 에러 토스트 표시
      const errorToast = document.createElement('div');
      errorToast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center max-w-md';
      errorToast.innerHTML = `
        <svg class="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
        <span>${errorMessage}</span>
      `;
      document.body.appendChild(errorToast);
      setTimeout(() => errorToast.remove(), 8000);
    }
  };
  // 분석 시작하기
  const startAnalysis = async (videoId) => {
    try {
      const response = await api.post(`/api/video/${videoId}/analysis/`);
      
      if (response.data.status === 'pending') {
        loadVideoList();
        
        const successToast = document.createElement('div');
        successToast.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center';
        successToast.innerHTML = `
          <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
          </svg>
          분석이 시작되었습니다.
        `;
        document.body.appendChild(successToast);
        setTimeout(() => successToast.remove(), 3000);
      }
    } catch (error) {
      console.error('분석 시작 실패:', error);
      
      const errorToast = document.createElement('div');
      errorToast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center';
      errorToast.innerHTML = `
        <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
        분석 시작에 실패했습니다.
      `;
      document.body.appendChild(errorToast);
      setTimeout(() => errorToast.remove(), 5000);
    }
  };

  // 파일 유효성 검사
  const validateFile = (file) => {
    if (file.size > 50 * 1024 * 1024) {
      const errorToast = document.createElement('div');
      errorToast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center max-w-md';
      errorToast.innerHTML = `
        <svg class="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
        </svg>
        <span>파일 크기가 너무 큽니다. 최대 50MB까지 업로드 가능합니다. (현재: ${(file.size / (1024*1024)).toFixed(1)}MB)</span>
      `;
      document.body.appendChild(errorToast);
      setTimeout(() => errorToast.remove(), 5000);
      return false;
    }

    if (file.name.length > 200) {
      const errorToast = document.createElement('div');
      errorToast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center';
      errorToast.innerHTML = `
        <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
        </svg>
        파일명이 너무 깁니다. 200자 이하로 제한됩니다.
      `;
      document.body.appendChild(errorToast);
      setTimeout(() => errorToast.remove(), 5000);
      return false;
    }

    const allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/mkv', 'video/webm'];
    if (!allowedTypes.includes(file.type)) {
      const errorToast = document.createElement('div');
      errorToast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center max-w-md';
      errorToast.innerHTML = `
        <svg class="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
        </svg>
        <span>지원하지 않는 파일 형식입니다. MP4, AVI, MOV, MKV, WEBM 파일을 업로드해주세요.</span>
      `;
      document.body.appendChild(errorToast);
      setTimeout(() => errorToast.remove(), 5000);
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
        const successMessage = document.createElement('div');
        successMessage.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center';
        successMessage.innerHTML = `
          <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
          </svg>
          영상 업로드 완료! 분석이 시작됩니다.
        `;
        document.body.appendChild(successMessage);
        setTimeout(() => successMessage.remove(), 3000);
        
        loadVideoList();
      }
    } catch (error) {
      console.error('영상 업로드 실패:', error);
      
      let errorMessage = '영상 업로드에 실패했습니다.';
      if (error.response?.data?.error) {
        errorMessage = error.response.data.error;
      } else if (error.message) {
        errorMessage = `업로드 오류: ${error.message}`;
      }
      
      const errorToast = document.createElement('div');
      errorToast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 flex items-center max-w-md';
      errorToast.innerHTML = `
        <svg class="w-5 h-5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
        <span>${errorMessage}</span>
      `;
      document.body.appendChild(errorToast);
      setTimeout(() => errorToast.remove(), 5000);
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

    const file = files[0];
    await processFileUpload(file);
  };

  // 비디오 선택
  const selectVideo = (video) => {
    navigate(`/video-chat/${video.id}`);
  };

  // 컴포넌트 마운트 시 초기화
  useEffect(() => {
    loadVideoList();
  }, []);

  // 주기적으로 영상 목록 업데이트 (분석 중인 영상이 있을 때)
  useEffect(() => {
    const hasAnalyzingVideos = videoList.some(video => 
      video.analysis_status === 'pending' || 
      video.analysis_status === 'analyzing' || 
      video.analysis_status === 'uploaded'
    );

    if (hasAnalyzingVideos) {
      const interval = setInterval(() => {
        loadVideoList();
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [videoList]);

  // 드롭존 hover/dragover 스타일 (파란색 → 연그린)
  const dropzoneStyle = (() => {
    if (uploading) return { borderColor: '#d1d5db', backgroundColor: '#f9fafb' };
    if (isHover || isDragOver) return { borderColor: BRAND_TINT_BORDER, backgroundColor: BRAND_TINT_BG };
    return { borderColor: NEUTRAL_BORDER, backgroundColor: 'white' };
  })();
  const dropzoneTextColor = (isHover || isDragOver) ? BRAND : '#374151';

  return (
    <div className="min-h-screen" style={{ background: "rgba(245, 242, 234, 0.4)" }}>
      <div className="max-w-4xl mx-auto p-6">
        <div className="mb-6">
          <h1 className="text-3xl font-bold mb-2" style={{ color: BRAND }}>영상 채팅</h1>
          <p className="text-gray-600">영상을 업로드하고 AI와 채팅해보세요</p>
        </div>

        <div className="mb-8">
          <div
            className="border-2 border-dashed rounded-lg p-8 text-center transition-all duration-300"
            style={{
              ...dropzoneStyle,
              transform: (isHover || isDragOver) ? 'scale(1.02)' : 'scale(1.0)'
            }}
            onMouseEnter={() => setIsHover(true)}
            onMouseLeave={() => setIsHover(false)}
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
                <div className="relative mb-6">
                  <div
                    className="w-16 h-16 rounded-full flex items-center justify-center shadow-lg"
                    style={{ backgroundColor: BRAND_TINT_BG, border: `2px solid ${BRAND_TINT_BORDER}` }}
                  >
                    <Upload className="w-8 h-8 animate-bounce" style={{ color: BRAND }} />
                  </div>
                  <div
                    className="absolute inset-0 w-16 h-16 rounded-full animate-ping opacity-20"
                    style={{ backgroundColor: BRAND_TINT_BG }}
                  />
                </div>
              
                <h3 className="text-xl font-bold text-gray-800 mb-4">영상 업로드 중</h3>
              
                <div className="bg-white/80 backdrop-blur-sm rounded-xl p-6 mb-4 shadow-md max-w-sm w-full">
                  <div className="text-center mb-4">
                    <p className="text-gray-700 font-medium mb-2">파일을 서버에 전송하고 있습니다...</p>
                    <div className="flex items-center justify-center text-sm text-gray-500">
                      <Clock className="w-4 h-4 mr-1" />
                      <span>잠시만 기다려주세요</span>
                    </div>
                  </div>
              
                  <div className="mb-4">
                    <div className="flex justify-between text-sm text-gray-600 mb-2">
                      <span className="font-medium">업로드 진행률</span>
                      <span className="font-bold" style={{ color: BRAND }}>{uploadProgress}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-4 shadow-inner">
                      <div
                        className="h-4 rounded-full transition-all duration-500 ease-out shadow-sm relative overflow-hidden"
                        style={{ width: `${uploadProgress}%`, backgroundColor: BRAND }}
                      >
                        <div
                          className="absolute inset-0 opacity-30 animate-pulse"
                          style={{
                            background:
                              'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,1) 50%, rgba(255,255,255,0) 100%)'
                          }}
                        />
                      </div>
                    </div>
                  </div>
              
                  <div className="space-y-2">
                    <div className={`flex items-center text-sm ${uploadProgress >= 25 ? 'text-green-600' : 'text-gray-400'}`}>
                      <div className={`w-2 h-2 rounded-full mr-2 ${uploadProgress >= 25 ? 'bg-green-500' : 'bg-gray-300'}`} />
                      파일 검증 중...
                    </div>
                    <div className={`flex items-center text-sm ${uploadProgress >= 50 ? 'text-green-600' : 'text-gray-400'}`}>
                      <div className={`w-2 h-2 rounded-full mr-2 ${uploadProgress >= 50 ? 'bg-green-500' : 'bg-gray-300'}`} />
                      서버로 전송 중...
                    </div>
                    <div className={`flex items-center text-sm ${uploadProgress >= 90 ? 'text-green-600' : 'text-gray-400'}`}>
                      <div className={`w-2 h-2 rounded-full mr-2 ${uploadProgress >= 90 ? 'bg-green-500' : 'bg-gray-300'}`} />
                      저장 완료!
                    </div>
                  </div>
                </div>
              
                <div className="text-center">
                  <div className="rounded-lg p-3 mb-2" style={{ backgroundColor: `${BRAND_TINT_BG}` }}>
                    <p className="text-sm font-medium" style={{ color: BRAND }}>
                      업로드 완료 후 자동으로 분석이 시작됩니다
                    </p>
                  </div>
                  <p className="text-xs text-gray-500">파일 크기에 따라 업로드 시간이 달라질 수 있습니다</p>
                </div>
              </>
              ) : (
                <>
                  <Upload className="w-12 h-12 mb-4" style={{ color: dropzoneTextColor }} />
                  <h3 className="text-lg font-semibold mb-2" style={{ color: dropzoneTextColor }}>
                    {isDragOver ? '영상을 여기에 놓으세요' : '영상 업로드'}
                  </h3>
                  <p className="mb-4" style={{ color: (isHover || isDragOver) ? BRAND : '#6b7280' }}>
                    {isDragOver ? '마우스를 놓으면 업로드됩니다' : '클릭하거나 드래그하여 영상 파일을 선택하세요'}
                  </p>
                  <p className="text-sm text-gray-400">MP4, AVI, MOV, MKV, WEBM 지원 (최대 50MB)</p>
                </>
              )}
            </label>
          </div>
        </div>

        {/* 비디오 목록 */}
        {videoList.length > 0 && (
          <div>
            <h2 className="text-xl font-semibold mb-4" style={{ color: BRAND }}>업로드된 영상</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {videoList.map((video) => (
                <div
                  key={video.id}
                  className="relative bg-white rounded-lg shadow-md p-4 hover:shadow-lg transition-shadow border"
                >
                  <div className="flex items-start mb-3 pr-10">
                    <FileVideo className="w-8 h-8 mr-3 flex-shrink-0 mt-0.5" style={{ color: BRAND }} />
                    <div className="flex-1 min-w-0 overflow-hidden">
                        <h3 className="font-medium text-gray-800 truncate block">
                        {video.original_name}
                        </h3>
                        <p className="text-sm text-gray-500">
                        {new Date(video.uploaded_at).toLocaleDateString()}
                        </p>
                    </div>
                    </div>
                  {/* 더보기 (…) 버튼 */}
                <button
                type="button"
                aria-label="더보기"
                className="absolute top-3 right-3 p-2 rounded-md hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-200"
                onClick={(e) => {
                    e.stopPropagation();
                    setMenuOpenId(menuOpenId === video.id ? null : video.id);
                }}
                >
                <EllipsisVertical className="w-5 h-5" style={{ color: '#6b7280' }} />
                </button>

                {/* 드롭다운 메뉴 */}
                {menuOpenId === video.id && (
                <div
                    ref={menuRef}
                    className="absolute top-10 right-3 w-44 bg-white border border-gray-200 rounded-lg shadow-lg z-20 overflow-hidden"
                    onClick={(e) => e.stopPropagation()}
                    role="menu"
                >
                    <button
                    className="w-full px-3 py-2 text-left text-sm hover:bg-black-50 flex items-center gap-2"
                    onClick={() => handleRename(video)}
                    role="menuitem"
                    >
                    <Pencil className="w-4 h-4 text-black-600" />
                    <span>이름 수정</span>
                    </button>
                    <button
                    className="w-full px-3 py-2 text-left text-sm hover:bg-black-50 flex items-center gap-2"
                    onClick={() => handleDelete(video)}
                    role="menuitem"
                    >
                    <Trash2 className="w-4 h-4 text-black-600" />
                    <span>영상 삭제</span>
                    </button>
                </div>
                )}
                  <div className="flex items-center justify-between text-sm mb-3">
                    <span className="text-gray-500">
                      {(video.file_size / (1024 * 1024)).toFixed(1)}MB
                    </span>
                    <div className="flex items-center">
                      {video.analysis_status === 'completed' && (
                        <div className="flex items-center bg-green-50 text-green-700 px-2 py-1 rounded-full text-xs font-medium">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          분석 완료
                        </div>
                      )}
                      {(video.analysis_status === 'pending' || video.analysis_status === 'analyzing') && (
                        <div className="flex items-center bg-gray-50 text-gray-700 px-2 py-1 rounded-full text-xs font-medium">
                          <Clock className="w-3 h-3 mr-1 animate-pulse" />
                          분석 중 ({video.analysis_progress || 0}%)
                        </div>
                      )}
                      {video.analysis_status === 'failed' && (
                        <div className="flex items-center bg-red-50 text-red-700 px-2 py-1 rounded-full text-xs font-medium">
                          <XCircle className="w-3 h-3 mr-1" />
                          분석 실패
                        </div>
                      )}
                      {(!video.analysis_status || video.analysis_status === 'uploaded') && (
                        <div className="flex items-center bg-gray-50 text-gray-700 px-2 py-1 rounded-full text-xs font-medium">
                          <FileVideo className="w-3 h-3 mr-1" />
                          업로드 완료
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* 액션 버튼들 */}
                  <div className="flex gap-2">
                    {video.analysis_status === 'completed' && (
                      <button
                        onClick={() => selectVideo(video)}
                        className="flex-1 px-6 py-3 rounded-lg transition-colors font-bold text-white"
                        style={{ backgroundColor: BRAND_BASE }}
                        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = BRAND_HOVER; }}
                        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = BRAND_BASE; }}
                      >
                        채팅하기
                      </button>
                    )}

                    {(video.analysis_status === 'pending' || video.analysis_status === 'analyzing') && (
                      <div className="flex-1">
                        <button
                          disabled
                          className="w-full px-4 py-2 bg-gray-500/90 text-white text-sm rounded-lg cursor-not-allowed flex items-center justify-center"
                        >
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          분석 중... ({video.analysis_progress || 0}%)
                        </button>
                        {video.analysis_message && (
                          <div className="mt-2 p-2 bg-gray-50 rounded-lg">
                            <p className="text-xs text-gray-700 text-center">
                              {video.analysis_message}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {video.analysis_status === 'failed' && (
                      <div className="flex-1">
                        <button
                          onClick={() => startAnalysis(video.id)}
                          className="w-full px-4 py-2 bg-gradient-to-r from-gray-500 to-orange-500 text-white text-sm rounded-lg hover:from-gray-600 hover:to-orange-600 transition-all duration-200 shadow-md hover:shadow-lg flex items-center justify-center"
                        >
                          <RefreshCw className="w-4 h-4 mr-2" />
                          다시 분석
                        </button>
                        {video.analysis_message && (
                          <div className="mt-2 p-2 bg-red-50 rounded-lg">
                            <p className="text-xs text-red-600 text-center">
                              {video.analysis_message}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {(!video.analysis_status || video.analysis_status === 'uploaded') && (
                      <button
                        onClick={() => startAnalysis(video.id)}
                        className="flex-1 px-4 py-2 bg-green-500 text-white text-sm rounded-lg hover:bg-green-600 transition-colors"
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
    </div>
  );
};

export default VideoListPage;