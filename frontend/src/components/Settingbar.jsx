import React, { useState } from 'react';
import { Settings, X } from 'lucide-react';

const Settingbar = () => {
  const [isSettingModalOpen, setIsSettingModalOpen] = useState(false);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isSignupModalOpen, setIsSignupModalOpen] = useState(false);

  return (
    <div>
      {/* 설정 버튼 */}
      <Settings
        className="w-5 h-5 text-gray-600 cursor-pointer"
        onClick={() => setIsSettingModalOpen(true)}
      />

      {/* 설정 모달 */}
      {isSettingModalOpen && !isLoginModalOpen && !isSignupModalOpen && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white p-6 rounded-lg shadow-lg w-96 relative flex flex-col items-center">
            <X
              className="absolute top-3 right-3 w-6 h-6 cursor-pointer"
              onClick={() => setIsSettingModalOpen(false)}
            />
            <h2 className="text-2xl font-bold">AI OF AI</h2>
            <p className="text-sm text-gray-600 mb-4">
              AI 통합 기반 답변 최적화 플랫폼
            </p>

            {/* 로그인 & 회원가입 버튼 */}
            <button 
              className="w-full bg-gray-300 p-2 rounded mb-2" 
              onClick={() => setIsLoginModalOpen(true)}
            >
              로그인
            </button>
            <button 
              className="w-full bg-gray-300 p-2 rounded mb-2" 
              onClick={() => setIsSignupModalOpen(true)}
            >
              회원가입
            </button>
          </div>
        </div>
      )}

      {/* 로그인 모달 */}
      {isLoginModalOpen && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white p-6 rounded-lg shadow-lg w-96 relative flex flex-col items-center">
            <X
              className="absolute top-3 right-3 w-6 h-6 cursor-pointer"
              onClick={() => setIsLoginModalOpen(false)}
            />
            <h2 className="text-2xl font-bold">AI OF AI</h2>
            <p className="text-sm text-gray-600 mb-4">
              AI 통합 기반 답변 최적화 플랫폼
            </p>
            <button className="w-full bg-gray-300 p-2 rounded mb-2">Google로 로그인</button>
            <button className="w-full bg-gray-300 p-2 rounded mb-2">Kakao로 로그인</button>
            <button className="w-full bg-gray-300 p-2 rounded mb-4">Naver로 로그인</button>
            
            <hr className="w-full border-gray-400 mb-4" />
            <input type="email" placeholder="이메일" className="w-full p-2 border rounded mb-2" />
            <input type="password" placeholder="비밀번호" className="w-full p-2 border rounded mb-2" />
            <div className="text-xs text-gray-600 flex justify-between w-full">
              <span>비밀번호를 잊으셨나요?</span>{' '}
              <span className="text-blue-500 cursor-pointer">비밀번호 찾기</span>
            </div>
            <button className="w-full bg-gray-800 text-white p-2 rounded mt-4">로그인</button>
            <div className="text-xs text-gray-600 mt-2">
              계정이 없으신가요?{' '}
              <span className="text-blue-500 cursor-pointer" onClick={() => {
                setIsLoginModalOpen(false);
                setIsSignupModalOpen(true);
              }}>
                회원가입
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 회원가입 모달 */}
      {isSignupModalOpen && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white p-6 rounded-lg shadow-lg w-96 relative flex flex-col items-center">
            <X
              className="absolute top-3 right-3 w-6 h-6 cursor-pointer"
              onClick={() => setIsSignupModalOpen(false)}
            />
            <h2 className="text-2xl font-bold">AI OF AI</h2>
            <p className="text-sm text-gray-600 mb-4">
              AI 통합 기반 답변 최적화 플랫폼
            </p>
            <button className="w-full bg-gray-300 p-2 rounded mb-2">Google로 회원가입</button>
            <button className="w-full bg-gray-300 p-2 rounded mb-2">Kakao로 회원가입</button>
            <button className="w-full bg-gray-300 p-2 rounded mb-4">Naver로 회원가입</button>
            <div className="text-xs text-gray-600 mt-2">
              계정이 없으신가요?{' '}
              <span className="text-blue-500 cursor-pointer" onClick={() => {
                setIsSignupModalOpen(false);
                setIsLoginModalOpen(true); //나중에 회원가입 페이지로 이동하도록 수정해야함
              }}>
                회원가입
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Settingbar;
