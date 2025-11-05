// context/ChatContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../utils/api';

const ChatContext = createContext();

const MESSAGES_KEY = "aiofai:messages"; // {conversationId: {modelId: messages[]}}
const HISTORY_KEY = "aiofai:conversations";

export const ChatProvider = ({ children, initialModels = [] }) => {
  const location = useLocation();
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

  // 대화 ID가 변경되면 해당 대화의 메시지 불러오기
  useEffect(() => {
    if (!currentConversationId) {
      setMessages({});
      return;
    }

    try {
      const allMessages = JSON.parse(sessionStorage.getItem(MESSAGES_KEY) || '{}');
      const conversationMessages = allMessages[currentConversationId] || {};
      setMessages(conversationMessages);
    } catch (error) {
      console.error('메시지 불러오기 실패:', error);
      setMessages({});
    }
  }, [currentConversationId]);

  // 메시지 저장 함수
  const saveMessages = (conversationId, newMessages) => {
    if (!conversationId) return;
    
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
        console.warn(`⚠️ 메시지 저장 크기가 큽니다: ${sizeInMB.toFixed(2)}MB. 큰 파일 데이터는 제외됩니다.`);
        
        // 큰 파일 데이터를 제거하고 다시 저장
        const cleanedMessages = optimizeMessages(newMessages);
        const cleanedJson = JSON.stringify({ ...allMessages, [conversationId]: cleanedMessages });
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
        // 기존 히스토리 업데이트
        if (titleText) {
          history[conversationIndex].title = titleText.slice(0, 30) + (titleText.length > 30 ? '...' : '');
        }
        history[conversationIndex].updatedAt = Date.now();
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
      
      saveMessages(currentConversationId, newMessages);
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
          formData.append('message', messageText || '');
          
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
            saveMessages(currentConversationId, newMessages);
            return newMessages;
          });

          return aiResponse;

        } catch (error) {
          let errorText = `죄송합니다. ${modelId.toUpperCase()} 모델에서 오류가 발생했습니다.`;
          
          if (error.response) {
            const status = error.response.status;
            if (status === 401) {
              errorText = `${modelId.toUpperCase()} API 키가 유효하지 않습니다. 설정을 확인해주세요.`;
            } else if (status === 429) {
              errorText = `${modelId.toUpperCase()} API 사용량 한도를 초과했습니다. 잠시 후 다시 시도해주세요.`;
            } else if (status >= 500) {
              errorText = `${modelId.toUpperCase()} 서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.`;
            } else {
              errorText = `${modelId.toUpperCase()} 모델에서 오류가 발생했습니다. (오류 코드: ${status})`;
            }
          } else if (error.request) {
            errorText = `${modelId.toUpperCase()} 모델에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.`;
          } else {
            errorText = `${modelId.toUpperCase()} 모델 처리 중 예상치 못한 오류가 발생했습니다.`;
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
            saveMessages(currentConversationId, newMessages);
            return newMessages;
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
                  saveMessages(currentConversationId, newMessages);
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
            judge_model: 'GPT-5',
            selected_models: selectedModels || []
          };
          
          let response;
          
          if (hasFiles) {
            const formData = new FormData();
            formData.append('message', messageText || '');
            formData.append('user_id', 'default_user');
            formData.append('judge_model', 'GPT-5');
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
            });
          } else {
            response = await api.post(`/chat/optimal/`, requestData, {
              headers: {
                'Content-Type': 'application/json',
              },
            });
          }

          const data = response.data;
          console.log('✅ OPTIMAL 응답 받음:', {
            status: response.status,
            dataKeys: Object.keys(data),
            responseLength: data.response ? data.response.length : 0,
            responsePreview: data.response ? data.response.substring(0, 100) : 'null',
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

            const optimalMessage = {
              text: data.response || data.error || "최적화된 응답을 받았습니다.",
              isUser: false,
              timestamp: new Date().toISOString(),
              id: Date.now() + Math.random() + 'optimal',
              similarityData: similarityData
            };

            console.log('✅ OPTIMAL 메시지 생성:', {
              textLength: optimalMessage.text ? optimalMessage.text.length : 0,
              textPreview: optimalMessage.text ? optimalMessage.text.substring(0, 100) : 'null'
            });

            newMessages['optimal'] = [...newMessages['optimal'], optimalMessage];
            saveMessages(currentConversationId, newMessages);
            return newMessages;
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
          
          if (error.response) {
            const status = error.response.status;
            const errorData = error.response.data;
            console.error('❌ OPTIMAL 서버 응답 오류:', { status, errorData });
            
            if (status === 401) {
              errorText = `OPTIMAL 모델 API 키가 유효하지 않습니다. 설정을 확인해주세요.`;
            } else if (status === 429) {
              errorText = `OPTIMAL 모델 API 사용량 한도를 초과했습니다. 잠시 후 다시 시도해주세요.`;
            } else if (status >= 500) {
              errorText = `OPTIMAL 모델 서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.`;
            } else {
              errorText = `OPTIMAL 모델에서 오류가 발생했습니다. (오류 코드: ${status})${errorData?.error ? ': ' + errorData.error : ''}`;
            }
          } else if (error.request) {
            console.error('❌ OPTIMAL 요청 전송 실패:', error.request);
            errorText = `OPTIMAL 모델에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.`;
          } else {
            console.error('❌ OPTIMAL 예상치 못한 오류:', error);
            errorText = `OPTIMAL 모델 처리 중 예상치 못한 오류가 발생했습니다: ${error.message || '알 수 없는 오류'}`;
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
            saveMessages(currentConversationId, newMessages);
            return newMessages;
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