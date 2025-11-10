import React, { useEffect, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { loginSuccess } from '../store/authSlice';

const NaverCallback = () => {
  const dispatch = useDispatch();
  const hasHandledRef = useRef(false);

  useEffect(() => {
    if (hasHandledRef.current) {
      return;
    }
    hasHandledRef.current = true;

    const handleNaverCallback = async () => {
      try {
        // URL에서 코드 추출
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        const error = urlParams.get('error');

        if (error) {
          console.error('네이버 로그인 오류:', error);
          alert('네이버 로그인 중 오류가 발생했습니다.');
          window.location.href = '/';
          return;
        }

        if (!code) {
          console.error('네이버 인증 코드가 없습니다.');
          alert('네이버 인증 코드를 받지 못했습니다.');
          window.location.href = '/';
          return;
        }

        // 저장된 state와 비교
        const savedState = localStorage.getItem('naverState');
        if (state !== savedState) {
          console.error('네이버 state 불일치');
          alert('보안 오류가 발생했습니다.');
          window.location.href = '/';
          return;
        }

        // 백엔드로 code/state 전달하여 토큰 교환 및 사용자 정보 처리
        const clientId = process.env.REACT_APP_NAVER_CLIENT_ID || '';
        const clientSecret = process.env.REACT_APP_NAVER_CLIENT_SECRET || '';
        let redirectUri = process.env.REACT_APP_NAVER_REDIRECT_URI || `${window.location.origin}/auth/naver/callback`;
        if (!redirectUri.includes('/auth/naver/callback')) {
          const normalized = redirectUri.replace(/\/?$/, '');
          redirectUri = `${normalized}/auth/naver/callback`;
        }

        const response = await fetch('http://localhost:8000/api/auth/naver/callback/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            code,
            state,
            client_id: clientId,
            client_secret: clientSecret,
            redirect_uri: redirectUri,
          }),
        });

        if (response.ok) {
          const data = await response.json();
          console.log('네이버 로그인 성공:', data);

          // Redux store에 사용자 정보 저장
          dispatch(loginSuccess(data.user));

          // 로컬 스토리지에도 저장
          localStorage.setItem('user', JSON.stringify(data.user));

          // 메인 페이지로 이동
          window.location.href = '/';
        } else {
          const errorData = await response.json();
          console.error('네이버 로그인 실패:', errorData);
          alert('네이버 로그인 처리 중 오류가 발생했습니다: ' + (errorData.error || '알 수 없는 오류'));
          window.location.href = '/';
        }
      } catch (error) {
        console.error('네이버 로그인 처리 오류:', error);
        alert('네이버 로그인 중 오류가 발생했습니다: ' + error.message);
        window.location.href = '/';
      }
    };

    handleNaverCallback();
  }, [dispatch]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500 mx-auto mb-4"></div>
        <p className="text-gray-600">네이버 로그인 처리 중...</p>
      </div>
    </div>
  );
};

export default NaverCallback;