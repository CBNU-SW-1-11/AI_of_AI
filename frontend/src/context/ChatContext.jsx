// context/ChatContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../utils/api';

const ChatContext = createContext();

const MESSAGES_KEY = "aiofai:messages"; // {conversationId: {modelId: messages[]}}
const HISTORY_KEY = "aiofai:conversations";

export const ChatProvider = ({ children, initialModels = [] }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [selectedModels, setSelectedModels] = useState(initialModels);
  const [messages, setMessages] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [loadingModels, setLoadingModels] = useState(new Set());
  const [loadingProgress, setLoadingProgress] = useState({});
  const [currentConversationId, setCurrentConversationId] = useState(null);

  // URL에서 현재 대화 ID 가져오기
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const cid = params.get('cid');
    setCurrentConversationId(cid);
  }, [location.search]);

  // 대화 ID가 변경되면 해당 대화의 메시지 및 AI 모델 불러오기
  useEffect(() => {
    if (!currentConversationId) {
      setMessages({});
      return;
    }

    try {
      // 메시지 불러오기
      const allMessages = JSON.parse(sessionStorage.getItem(MESSAGES_KEY) || '{}');
      const conversationMessages = allMessages[currentConversationId] || {};
      
      console.log('📥 메시지 불러오기:', {
        conversationId: currentConversationId,
        messageKeys: Object.keys(conversationMessages),
        messageCounts: Object.entries(conversationMessages).reduce((acc, [key, val]) => {
          acc[key] = Array.isArray(val) ? val.length : 'not array';
          return acc;
        }, {})
      });
      setMessages(conversationMessages);

      // 해당 대화의 AI 모델 복원
      const history = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]');
      const currentConversation = history.find(conv => conv.id === currentConversationId);
      
      if (currentConversation && currentConversation.selectedModels) {
        console.log('🔄 대화 전환: AI 모델 복원', currentConversation.selectedModels);
        setSelectedModels(currentConversation.selectedModels);
      }
    } catch (error) {
      console.error('메시지 불러오기 실패:', error);
      setMessages({});
    }
  }, [currentConversationId]);

  // 메시지 저장 함수
  const saveMessages = (conversationId, newMessages) => {
    if (!conversationId) return;
    
    console.log('💾 메시지 저장 시도:', {
      conversationId,
      messageKeys: Object.keys(newMessages),
      messageCounts: Object.entries(newMessages).reduce((acc, [key, val]) => {
        acc[key] = Array.isArray(val) ? val.length : 'not array';
        return acc;
      }, {})
    });
    
    try {
      // 파일 데이터 최적화: 큰 파일은 메타데이터만 저장
      const optimizeMessages = (messages) => {
        if (!messages || typeof messages !== 'object') return messages;
        
        const optimized = {};
        for (const [modelId, messageArray] of Object.entries(messages)) {
          if (!Array.isArray(messageArray)) {
            optimized[modelId] = messageArray;
            continue;
          }
          
          optimized[modelId] = messageArray.map(msg => {
            if (!msg.files || !Array.isArray(msg.files)) return msg;
            
            // 파일 데이터 최적화
            const optimizedFiles = msg.files.map(file => {
              // dataUrl 크기 체크 (2MB 이상이면 메타데이터만 저장)
              const dataUrlSize = file.dataUrl ? (file.dataUrl.length * 0.75) / 1024 / 1024 : 0; // Base64 대략적 크기 계산
              
              if (dataUrlSize > 2) {
                // 큰 파일은 메타데이터만 저장하고 플래그 추가
                return {
                  name: file.name,
                  type: file.type,
                  size: file.size,
                  dataUrl: null, // 큰 파일은 null로 저장
                  _largeFile: true,
                  _dataUrlSize: dataUrlSize.toFixed(2) + 'MB'
                };
              }
              
              // 작은 파일은 전체 저장
              return file;
            });
            
            return {
              ...msg,
              files: optimizedFiles
            };
          });
        }
        
        return optimized;
      };
      
      const optimizedMessages = optimizeMessages(newMessages);
      const allMessages = JSON.parse(sessionStorage.getItem(MESSAGES_KEY) || '{}');
      allMessages[conversationId] = optimizedMessages;
      
      // 저장 시도 (크기 체크)
      const jsonString = JSON.stringify(allMessages);
      const sizeInMB = (new Blob([jsonString]).size) / 1024 / 1024;
      
      if (sizeInMB > 5) {
        console.warn(`⚠️ 메시지 저장 크기가 큽니다: ${sizeInMB.toFixed(2)}MB. 모든 파일 데이터와 오래된 메시지를 제외합니다.`);
        
        // 더 공격적인 정리: 모든 파일의 dataUrl 제거 + 최근 메시지만 유지
        const aggressiveOptimize = (messages) => {
          const result = {};
          for (const [model, msgs] of Object.entries(messages)) {
            if (!Array.isArray(msgs)) continue;
            
            // 최근 30개 메시지만 유지 (대화 15턴)
            const recentMsgs = msgs.slice(-30);
            
            result[model] = recentMsgs.map(msg => {
              if (!msg) return msg;
              
              // 모든 파일의 dataUrl 제거
              const cleanedFiles = msg.files ? msg.files.map(file => ({
                name: file.name,
                type: file.type,
                size: file.size,
                dataUrl: null // 모든 파일 데이터 제거
              })) : msg.files;
              
              return {
                ...msg,
                files: cleanedFiles
              };
            });
          }
          return result;
        };
        
        const cleanedMessages = aggressiveOptimize(newMessages);
        const cleanedAll = { ...allMessages, [conversationId]: cleanedMessages };
        const cleanedJson = JSON.stringify(cleanedAll);
        const cleanedSize = (new Blob([cleanedJson]).size) / 1024 / 1024;
        
        console.log(`✅ 정리 후 크기: ${cleanedSize.toFixed(2)}MB`);
        sessionStorage.setItem(MESSAGES_KEY, cleanedJson);
      } else {
        sessionStorage.setItem(MESSAGES_KEY, jsonString);
      }
      
      // 히스토리 업데이트 (제목과 시간)
      let history = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]');
      let conversationIndex = history.findIndex(item => item.id === conversationId);
      
      // 첫 사용자 메시지 찾기 (모든 모델의 메시지에서 찾기)
      let firstUserMessageObj = null;
      for (const messageArray of Object.values(newMessages)) {
        if (Array.isArray(messageArray)) {
          firstUserMessageObj = messageArray.find(msg => msg && msg.isUser);
          if (firstUserMessageObj) break;
        }
      }
      
      let titleText = '';
      
      if (firstUserMessageObj) {
        if (firstUserMessageObj.text && firstUserMessageObj.text.trim()) {
          titleText = firstUserMessageObj.text.trim();
        } else if (firstUserMessageObj.files && firstUserMessageObj.files.length > 0) {
          // 파일만 있는 경우 파일명으로 제목 설정
          const fileNames = firstUserMessageObj.files.map(f => f.name || '파일').join(', ');
          titleText = `📎 ${fileNames}`;
        }
      }
      
      if (conversationIndex === -1) {
        // 히스토리에 없으면 새로 추가
        const newConversation = {
          id: conversationId,
          title: titleText ? (titleText.slice(0, 30) + (titleText.length > 30 ? '...' : '')) : '새 대화',
          updatedAt: Date.now()
        };
        history = [newConversation, ...history].slice(0, 100);
        sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history));
        
        // storage 이벤트 수동 발생 (다른 탭용)
        window.dispatchEvent(new StorageEvent('storage', {
          key: HISTORY_KEY,
          newValue: JSON.stringify(history)
        }));
        // 같은 탭에서도 감지되도록 custom event 발생
        window.dispatchEvent(new CustomEvent('customstorage', {
          detail: { key: HISTORY_KEY, newValue: JSON.stringify(history) }
        }));
      } else {
        // 기존 히스토리 업데이트 (순서 변경: 맨 위로 이동)
        const existingConversation = history[conversationIndex];
        
        // 제목이 명시적으로 설정되지 않았고 "새 대화"인 경우에만 첫 메시지로 업데이트
        if (titleText && !existingConversation._titleSet && existingConversation.title === "새 대화") {
          existingConversation.title = titleText.slice(0, 30) + (titleText.length > 30 ? '...' : '');
        }
        existingConversation.updatedAt = Date.now();
        
        // 배열에서 제거하고 맨 앞에 추가
        history.splice(conversationIndex, 1);
        history.unshift(existingConversation);
        
        sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history));
        
        // storage 이벤트 수동 발생 (다른 탭용)
        window.dispatchEvent(new StorageEvent('storage', {
          key: HISTORY_KEY,
          newValue: JSON.stringify(history)
        }));
        // 같은 탭에서도 감지되도록 custom event 발생
        window.dispatchEvent(new CustomEvent('customstorage', {
          detail: { key: HISTORY_KEY, newValue: JSON.stringify(history) }
        }));
      }
    } catch (error) {
      console.error('메시지 저장 실패:', error);
      // 오류 발생 시 큰 파일 데이터 없이 재시도
      try {
        const allMessages = JSON.parse(sessionStorage.getItem(MESSAGES_KEY) || '{}');
        const cleanedMessages = {};
        for (const [modelId, messageArray] of Object.entries(newMessages)) {
          if (Array.isArray(messageArray)) {
            cleanedMessages[modelId] = messageArray.map(msg => {
              if (msg.files && Array.isArray(msg.files)) {
                return {
                  ...msg,
                  files: msg.files.map(f => ({
                    name: f.name,
                    type: f.type,
                    size: f.size,
                    dataUrl: null,
                    _largeFile: true
                  }))
                };
              }
              return msg;
            });
          } else {
            cleanedMessages[modelId] = messageArray;
          }
        }
        allMessages[conversationId] = cleanedMessages;
        sessionStorage.setItem(MESSAGES_KEY, JSON.stringify(allMessages));
        console.log('✅ 큰 파일 제외 후 메시지 저장 성공');
      } catch (retryError) {
        console.error('재시도 저장도 실패:', retryError);
      }
    }
  };

  useEffect(() => {
    if (initialModels.length > 0) {
      setSelectedModels(initialModels);
    }
  }, [initialModels]);

  // AI 모델이 변경되면 히스토리에 저장 (updatedAt은 변경하지 않음 - 순서 유지)
  // 단, 모델 변경 감지를 위해 임시로만 저장하고, 실제 메시지 전송 시 새 대화로 분리
  useEffect(() => {
    if (!currentConversationId || selectedModels.length === 0) return;

    try {
      const history = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]');
      const currentConv = history.find(conv => conv.id === currentConversationId);
      
      // 현재 대화가 히스토리에 있고, 모델이 설정되어 있지 않은 경우에만 업데이트
      // (새로 생성된 대화방의 경우)
      if (currentConv && (!currentConv.selectedModels || currentConv.selectedModels.length === 0)) {
        const updatedHistory = history.map(conv => {
          if (conv.id === currentConversationId) {
            return {
              ...conv,
              selectedModels: selectedModels
            };
          }
          return conv;
        });
        
        sessionStorage.setItem(HISTORY_KEY, JSON.stringify(updatedHistory));
        
        // storage 이벤트 발생
        window.dispatchEvent(new StorageEvent('storage', {
          key: HISTORY_KEY,
          newValue: JSON.stringify(updatedHistory)
        }));
      }
    } catch (error) {
      console.error('모델 선택 저장 실패:', error);
    }
  }, [selectedModels, currentConversationId]);

  useEffect(() => {
    const initializeChat = async () => {
      try {
        await api.post('/api/cache/clear/', { user_id: 'default_user' });
        console.log('✅ 새로고침 시 LLM 캐시 초기화 완료');
      } catch (error) {
        console.warn('⚠️ 채팅 초기화 실패:', error);
      }
    };

    initializeChat();
  }, []);

  const sendMessage = async (messageText, requestId = null, options = {}) => {
    if (!currentConversationId) {
      console.error('대화 ID가 없습니다.');
      return;
    }

    const filesBase64 = options.filesBase64 || [];
    const imagesBase64 = options.imagesBase64 || [];
    const videosBase64 = options.videosBase64 || [];
    const hasFiles = filesBase64.length > 0 || imagesBase64.length > 0 || videosBase64.length > 0;
    
    if (!messageText?.trim() && !hasFiles) {
      console.warn('메시지나 파일이 없습니다.');
      return;
    }
    
    if (!selectedModels || selectedModels.length === 0) {
      console.warn('선택된 모델이 없습니다.');
      return;
    }
    
    if (messageText && messageText.length > 10000) {
      console.warn('메시지가 너무 깁니다. 10,000자 이하로 입력해주세요.');
      return;
    }
    
    const maxFileSize = 10 * 1024 * 1024;
    const oversizedFiles = [...filesBase64, ...imagesBase64, ...videosBase64].filter(file => 
      file.size && file.size > maxFileSize
    );
    
    if (oversizedFiles.length > 0) {
      console.warn(`파일 크기가 너무 큽니다. 10MB 이하의 파일을 업로드해주세요.`);
      return;
    }

    // 🔄 AI 모델 변경 감지: 히스토리의 모델과 현재 선택된 모델 비교
    let actualConversationId = currentConversationId;
    let newlyAddedModels = []; // 새로 추가된 모델 추적
    let conversationContext = null; // 이전 대화 맥락
    
    try {
      const history = JSON.parse(sessionStorage.getItem(HISTORY_KEY) || '[]');
      const currentConversation = history.find(conv => conv.id === currentConversationId);
      
      // 현재 대화가 있고, 모델이 설정되어 있는 경우
      if (currentConversation) {
        const historyModels = (currentConversation.selectedModels || []).sort();
        const currentModels = [...selectedModels].sort();
        
        // 모델이 변경되었는지 확인 (빈 배열에서 모델이 추가된 경우도 포함)
        const modelsChanged = JSON.stringify(historyModels) !== JSON.stringify(currentModels);
        
        if (modelsChanged && currentModels.length > 0) {
          console.log('🔄 AI 모델 변경 감지! 새 대화 생성');
          console.log('이전 모델:', historyModels);
          console.log('현재 모델:', currentModels);
          
          // 새로 추가된 모델 찾기
          newlyAddedModels = currentModels.filter(model => !historyModels.includes(model));
          console.log('🆕 새로 추가된 모델:', newlyAddedModels);
          
          // 기존 메시지 가져오기
          const allMessages = JSON.parse(sessionStorage.getItem(MESSAGES_KEY) || '{}');
          const oldMessages = allMessages[currentConversationId] || {};
          
          // 이전 대화의 전체 히스토리 생성 (질문 + 답변)
          const conversationHistory = [];
          
          // 변경되지 않은 모델 중 하나를 선택하여 전체 대화 흐름 추출
          let referenceModel = historyModels.find(modelId => 
            currentModels.includes(modelId) && oldMessages[modelId]
          );
          
          // 모든 AI가 바뀌었을 경우, 이전 대화의 첫 번째 모델을 참조 모델로 사용
          if (!referenceModel && historyModels.length > 0) {
            referenceModel = historyModels.find(modelId => oldMessages[modelId]);
          }
          
          if (referenceModel && oldMessages[referenceModel]) {
            const referenceMessages = oldMessages[referenceModel];
            
            referenceMessages.forEach(msg => {
              if (msg.isUser) {
                // 사용자 질문 추가
                conversationHistory.push({
                  role: 'user',
                  text: msg.text,
                  timestamp: msg.timestamp
                });
              } else {
                // AI 답변 추가
                conversationHistory.push({
                  role: 'assistant',
                  text: msg.text,
                  timestamp: msg.timestamp
                });
              }
            });
          }
          
          // 맥락 텍스트 생성 (최근 대화 포함)
          if (conversationHistory.length > 0) {
            // 최근 10개 메시지만 (너무 길어지지 않도록)
            const recentHistory = conversationHistory.slice(-10);
            
            conversationContext = "=== 이전 대화 내역 ===\n\n";
            
            recentHistory.forEach((msg, idx) => {
              if (msg.role === 'user') {
                conversationContext += `[사용자 질문 ${Math.floor(idx/2) + 1}]\n${msg.text}\n\n`;
              } else {
                conversationContext += `[AI 답변]\n${msg.text.substring(0, 500)}${msg.text.length > 500 ? '...(이하 생략)' : ''}\n\n`;
              }
            });
            
            conversationContext += "===================\n\n위 대화 내역을 참고하여, 이어지는 질문에 답변해주세요.\n\n현재 질문:\n";
            
            console.log('📝 생성된 대화 맥락:', {
              historyLength: conversationHistory.length,
              recentHistoryLength: recentHistory.length,
              referenceModel,
              contextPreview: conversationContext.substring(0, 300) + '...'
            });
          }
          
          // 새 대화 ID 생성
          const newId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
          
          // 현재 메시지를 제목으로 설정
          let newTitle = "새 대화";
          if (messageText && messageText.trim()) {
            newTitle = messageText.trim().slice(0, 30) + (messageText.trim().length > 30 ? '...' : '');
          } else if (hasFiles) {
            const fileNames = [...filesBase64, ...imagesBase64, ...videosBase64]
              .map(f => f.name || '파일').slice(0, 2).join(', ');
            newTitle = `📎 ${fileNames}`;
          }
          
          const newConversation = {
            id: newId,
            title: newTitle,
            updatedAt: Date.now(),
            selectedModels: selectedModels,
            _titleSet: true // 제목이 명시적으로 설정되었음을 표시
          };
          
          // 변경되지 않은 모델의 메시지만 복사
          const newMessages = {};
          const unchangedModels = historyModels.filter(model => currentModels.includes(model));
          
          // 공통 모델의 메시지 복사
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
          
          console.log('✅ 복사된 메시지:', {
            unchangedModels,
            allModelsChanged,
            newMessagesKeys: Object.keys(newMessages),
            hasOptimal: !!newMessages['optimal']
          });
          
          allMessages[newId] = newMessages;
          sessionStorage.setItem(MESSAGES_KEY, JSON.stringify(allMessages));
          
          // 히스토리에 새 대화 추가
          const updatedHistory = [newConversation, ...history].slice(0, 100);
          sessionStorage.setItem(HISTORY_KEY, JSON.stringify(updatedHistory));
          
          // storage 이벤트 발생
          window.dispatchEvent(new StorageEvent('storage', {
            key: HISTORY_KEY,
            newValue: JSON.stringify(updatedHistory)
          }));
          
          // 새 대화로 전환 (optimal 메시지 제거 확인)
          setCurrentConversationId(newId);
          setMessages(newMessages);
          
          // URL 업데이트 및 페이지 이동
          navigate(`/?cid=${newId}`, { replace: true });
          
          // 새 대화 ID로 메시지 전송 계속
          actualConversationId = newId;
        }
      }
    } catch (error) {
      console.error('모델 변경 감지 실패:', error);
    }

    const userMessage = {
      text: messageText?.trim() || '',
      isUser: true,
      timestamp: new Date().toISOString(),
      id: Date.now() + Math.random(),
      files: hasFiles ? [...filesBase64, ...imagesBase64, ...videosBase64] : []
    };

    const modelsToUpdate = [...selectedModels, "optimal"];
    
    // 사용자 메시지를 한 번만 추가 (중복 방지)
    setMessages(prevMessages => {
      const newMessages = { ...prevMessages };
      
      modelsToUpdate.forEach(modelId => {
        if (!newMessages[modelId]) {
          newMessages[modelId] = [];
        }
        // 중복 체크: 같은 ID의 메시지가 이미 있으면 추가하지 않음
        const alreadyExists = newMessages[modelId].some(msg => msg.id === userMessage.id);
        if (!alreadyExists) {
          newMessages[modelId] = [...newMessages[modelId], userMessage];
        }
      });
      
      saveMessages(actualConversationId, newMessages);
      return newMessages;
    });

    setIsLoading(true);
    setLoadingModels(new Set(modelsToUpdate));
    setLoadingProgress({});

    try {
      const otherModels = modelsToUpdate.filter(modelId => modelId !== 'optimal');
      const otherResponses = {};
      
      const otherResponsePromises = otherModels.map(async (modelId, index) => {
        try {
          setLoadingProgress(prev => ({
            ...prev,
            [modelId]: { status: 'processing', progress: 0 }
          }));
          
          const formData = new FormData();
          
          // 새로 추가된 모델인 경우 이전 대화 맥락 포함
          const isNewModel = newlyAddedModels.includes(modelId);
          const finalMessage = isNewModel && conversationContext 
            ? conversationContext + (messageText || '')
            : (messageText || '');
          
          formData.append('message', finalMessage);
          
          if (isNewModel && conversationContext) {
            console.log(`📨 ${modelId}에게 대화 맥락 전달:`, finalMessage.substring(0, 200) + '...');
          }
          
          if (hasFiles) {
            const firstFile = filesBase64[0] || imagesBase64[0] || videosBase64[0];
            if (firstFile) {
              const byteCharacters = atob(firstFile.dataUrl.split(',')[1]);
              const byteNumbers = new Array(byteCharacters.length);
              for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
              }
              const byteArray = new Uint8Array(byteNumbers);
              const blob = new Blob([byteArray], { type: firstFile.type });
              formData.append('file', blob, firstFile.name);
            }
          }

          const response = await api.post(`/chat/${modelId}/`, formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          });

          const data = response.data;
          const aiResponse = data.response || "응답을 받았습니다.";
          
          setLoadingProgress(prev => ({
            ...prev,
            [modelId]: { status: 'completed', progress: 100 }
          }));
          
          otherResponses[modelId] = aiResponse;
          
          const aiMessage = {
            text: aiResponse,
            isUser: false,
            timestamp: new Date().toISOString(),
            id: Date.now() + Math.random() + modelId
          };

          setMessages(prevMessages => {
            const newMessages = { ...prevMessages };
            if (!newMessages[modelId]) {
              newMessages[modelId] = [];
            }
            newMessages[modelId] = [...newMessages[modelId], aiMessage];
            saveMessages(actualConversationId, newMessages);
            return newMessages;
          });

          // 해당 모델의 로딩 상태 제거
          setLoadingModels(prev => {
            const newSet = new Set(prev);
            newSet.delete(modelId);
            return newSet;
          });

          return aiResponse;

        } catch (error) {
          let errorText = `죄송합니다. ${modelId.toUpperCase()} 모델에서 오류가 발생했습니다.`;
          
          // 백엔드에서 반환한 친화적인 오류 메시지 우선 사용
          if (error.response?.data?.error) {
            errorText = error.response.data.error;
          } else if (error.response?.data?.response) {
            // response 필드에 오류 메시지가 있는 경우
            errorText = error.response.data.response;
          } else if (error.response) {
            const status = error.response.status;
            if (status === 401) {
              errorText = `API 키가 유효하지 않습니다. 설정을 확인해주세요.`;
            } else if (status === 429) {
              errorText = `모델 사용량이 초과되었습니다. 다른 모델을 사용해주세요.`;
            } else if (status >= 500) {
              errorText = `서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.`;
            } else {
              errorText = `오류가 발생했습니다. 잠시 후 다시 시도해주세요.`;
            }
          } else if (error.request) {
            // 요청은 보냈지만 응답을 받지 못한 경우
            const errorCode = error.code;
            if (errorCode === 'ECONNREFUSED' || errorCode === 'ERR_CONNECTION_REFUSED') {
              errorText = `백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.`;
            } else if (errorCode === 'ETIMEDOUT' || errorCode === 'ECONNABORTED' || error.message?.includes('timeout')) {
              errorText = `요청 시간이 초과되었습니다. 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.`;
            } else if (errorCode === 'ERR_NETWORK' || errorCode === 'ENOTFOUND') {
              errorText = `네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인해주세요.`;
            } else {
              errorText = `서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.`;
            }
          } else {
            errorText = `처리 중 예상치 못한 오류가 발생했습니다.`;
          }
          
          setLoadingProgress(prev => ({
            ...prev,
            [modelId]: { status: 'error', progress: 0, error: errorText }
          }));
          
          const errorMessage = {
            text: errorText,
            isUser: false,
            timestamp: new Date().toISOString(),
            id: Date.now() + Math.random() + modelId + "_error",
            isError: true
          };

          setMessages(prevMessages => {
            const newMessages = { ...prevMessages };
            if (!newMessages[modelId]) {
              newMessages[modelId] = [];
            }
            newMessages[modelId] = [...newMessages[modelId], errorMessage];
            saveMessages(actualConversationId, newMessages);
            return newMessages;
          });
          
          // 에러 발생 시에도 로딩 상태 제거
          setLoadingModels(prev => {
            const newSet = new Set(prev);
            newSet.delete(modelId);
            return newSet;
          });
          
          return null;
        }
      });

      await Promise.all(otherResponsePromises);

      if (otherModels.length >= 2) {
        const modelResponses = {};
        
        setMessages(prevMessages => {
          const newMessages = { ...prevMessages };
          
          otherModels.forEach((modelId, index) => {
            const modelMessages = newMessages[modelId] || [];
            const lastAIMessage = modelMessages.filter(msg => !msg.isUser).pop();
            if (lastAIMessage) {
              modelResponses[modelId] = lastAIMessage.text;
            }
          });

          console.log('Collected model responses for similarity analysis:', modelResponses);

          if (Object.keys(modelResponses).length >= 2) {
            import('../utils/similarityAnalysis').then(({ calculateTextSimilarity, clusterResponses }) => {
              try {
                const clusters = clusterResponses(modelResponses, 0.7);
                const similarityMatrix = {};
                
                Object.keys(modelResponses).forEach(model1 => {
                  similarityMatrix[model1] = {};
                  Object.keys(modelResponses).forEach(model2 => {
                    if (model1 === model2) {
                      similarityMatrix[model1][model2] = 1;
                    } else {
                      similarityMatrix[model1][model2] = calculateTextSimilarity(
                        modelResponses[model1], 
                        modelResponses[model2]
                      );
                    }
                  });
                });

                const analysisResult = {
                  messageId: userMessage.id,
                  clusters,
                  similarityMatrix,
                  modelResponses,
                  averageSimilarity: Object.values(similarityMatrix)
                    .flatMap(row => Object.values(row))
                    .filter(val => val < 1)
                    .reduce((sum, val) => sum + val, 0) / (Object.keys(modelResponses).length * (Object.keys(modelResponses).length - 1))
                };

                console.log('Saving similarity analysis result for userMessage ID:', userMessage.id);
                console.log('Analysis result:', analysisResult);
                
                setMessages(prevMessages => {
                  const newMessages = { ...prevMessages };
                  if (!newMessages['_similarityData']) {
                    newMessages['_similarityData'] = {};
                  }
                  newMessages['_similarityData'][userMessage.id] = analysisResult;
                  console.log('Similarity data saved. Current _similarityData:', newMessages['_similarityData']);
                  saveMessages(actualConversationId, newMessages);
                  return newMessages;
                });
              } catch (error) {
                console.error('유사도 분석 오류:', error);
              }
            }).catch(error => {
              console.error('유사도 분석 모듈 로드 오류:', error);
            });
          }
          
          return newMessages;
        });
      }

      if (modelsToUpdate.includes('optimal')) {
        try {
          const requestData = {
            message: messageText || '',
            user_id: 'default_user',
            judge_model: 'GPT-4o',
            selected_models: selectedModels || []
          };
          
          let response;
          
          if (hasFiles) {
            const formData = new FormData();
            formData.append('message', messageText || '');
            formData.append('user_id', 'default_user');
            formData.append('judge_model', 'GPT-4o');
            formData.append('selected_models', JSON.stringify(selectedModels || []));
            
            const firstFile = filesBase64[0] || imagesBase64[0] || videosBase64[0];
            if (firstFile) {
              const byteCharacters = atob(firstFile.dataUrl.split(',')[1]);
              const byteNumbers = new Array(byteCharacters.length);
              for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
              }
              const byteArray = new Uint8Array(byteNumbers);
              const blob = new Blob([byteArray], { type: firstFile.type });
              formData.append('file', blob, firstFile.name);
            }
            
            response = await api.post(`/chat/optimal/`, formData, {
              headers: {
                'Content-Type': 'multipart/form-data',
              },
              timeout: 180000, // 3분
            });
          } else {
            response = await api.post(`/chat/optimal/`, requestData, {
              headers: {
                'Content-Type': 'application/json',
              },
              timeout: 180000, // 3분
            });
          }

          const data = response.data;
          console.log('✅ OPTIMAL 응답 받음:', {
            status: response.status,
            dataKeys: Object.keys(data),
            responseLength: data.response ? data.response.length : 0,
            responsePreview: data.response ? data.response.substring(0, 100) : 'null',
            hasAnalysisData: !!data.analysisData,
            hasRationale: !!data.rationale,
            fullData: data
          });
          
          if (!data.response || data.response.trim() === '') {
            console.error('❌ OPTIMAL 응답이 비어있습니다!', data);
          }
          
          setMessages(prevMessages => {
            const newMessages = { ...prevMessages };
            if (!newMessages['optimal']) {
              newMessages['optimal'] = [];
            }

            const similarityData = newMessages['_similarityData'] && newMessages['_similarityData'][userMessage.id] 
              ? newMessages['_similarityData'][userMessage.id] 
              : null;

            console.log('Creating optimal message for userMessage ID:', userMessage.id);
            console.log('Available similarity data:', newMessages['_similarityData']);
            console.log('Retrieved similarity data:', similarityData);
            console.log('Analysis data from backend:', JSON.stringify(data.analysisData, null, 2));
          console.log('Rationale from backend:', data.rationale);

          const formatOptimalResponse = (value) => {
            if (value === null || value === undefined) return '';
            if (typeof value === 'string') return value;

            try {
              let optimalAnswer =
                value['최적의_답변'] ||
                value.optimal_answer ||
                value.answer ||
                value.text ||
                '';

              const verificationResults =
                value['llm_검증_결과'] ||
                value.verification_results ||
                value.analysis ||
                {};

              const rationale =
                value['분석_근거'] ||
                value.analysis_rationale ||
                value.rationale ||
                '';

              if (!optimalAnswer) {
                const verificationEntries = Object.entries(verificationResults || {});
                if (verificationEntries.length > 0) {
                  const sortedByConfidence = verificationEntries
                    .map(([modelName, result]) => {
                      if (!result || typeof result !== 'object') return null;
                      const accuracy = result['정확성'] || result.accuracy || '';
                      const confidence = parseInt(result['신뢰도'] || result.confidence || '0', 10);
                      const adopted = result['채택된_정보'] || result.adopted_info || result.adopted || [];
                      return {
                        modelName,
                        accuracy,
                        confidence: Number.isNaN(confidence) ? 0 : confidence,
                        adopted: Array.isArray(adopted) ? adopted : [],
                      };
                    })
                    .filter(Boolean)
                    .sort((a, b) => b.confidence - a.confidence);

                  const bestEntry =
                    sortedByConfidence.find(entry => entry.accuracy === '✅' && entry.adopted.length > 0) ||
                    sortedByConfidence[0];

                  if (bestEntry) {
                    const adoptedText = bestEntry.adopted.join('\n');
                    optimalAnswer = `${bestEntry.modelName} 모델이 ${bestEntry.confidence}% 신뢰도로 선택되었습니다.\n\n${adoptedText}`;
                  }
                }
              }

              const recommendation =
                value['최종_추천'] ||
                value.recommendation ||
                '';

              const insights =
                value['추가_인사이트'] ||
                value.additional_insights ||
                '';

              let markdown = '';

              if (optimalAnswer) {
                markdown += `## 최적의 답변\n\n${optimalAnswer}\n\n`;
              }

              const entries = Object.entries(verificationResults || {});
              if (entries.length > 0) {
                markdown += '## 각 LLM 검증 결과\n';
                entries.forEach(([modelName, result]) => {
                  if (!result || typeof result !== 'object') return;
                  const accuracy = result['정확성'] || result.accuracy || '';
                  const error = result['오류'] || result.error || '';
                  const confidence = result['신뢰도'] || result.confidence || '';
                  const adopted = result['채택된_정보'] || result.adopted_info || result.adopted || [];
                  const rejected = result['제외된_정보'] || result.rejected_info || result.rejected || [];

                  markdown += `\n### ${modelName}\n`;
                  if (accuracy) markdown += `- 정확성: ${accuracy}\n`;
                  if (error) markdown += `- 오류: ${error}\n`;
                  if (confidence !== '') markdown += `- 신뢰도: ${confidence}%\n`;
                  if (Array.isArray(adopted) && adopted.length > 0) {
                    adopted.forEach(item => {
                      if (item && String(item).trim()) {
                        markdown += `- 채택된 정보: ${item}\n`;
                      }
                    });
                  }
                  if (Array.isArray(rejected) && rejected.length > 0) {
                    rejected.forEach(item => {
                      if (item && String(item).trim()) {
                        markdown += `- 제외된 정보: ${item}\n`;
                      }
                    });
                  }
                });
                markdown += '\n';
              }

              if (rationale) {
                markdown += `## 분석 근거\n\n${rationale}\n\n`;
              }

              if (recommendation) {
                markdown += `## 최종 추천\n\n${recommendation}\n\n`;
              }

              if (insights) {
                markdown += `## 추가 인사이트\n\n${insights}\n\n`;
              }

              if (markdown.trim()) {
                return markdown.trim();
              }

              return JSON.stringify(value, null, 2);
            } catch (formatError) {
              console.warn('최적화 응답 포맷 변환 실패:', formatError);
              try {
                return JSON.stringify(value, null, 2);
              } catch {
                return String(value);
              }
            }
          };

          const formattedResponse = formatOptimalResponse(data.response || data.error || "최적화된 응답을 받았습니다.");
          console.log('Formatted optimal response:', formattedResponse);

          const optimalMessage = {
            text: formattedResponse,
              isUser: false,
              timestamp: new Date().toISOString(),
              id: Date.now() + Math.random() + 'optimal',
              similarityData: similarityData,
              // 백엔드에서 받은 분석 데이터 저장
              analysisData: data.analysisData || null,
              rationale: data.rationale || null
            };

            console.log('✅ OPTIMAL 메시지 생성:', {
              textLength: optimalMessage.text ? optimalMessage.text.length : 0,
              textPreview: optimalMessage.text ? optimalMessage.text.substring(0, 100) : 'null'
            });

            newMessages['optimal'] = [...newMessages['optimal'], optimalMessage];
            saveMessages(actualConversationId, newMessages);
            return newMessages;
          });

          // optimal 로딩 상태 제거
          setLoadingModels(prev => {
            const newSet = new Set(prev);
            newSet.delete('optimal');
            return newSet;
          });

        } catch (error) {
          console.error('❌ OPTIMAL 요청 오류:', {
            error,
            response: error.response,
            responseData: error.response?.data,
            request: error.request,
            message: error.message
          });
          
          let errorText = `죄송합니다. OPTIMAL 모델에서 오류가 발생했습니다.`;
          
          // 백엔드에서 반환한 친화적인 오류 메시지 우선 사용
          if (error.response?.data?.error) {
            errorText = error.response.data.error;
          } else if (error.response?.data?.response) {
            // response 필드에 오류 메시지가 있는 경우
            errorText = error.response.data.response;
          } else if (error.response) {
            const status = error.response.status;
            const errorData = error.response.data;
            console.error('❌ OPTIMAL 서버 응답 오류:', { status, errorData });
            
            if (status === 401) {
              errorText = `API 키가 유효하지 않습니다. 설정을 확인해주세요.`;
            } else if (status === 429) {
              errorText = `모델 사용량이 초과되었습니다. 다른 모델을 사용해주세요.`;
            } else if (status >= 500) {
              errorText = `서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.`;
            } else {
              errorText = `오류가 발생했습니다. 잠시 후 다시 시도해주세요.`;
            }
          } else if (error.request) {
            // 요청은 보냈지만 응답을 받지 못한 경우
            console.error('❌ OPTIMAL 요청 전송 실패:', error.request);
            const errorCode = error.code;
            if (errorCode === 'ECONNREFUSED' || errorCode === 'ERR_CONNECTION_REFUSED') {
              errorText = `백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.`;
            } else if (errorCode === 'ETIMEDOUT' || errorCode === 'ECONNABORTED' || error.message?.includes('timeout')) {
              errorText = `요청 시간이 초과되었습니다. 이미지 분석 등 시간이 오래 걸리는 작업일 수 있습니다. 잠시 후 다시 시도해주세요.`;
            } else if (errorCode === 'ERR_NETWORK' || errorCode === 'ENOTFOUND') {
              errorText = `네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인해주세요.`;
            } else {
              errorText = `서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.`;
            }
          } else {
            console.error('❌ OPTIMAL 예상치 못한 오류:', error);
            errorText = `처리 중 예상치 못한 오류가 발생했습니다.`;
          }
          
          const errorMessage = {
            text: errorText,
            isUser: false,
            timestamp: new Date().toISOString(),
            id: Date.now() + Math.random() + 'optimal_error',
            isError: true
          };

          setMessages(prevMessages => {
            const newMessages = { ...prevMessages };
            if (!newMessages['optimal']) {
              newMessages['optimal'] = [];
            }
            newMessages['optimal'] = [...newMessages['optimal'], errorMessage];
            saveMessages(actualConversationId, newMessages);
            return newMessages;
          });

          // optimal 에러 시에도 로딩 상태 제거
          setLoadingModels(prev => {
            const newSet = new Set(prev);
            newSet.delete('optimal');
            return newSet;
          });
        }
      }
      
    } catch (error) {
      console.error("Error in sendMessage:", error);
    } finally {
      setIsLoading(false);
      setLoadingModels(new Set());
    }
  };

  const getCacheStatistics = async () => {
    try {
      const response = await api.get('/api/cache/statistics/?user_id=default_user');
      return response.data;
    } catch (error) {
      console.warn('⚠️ 캐시 통계 조회 실패:', error);
      return null;
    }
  };

  const clearConversationContext = async () => {
    try {
      const response = await api.post('/api/cache/context/clear/', { user_id: 'default_user' });
      console.log('✅ 대화 맥락 초기화 완료');
      return response.data;
    } catch (error) {
      console.warn('⚠️ 대화 맥락 초기화 실패:', error);
      return null;
    }
  };

  return (
    <ChatContext.Provider value={{
      selectedModels,
      setSelectedModels,
      messages,
      setMessages,
      isLoading,
      loadingModels,
      loadingProgress,
      getCacheStatistics,
      clearConversationContext,
      sendMessage,
      currentConversationId
    }}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};