// context/ChatContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../utils/api';

const ChatContext = createContext();

export const ChatProvider = ({ children, initialModels = [] }) => {
  const [selectedModels, setSelectedModels] = useState(initialModels);
  const [messages, setMessages] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [loadingModels, setLoadingModels] = useState(new Set());
  const [loadingProgress, setLoadingProgress] = useState({});

  // initialModels가 변경되면 selectedModels 업데이트
  useEffect(() => {
    if (initialModels.length > 0) {
      setSelectedModels(initialModels);
    }
  }, [initialModels]);

  // 새로고침 시 캐시 초기화 및 대화 맥락 복원
  useEffect(() => {
    const initializeChat = async () => {
      try {
        // LLM 캐시 초기화
        await api.post('/api/cache/clear/', { user_id: 'default_user' });
        console.log('✅ 새로고침 시 LLM 캐시 초기화 완료');
      } catch (error) {
        console.warn('⚠️ 채팅 초기화 실패:', error);
      }
    };

    initializeChat();
  }, []); // 컴포넌트 마운트 시 한 번만 실행

  const sendMessage = async (messageText, requestId = null, options = {}) => {
    // 파일이 options에 있는 경우 처리
    const filesBase64 = options.filesBase64 || [];
    const imagesBase64 = options.imagesBase64 || [];
    const hasFiles = filesBase64.length > 0 || imagesBase64.length > 0;
    
    // 입력 유효성 검사
    if (!messageText?.trim() && !hasFiles) {
      console.warn('메시지나 파일이 없습니다.');
      return;
    }
    
    if (!selectedModels || selectedModels.length === 0) {
      console.warn('선택된 모델이 없습니다.');
      return;
    }
    
    // 메시지 길이 제한 (너무 긴 메시지 방지)
    if (messageText && messageText.length > 10000) {
      console.warn('메시지가 너무 깁니다. 10,000자 이하로 입력해주세요.');
      return;
    }
    
    // 파일 크기 제한 (10MB)
    const maxFileSize = 10 * 1024 * 1024; // 10MB
    const oversizedFiles = [...filesBase64, ...imagesBase64].filter(file => 
      file.size && file.size > maxFileSize
    );
    
    if (oversizedFiles.length > 0) {
      console.warn(`파일 크기가 너무 큽니다. 10MB 이하의 파일을 업로드해주세요.`);
      return;
    }

    // 파일명들을 추출
    const fileNames = [
      ...filesBase64.map(f => f.name),
      ...imagesBase64.map(f => f.name)
    ];

    // 사용자 메시지 생성
    const userMessage = {
      text: hasFiles ? `파일 업로드: ${fileNames.join(', ')}` : messageText.trim(),
      isUser: true,
      timestamp: new Date().toISOString(),
      id: Date.now() + Math.random(),
      // 파일이 있는 경우 파일 정보 추가
      files: hasFiles ? [...filesBase64, ...imagesBase64] : []
    };

    // 모든 선택된 모델 + optimal에 사용자 메시지 추가
    const modelsToUpdate = [...selectedModels, "optimal"];
    
    setMessages(prevMessages => {
      const newMessages = { ...prevMessages };
      
      modelsToUpdate.forEach(modelId => {
        if (!newMessages[modelId]) {
          newMessages[modelId] = [];
        }
        newMessages[modelId] = [...newMessages[modelId], userMessage];
      });
      
      return newMessages;
    });

    // 로딩 상태 시작
    setIsLoading(true);
    setLoadingModels(new Set(modelsToUpdate));
    setLoadingProgress({});

    // 각 모델별로 AI 응답 처리
    try {
      // 먼저 optimal을 제외한 모델들의 응답을 수집
      const otherModels = modelsToUpdate.filter(modelId => modelId !== 'optimal');
      const otherResponses = {};
      
             // 다른 모델들의 응답 수집
             const otherResponsePromises = otherModels.map(async (modelId, index) => {
               try {
                 // 로딩 진행률 업데이트
                 setLoadingProgress(prev => ({
                   ...prev,
                   [modelId]: { status: 'processing', progress: 0 }
                 }));
                 const formData = new FormData();
                 formData.append('message', messageText || '');
                 
                 // 파일이 있는 경우 FormData에 추가
                 if (hasFiles) {
                   // 첫 번째 파일만 전송 (백엔드에서 하나씩 처리)
                   const firstFile = filesBase64[0] || imagesBase64[0];
                   if (firstFile) {
                     // Base64를 Blob으로 변환
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
          
          // 로딩 완료 상태 업데이트
          setLoadingProgress(prev => ({
            ...prev,
            [modelId]: { status: 'completed', progress: 100 }
          }));
          
          // 응답 저장
          otherResponses[modelId] = aiResponse;
          
          const aiMessage = {
            text: aiResponse,
            isUser: false,
            timestamp: new Date().toISOString(),
            id: Date.now() + Math.random() + modelId
          };

          // 각 모델별로 응답 추가
          setMessages(prevMessages => {
            const newMessages = { ...prevMessages };
            if (!newMessages[modelId]) {
              newMessages[modelId] = [];
            }
            newMessages[modelId] = [...newMessages[modelId], aiMessage];
            return newMessages;
          });

          return aiResponse;

        } catch (error) {
          // 구체적인 에러 메시지 생성
          let errorText = `죄송합니다. ${modelId.toUpperCase()} 모델에서 오류가 발생했습니다.`;
          
          if (error.response) {
            // 서버 응답이 있는 경우
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
            // 네트워크 오류
            errorText = `${modelId.toUpperCase()} 모델에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.`;
          } else {
            // 기타 오류
            errorText = `${modelId.toUpperCase()} 모델 처리 중 예상치 못한 오류가 발생했습니다.`;
          }
          
          // 로딩 실패 상태 업데이트
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
            return newMessages;
          });
          
          return null;
        }
      });

             // 다른 모델들의 응답 완료 대기
             await Promise.all(otherResponsePromises);

             // 유사도 분석 수행 (2개 이상의 모델이 있는 경우)
             if (otherModels.length >= 2) {
               const modelResponses = {};
               
               // 최신 메시지 상태에서 AI 응답들 수집 및 유사도 분석 수행
               setMessages(prevMessages => {
                 const newMessages = { ...prevMessages };
                 
                 otherModels.forEach((modelId, index) => {
                   // 해당 모델의 최신 AI 응답 찾기
                   const modelMessages = newMessages[modelId] || [];
                   const lastAIMessage = modelMessages.filter(msg => !msg.isUser).pop();
                   if (lastAIMessage) {
                     modelResponses[modelId] = lastAIMessage.text;
                   }
                 });

                 console.log('Collected model responses for similarity analysis:', modelResponses);

                 if (Object.keys(modelResponses).length >= 2) {
                   // 비동기로 유사도 분석 수행
                   import('../utils/similarityAnalysis').then(({ calculateTextSimilarity, clusterResponses }) => {
                     try {
                       const clusters = clusterResponses(modelResponses, 0.7);
                       const similarityMatrix = {};
                       
                       // 유사도 행렬 계산
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

                       // 유사도 분석 결과 생성
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

                       // 유사도 분석 결과를 전역 상태에 저장
                       console.log('Saving similarity analysis result for userMessage ID:', userMessage.id);
                       console.log('Analysis result:', analysisResult);
                       
                       setMessages(prevMessages => {
                         const newMessages = { ...prevMessages };
                         if (!newMessages['_similarityData']) {
                           newMessages['_similarityData'] = {};
                         }
                         newMessages['_similarityData'][userMessage.id] = analysisResult;
                         console.log('Similarity data saved. Current _similarityData:', newMessages['_similarityData']);
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

             // optimal 모델 처리 (다른 AI들의 응답을 포함하여)
             if (modelsToUpdate.includes('optimal')) {
               try {
                 // JSON 형태로 데이터 전송 (judge_model 및 selected_models 포함)
                 const requestData = {
                   message: messageText || '',
                   user_id: 'default_user',
                   judge_model: 'GPT-3.5-turbo',  // 기본 심판 모델
                   selected_models: selectedModels || []  // 사용자가 선택한 모델들
                 };
                 
                 let response;
                 
                 if (hasFiles) {
                   // 파일이 있는 경우 FormData 사용
                   const formData = new FormData();
                   formData.append('message', messageText || '');
                   formData.append('user_id', 'default_user');
                   formData.append('judge_model', 'GPT-3.5-turbo');
                   formData.append('selected_models', JSON.stringify(selectedModels || []));
                   
                   // 첫 번째 파일만 전송 (백엔드에서 하나씩 처리)
                   const firstFile = filesBase64[0] || imagesBase64[0];
                   if (firstFile) {
                     // Base64를 Blob으로 변환
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
                   // 파일이 없는 경우 JSON 사용
                   response = await api.post(`/chat/optimal/`, requestData, {
                     headers: {
                       'Content-Type': 'application/json',
                     },
                   });
                 }

          const data = response.data;
          
          // optimal 응답 추가 (유사도 분석 데이터 포함)
          setMessages(prevMessages => {
            const newMessages = { ...prevMessages };
            if (!newMessages['optimal']) {
              newMessages['optimal'] = [];
            }

            // 유사도 분석 데이터 가져오기 (최신 상태에서)
            const similarityData = newMessages['_similarityData'] && newMessages['_similarityData'][userMessage.id] 
              ? newMessages['_similarityData'][userMessage.id] 
              : null;

            console.log('Creating optimal message for userMessage ID:', userMessage.id);
            console.log('Available similarity data:', newMessages['_similarityData']);
            console.log('Retrieved similarity data:', similarityData);

            const optimalMessage = {
              text: data.response || "최적화된 응답을 받았습니다.",
              isUser: false,
              timestamp: new Date().toISOString(),
              id: Date.now() + Math.random() + 'optimal',
              similarityData: similarityData
            };

            newMessages['optimal'] = [...newMessages['optimal'], optimalMessage];
            return newMessages;
          });

        } catch (error) {
          // 구체적인 에러 메시지 생성
          let errorText = `죄송합니다. OPTIMAL 모델에서 오류가 발생했습니다.`;
          
          if (error.response) {
            const status = error.response.status;
            if (status === 401) {
              errorText = `OPTIMAL 모델 API 키가 유효하지 않습니다. 설정을 확인해주세요.`;
            } else if (status === 429) {
              errorText = `OPTIMAL 모델 API 사용량 한도를 초과했습니다. 잠시 후 다시 시도해주세요.`;
            } else if (status >= 500) {
              errorText = `OPTIMAL 모델 서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.`;
            } else {
              errorText = `OPTIMAL 모델에서 오류가 발생했습니다. (오류 코드: ${status})`;
            }
          } else if (error.request) {
            errorText = `OPTIMAL 모델에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.`;
          } else {
            errorText = `OPTIMAL 모델 처리 중 예상치 못한 오류가 발생했습니다.`;
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
            return newMessages;
          });
        }
      }
      
    } catch (error) {
      console.error("Error in sendMessage:", error);
    } finally {
      // 로딩 상태 종료
      setIsLoading(false);
      setLoadingModels(new Set());
      // 진행률은 유지 (사용자가 확인할 수 있도록)
    }
  };

  // 캐시 통계 조회
  const getCacheStatistics = async () => {
    try {
      const response = await api.get('/api/cache/statistics/?user_id=default_user');
      return response.data;
    } catch (error) {
      console.warn('⚠️ 캐시 통계 조회 실패:', error);
      return null;
    }
  };

  // 대화 맥락 초기화
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
      sendMessage
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