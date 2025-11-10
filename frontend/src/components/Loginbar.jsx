import React, { useCallback } from 'react';
import { X } from 'lucide-react';
import { useDispatch } from 'react-redux';
import { loginSuccess } from '../store/authSlice';

const Loginbar = ({ onClose }) => {
  const dispatch = useDispatch();
  
  // 쿼리스트링 빌더
  const buildQuery = (obj) =>
    Object.entries(obj)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&');

  // 구글 토큰 처리 함수
  const handleGoogleToken = useCallback(async (accessToken) => {
    try {
      const response = await fetch('http://localhost:8000/api/auth/google/callback/', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        // credentials 제거하여 CORS 문제 해결
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('구글 로그인 성공:', data);
        
        // Redux store에 사용자 정보 저장
        dispatch(loginSuccess(data.user));
        
        // 로컬 스토리지에도 저장
        localStorage.setItem('user', JSON.stringify(data.user));
        
        onClose(); // 로그인 바 닫기
      } else {
        const errorData = await response.json();
        console.error('로그인 실패:', errorData);
        throw new Error(errorData.error || '로그인 실패');
      }
    } catch (error) {
      console.error('구글 로그인 처리 오류:', error);
      alert('구글 로그인 중 오류가 발생했습니다: ' + error.message);
    }
  }, [onClose]);

  // ✅ 구글: 직접 OAuth URL 방식 (더 안정적)
  const handleGoogleLogin = useCallback(() => {
    const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID || '94821981810-32iorb0jccvsdi4jq3pp3mc6rvmb0big.apps.googleusercontent.com';
    
    // 간단한 팝업 방식
    const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` + buildQuery({
      client_id: clientId,
      response_type: 'token',
      scope: 'openid email profile',
      redirect_uri: 'http://localhost:3000',
      prompt: 'consent',
    });
    
    // 팝업으로 구글 로그인
    const popup = window.open(authUrl, 'googleLogin', 'width=500,height=600,scrollbars=yes,resizable=yes');
    
    // 팝업에서 토큰 수신 대기
    const checkClosed = setInterval(() => {
      try {
        if (popup.closed) {
          clearInterval(checkClosed);
          return;
        }
        
        // URL에서 토큰 추출 시도
        const url = popup.location.href;
        if (url.includes('access_token=')) {
          const token = url.split('access_token=')[1].split('&')[0];
          popup.close();
          clearInterval(checkClosed);
          
          // 백엔드로 토큰 전송
          handleGoogleToken(decodeURIComponent(token));
        }
      } catch (e) {
        // CORS 오류 무시 (정상적인 동작)
      }
    }, 1000);
  }, []);


  // ✅ 카카오: 리다이렉트 방식으로 변경
  const handleKakaoLogin = useCallback(() => {
    const clientId = process.env.REACT_APP_KAKAO_CLIENT_ID || '8bfca9df8364fead1243d41c773ec5a2';
    let redirectUri = process.env.REACT_APP_KAKAO_REDIRECT_URI || `${window.location.origin}/auth/kakao/callback`;
    if (!redirectUri.includes('/auth/kakao/callback')) {
      const normalized = redirectUri.replace(/\/?$/, '');
      redirectUri = `${normalized}/auth/kakao/callback`;
    }
    
    const q = buildQuery({
      response_type: 'code',
      client_id: clientId,
      redirect_uri: redirectUri,
      scope: 'profile_nickname,account_email',
      prompt: 'login',
    });
    
    const authUrl = `https://kauth.kakao.com/oauth/authorize?${q}`;
    
    // 현재 페이지에서 카카오 로그인으로 이동
    window.location.href = authUrl;
  }, []);

  // ✅ 네이버: 리다이렉트 방식으로 변경
  const handleNaverLogin = useCallback(() => {
    const clientId = process.env.REACT_APP_NAVER_CLIENT_ID;
    let redirectUri = process.env.REACT_APP_NAVER_REDIRECT_URI || `${window.location.origin}/auth/naver/callback`;
    if (!redirectUri.includes('/auth/naver/callback')) {
      const normalized = redirectUri.replace(/\/?$/, '');
      redirectUri = `${normalized}/auth/naver/callback`;
    }
    
    if (!clientId) {
      console.warn('NAVER env가 비어 있습니다. REACT_APP_NAVER_CLIENT_ID 확인');
      alert('네이버 로그인 설정이 완료되지 않았습니다. 환경변수 REACT_APP_NAVER_CLIENT_ID를 확인해주세요.');
      return;
    }
    
    const state = Math.random().toString(36).slice(2, 13);
    localStorage.setItem('naverState', state);
    
    const q = buildQuery({
      response_type: 'code',
      client_id: clientId,
      redirect_uri: redirectUri,
      state,
      auth_type: 'reauthenticate',
      prompt: 'consent',
      service_provider: 'NAVER',
      access_type: 'offline',
      include_granted_scopes: 'true',
    });
    
    const authUrl = `https://nid.naver.com/oauth2.0/authorize?${q}`;
    
    // 현재 페이지에서 네이버 로그인으로 이동
    window.location.href = authUrl;
  }, []);


  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-40">
      <div className="bg-white p-6 rounded-lg shadow-lg w-96 relative">
        <X
          className="absolute top-3 right-3 w-6 h-6 cursor-pointer text-gray-500 hover:text-gray-700"
          onClick={onClose}
        />
        <h3 className="text-xl font-bold mb-2 text-left" style={{ color: '#2d3e2c' }}>로그인</h3>
        <p className="text-sm text-gray-600 mb-4 text-left">소셜 계정으로 간편하게 로그인하세요.</p>
        <hr className="w-full border-gray-300 mb-4" />

        {/* 소셜 로그인 버튼들 */}
        <div className="w-full flex flex-col space-y-3">
          <button 
            className="w-full p-3 border border-gray-200 rounded-lg bg-white transition-colors font-medium"
            style={{ color: '#2d3e2c' }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = 'rgba(139, 168, 138, 0.05)';
              e.target.style.borderColor = 'rgba(139, 168, 138, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = 'white';
              e.target.style.borderColor = '#d1d5db';
            }}
            onClick={handleGoogleLogin}
          >
            Google로 로그인
          </button>

          <button 
            className="w-full p-3 border border-gray-200 rounded-lg bg-white transition-colors font-medium"
            style={{ color: '#2d3e2c' }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = 'rgba(139, 168, 138, 0.05)';
              e.target.style.borderColor = 'rgba(139, 168, 138, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = 'white';
              e.target.style.borderColor = '#d1d5db';
            }}
            onClick={handleKakaoLogin}
          >
            Kakao로 로그인
          </button>

          <button 
            className="w-full p-3 border border-gray-200 rounded-lg bg-white transition-colors font-medium"
            style={{ color: '#2d3e2c' }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = 'rgba(139, 168, 138, 0.05)';
              e.target.style.borderColor = 'rgba(139, 168, 138, 0.4)';
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = 'white';
              e.target.style.borderColor = '#d1d5db';
            }}
            onClick={handleNaverLogin}
          >
            Naver로 로그인
          </button>
        </div>
      </div>
    </div>
  );
};

export default Loginbar;