import React, { useEffect, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { loginSuccess } from '../store/authSlice';

const KakaoCallback = () => {
  const dispatch = useDispatch();
  const hasHandledRef = useRef(false);

  useEffect(() => {
    if (hasHandledRef.current) {
      return;
    }
    hasHandledRef.current = true;

    const handleKakaoCallback = async () => {
      try {
        // URL에서 코드 추출
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const error = urlParams.get('error');

        if (error) {
          console.error('카카오 로그인 오류:', error);
          alert('카카오 로그인 중 오류가 발생했습니다.');
          window.location.href = '/';
          return;
        }

        if (!code) {
          console.error('카카오 인증 코드가 없습니다.');
          alert('카카오 인증 코드를 받지 못했습니다.');
          window.location.href = '/';
          return;
        }

        // 코드를 액세스 토큰으로 교환
        const clientId = process.env.REACT_APP_KAKAO_CLIENT_ID || '8bfca9df8364fead1243d41c773ec5a2';
        let redirectUri = process.env.REACT_APP_KAKAO_REDIRECT_URI || `${window.location.origin}/auth/kakao/callback`;
        if (!redirectUri.includes('/auth/kakao/callback')) {
          const normalized = redirectUri.replace(/\/?$/, '');
          redirectUri = `${normalized}/auth/kakao/callback`;
        }

        const tokenParams = new URLSearchParams({
          grant_type: 'authorization_code',
          client_id: clientId,
          redirect_uri: redirectUri,
          code: code,
        });
        const clientSecret = process.env.REACT_APP_KAKAO_CLIENT_SECRET;
        if (clientSecret) {
          tokenParams.append('client_secret', clientSecret);
        }

        const tokenResponse = await fetch('https://kauth.kakao.com/oauth/token', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: tokenParams,
        });

        const tokenData = await tokenResponse.json();

        if (!tokenResponse.ok) {
          const errorDescription = tokenData.error_description || JSON.stringify(tokenData);
          throw new Error(`카카오 토큰 교환 실패: ${errorDescription}`);
        }

        const accessToken = tokenData.access_token;

        // 백엔드로 토큰 전송
        const response = await fetch('http://localhost:8000/api/auth/kakao/callback/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            access_token: accessToken
          }),
        });

        if (response.ok) {
          const data = await response.json();
          console.log('카카오 로그인 성공:', data);

          // Redux store에 사용자 정보 저장
          dispatch(loginSuccess(data.user));

          // 로컬 스토리지에도 저장
          localStorage.setItem('user', JSON.stringify(data.user));

          // 메인 페이지로 이동
          window.location.href = '/';
        } else {
          const errorData = await response.json();
          console.error('카카오 로그인 실패:', errorData);
          alert('카카오 로그인 처리 중 오류가 발생했습니다: ' + (errorData.error || '알 수 없는 오류'));
          window.location.href = '/';
        }
      } catch (error) {
        console.error('카카오 로그인 처리 오류:', error);
        alert('카카오 로그인 중 오류가 발생했습니다: ' + error.message);
        window.location.href = '/';
      }
    };

    handleKakaoCallback();
  }, [dispatch]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-gray-600">카카오 로그인 처리 중...</p>
      </div>
    </div>
  );
};

export default KakaoCallback;