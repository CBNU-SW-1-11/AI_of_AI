import React from 'react';
import { TrendingUp, ThumbsUp, ThumbsDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const normalizeModelName = (name) => {
  if (!name) return '';
  return String(name).toLowerCase().replace(/\s+/g, '-').replace(/_+/g, '-');
};

const normalizeTextList = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value
      .map(item => {
        if (item === null || item === undefined) return '';
        return String(item).trim();
      })
      .filter(Boolean);
  }
  if (typeof value === 'string') {
    return value
      .split(/\n|,|;/)
      .map(item => item.trim())
      .filter(Boolean);
  }
  return [];
};

const buildFallbackRationale = (analysisData, verificationSource) => {
  const parts = [];
  const sourceUsed =
    (verificationSource && (verificationSource.사용됨 ?? verificationSource.used ?? verificationSource.isUsed)) || false;

  const title =
    (verificationSource && (verificationSource.제목 || verificationSource.title)) ||
    (verificationSource && verificationSource.source) ||
    '검증 소스';

  if (sourceUsed) {
    const sourceName = verificationSource.source || verificationSource.소스;
    const display = sourceName && sourceName !== title ? `${title} (${sourceName})` : title;
    parts.push(`${display} 내용을 기준으로 답변을 정리했습니다.`);
  }

  const adoptedSummary = [];

  if (analysisData && typeof analysisData === 'object') {
    Object.entries(analysisData).forEach(([modelName, detail]) => {
      if (!detail || typeof detail !== 'object') return;
      const adoptedSentences = normalizeTextList(detail.채택된_정보 || detail.adopted || detail.adopted_info);
      const rejectedSentences = normalizeTextList(detail.제외된_정보 || detail.rejected || detail.rejected_info);
      const accuracy = typeof detail.정확성 === 'string' ? detail.정확성.trim() : (detail.accuracy || '');
      const error = (detail.오류 || detail.error || '').toString().trim();

      if (adoptedSentences.length > 0) {
        adoptedSummary.push({ modelName, sentences: adoptedSentences });
      } else if (rejectedSentences.length === 0 && error && !parts.some(text => text.includes(modelName))) {
        parts.push(`${modelName} 응답은 "${error}"로 인해 참고용으로만 사용했습니다.`);
      } else if (rejectedSentences.length === 0 && accuracy && accuracy.trim() && accuracy.trim() !== '✅') {
        parts.push(`${modelName} 응답은 "${accuracy.trim()}"로 표시되어 참고용으로만 활용했습니다.`);
      }
    });
  }

  if (adoptedSummary.length > 0) {
    const uniqueModels = adoptedSummary.map(item => item.modelName);
    const joinNames = (names) => {
      if (names.length === 1) return names[0];
      if (names.length === 2) return `${names[0]}와 ${names[1]}`;
      return `${names[0]}, ${names[1]} 등 ${names.length}개 모델`;
    };

    parts.push(`${joinNames(uniqueModels)}의 정보가 검증 소스와 일치하여 채택되었습니다.`);

    const highlightSentences = adoptedSummary
      .slice(0, 2)
      .map(item => {
        const sentence = item.sentences[0];
        if (!sentence) return null;
        const cleaned = sentence.replace(/\s+/g, ' ').trim().replace(/["“”]/g, '');
        const quoted = cleaned.endsWith('.') ? cleaned.slice(0, -1) : cleaned;
        return `${item.modelName}는 "${quoted}"라고 설명했습니다`;
      })
      .filter(Boolean);

    if (highlightSentences.length > 0) {
      if (highlightSentences.length === 1) {
        parts.push(`${highlightSentences[0]}.`);
      } else {
        parts.push(`${highlightSentences[0]} 그리고 ${highlightSentences[1]}.`);
      }
    }
  }

  if (parts.length === 0) {
    if (sourceUsed) {
      parts.push(`${title} 내용을 바탕으로 최적의 답변을 구성했습니다.`);
    } else {
      parts.push('여러 모델의 공통 정보를 조합해 최적의 답변을 구성했습니다.');
    }
  }

  return parts.join(' ');
};

// 백엔드 모델 이름을 프론트엔드 모델 ID로 변환
const backendToFrontendModelId = (backendName) => {
  if (!backendName) return '';
  
  const originalName = String(backendName);
  const normalized = originalName.toLowerCase().replace(/\s+/g, '-').replace(/_+/g, '-');
  
  // 백엔드 모델 이름 -> 프론트엔드 모델 ID 매핑
  const modelMapping = {
    // GPT 모델
    'gpt-5': 'gpt-5',
    'gpt-5-mini': 'gpt-5-mini',
    'gpt-4.1': 'gpt-4.1',
    'gpt-4.1-mini': 'gpt-4.1-mini',
    'gpt-4o': 'gpt-4o',
    'gpt-4o-mini': 'gpt-4o-mini',
    'gpt-4-turbo': 'gpt-4-turbo',
    'gpt-3.5-turbo': 'gpt-3.5-turbo',
    
    // Gemini 모델
    'gemini-2.5-pro': 'gemini-2.5-pro',
    'gemini-2.5-flash': 'gemini-2.5-flash',
    'gemini-2.0-flash-exp': 'gemini-2.0-flash-exp',
    'gemini-2.0-flash-lite': 'gemini-2.0-flash-lite',
    
    // Claude 모델
    'claude-4-opus': 'claude-4-opus',
    'claude-3.7-sonnet': 'claude-3.7-sonnet',
    'claude-3.5-sonnet': 'claude-3.5-sonnet',
    'claude-3.5-haiku': 'claude-3.5-haiku',
    'claude-3-opus': 'claude-3-opus',
    
    // Clova 모델 (다양한 형식 지원)
    'hcx-003': 'clova-hcx-003',
    'hcx-dash-001': 'clova-hcx-dash-001',
    'hyperclova-x-hcx-003': 'clova-hcx-003',
    'hyperclova-x-hcx-dash-001': 'clova-hcx-dash-001',
  };
  
  // 직접 매핑이 있으면 사용
  if (modelMapping[normalized]) {
    return modelMapping[normalized];
  }
  
  // Clova 모델 특별 처리 (HCX-로 시작하는 경우, 다양한 형식 지원)
  if (normalized.includes('hcx-003')) {
    return 'clova-hcx-003';
  }
  if (normalized.includes('hcx-dash-001') || normalized.includes('hcx-dash')) {
    return 'clova-hcx-dash-001';
  }
  if (normalized.startsWith('hcx-')) {
    return `clova-${normalized}`;
  }
  
  // 기본 정규화 반환
  return normalized;
};

const AIAnalysisModal = ({ isOpen, onClose, analysisData, selectedModels = [] }) => {
  if (!isOpen) return null;

  // analysisData 구조 변경에 대응
  let rawAnalysisData = analysisData?.analysisData || analysisData || {};
  const verificationSource = analysisData?.verificationSource || null;
  const providedRationale = typeof analysisData?.rationale === 'string' ? analysisData.rationale.trim() : '';
  const rationale = providedRationale || buildFallbackRationale(rawAnalysisData, verificationSource);

  // selectedModels를 정규화된 모델 ID로 변환
  const selectedModelSet = new Set((selectedModels || []).map(normalizeModelName));
  const shouldFilter = selectedModelSet.size > 0;
  
  console.log('🔍 AIAnalysisModal - selectedModels:', selectedModels);
  console.log('🔍 AIAnalysisModal - selectedModelSet:', Array.from(selectedModelSet));
  console.log('🔍 AIAnalysisModal - rawAnalysisData keys:', Object.keys(rawAnalysisData));
  console.log('🔍 AIAnalysisModal - rawAnalysisData 전체:', JSON.stringify(rawAnalysisData, null, 2));
  
  // 백엔드 데이터 형식 변환 (채택된_정보, 제외된_정보 -> adopted, rejected)
  // 백엔드: { "GPT-4o-Mini": { "정확성": "✅", "채택된_정보": [...], "제외된_정보": [...] } }
  // 프론트엔드: { "GPT-4o-Mini": { "accuracy": "✅", "adopted": [...], "rejected": [...] } }
  const actualAnalysisData = {};
  
  // rawAnalysisData의 모든 모델 처리
  Object.entries(rawAnalysisData).forEach(([modelName, data]) => {
    if (data && typeof data === 'object') {
      // 백엔드 모델 이름을 프론트엔드 모델 ID로 변환
      const frontendModelId = backendToFrontendModelId(modelName);
      const normalizedBackendName = normalizeModelName(frontendModelId);
      
      console.log(`🔍 모델 매칭 체크: "${modelName}" -> "${frontendModelId}" -> "${normalizedBackendName}"`);
      console.log(`🔍 selectedModelSet:`, Array.from(selectedModelSet));
      console.log(`🔍 selectedModelSet에 포함? ${selectedModelSet.has(normalizedBackendName)}`);
      
      if (shouldFilter && !selectedModelSet.has(normalizedBackendName)) {
        console.log(`❌ 필터링됨: ${modelName} (${normalizedBackendName})`);
        return;
      }
      
      console.log(`✅ 포함됨: ${modelName}`);

      actualAnalysisData[modelName] = {
        accuracy: data.정확성 || data.accuracy || '✅',
        confidence: parseInt(data.신뢰도 || data.confidence || '0'),
        adopted: data.채택된_정보 || data.adopted || [],
        rejected: data.제외된_정보 || data.rejected || [],
        error: data.오류 || data.error || '정확한 정보 제공'
      };
    }
  });
  
  // selectedModels에 있지만 rawAnalysisData에 없는 모델 확인
  if (shouldFilter) {
    const missingModels = [];
    selectedModels.forEach(selectedModel => {
      const normalizedSelected = normalizeModelName(selectedModel);
      let found = false;
      
      // rawAnalysisData의 모든 키를 확인
      for (const backendModelName of Object.keys(rawAnalysisData)) {
        const frontendModelId = backendToFrontendModelId(backendModelName);
        const normalizedBackend = normalizeModelName(frontendModelId);
        if (normalizedBackend === normalizedSelected) {
          found = true;
          break;
        }
      }
      
      if (!found) {
        missingModels.push(selectedModel);
        console.warn(`⚠️ 선택된 모델 "${selectedModel}" (정규화: "${normalizedSelected}")이 rawAnalysisData에 없습니다!`);
      }
    });
    
    if (missingModels.length > 0) {
      console.error(`❌ 누락된 모델들:`, missingModels);
      console.error(`❌ rawAnalysisData에 있는 모델들:`, Object.keys(rawAnalysisData));
    }
  }
  
  console.log('AIAnalysisModal - actualAnalysisData:', JSON.stringify(actualAnalysisData, null, 2));
  console.log('AIAnalysisModal - rationale:', rationale);
  console.log('AIAnalysisModal - Object.keys(actualAnalysisData):', Object.keys(actualAnalysisData));

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
      <div className="bg-white rounded-lg w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Header - 상단 고정 */}
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-semibold text-gray-800">각 AI 분석 결과</h2>
            <p className="text-gray-500 text-sm mt-1">각 LLM 모델의 상세 검증 결과</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl font-light transition-colors"
          >
            ×
          </button>
        </div>

        {/* Content - 스크롤 가능 */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {/* 분석 근거 섹션 - 강조 표시 */}
          {rationale && (
            <div className="border-2 border-blue-400 rounded-lg p-6 bg-blue-50 shadow-lg">
              <h3 className="text-xl font-bold text-blue-900 mb-4 flex items-center">
                <TrendingUp className="mr-3 text-blue-600" size={24} />
                📊 최적 답변 생성 근거
              </h3>
              <div className="bg-white rounded-lg p-4 border border-blue-200 shadow-sm">
                <p className="text-gray-800 leading-relaxed whitespace-pre-line text-base font-medium">
                  {rationale}
                </p>
              </div>
            </div>
          )}
          
          {/* 각 AI 모델별 분석 */}
          {Object.entries(actualAnalysisData).map(([aiName, analysis], index) => (
            <div
              key={aiName}
              className="border border-gray-200 rounded-lg p-5 bg-white hover:shadow-md transition-shadow"
            >
              {/* AI Name Header */}
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-100">
                <h3 className="text-lg font-semibold text-gray-800">
                  {aiName}
                </h3>
                <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg">
                  <TrendingUp size={16} className="text-gray-600" />
                  <span className="font-semibold text-gray-700 text-sm">
                    신뢰도: {analysis.confidence}%
                  </span>
                </div>
              </div>

              {/* Analysis Grid */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* 채택된 정보 */}
                <div className="border border-gray-200 bg-green-50 p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <ThumbsUp className="text-green-600" size={18} />
                    <h4 className="font-semibold text-gray-800 text-sm">참고한 정보</h4>
                  </div>
                  {analysis.adopted && analysis.adopted.length > 0 ? (
                    <ul className="space-y-2">
                      {analysis.adopted.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                          <span className="text-green-600 mt-0.5 font-bold">✓</span>
                          <div className="leading-relaxed prose prose-sm prose-slate">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {item}
                            </ReactMarkdown>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-gray-500 italic">채택된 정보가 없습니다</p>
                  )}
                </div>

                {/* 틀린 정보 */}
                <div className="border border-gray-200 bg-red-50 p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <ThumbsDown className="text-red-600" size={18} />
                    <h4 className="font-semibold text-gray-800 text-sm">제외한 정보</h4>
                  </div>
                  {analysis.rejected && analysis.rejected.length > 0 ? (
                    <ul className="space-y-2">
                      {analysis.rejected.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                          <span className="text-red-600 mt-0.5 font-bold">✗</span>
                          <div className="leading-relaxed prose prose-sm prose-slate">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {item}
                            </ReactMarkdown>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-gray-500 italic">틀린 정보가 없습니다</p>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* 종합 분석 */}
          {Object.keys(actualAnalysisData).length > 0 && (
            <div className="border-t border-gray-200 pt-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                  <TrendingUp className="text-gray-600" size={16} />
                  📊 종합 분석
                </h3>
                <p className="text-sm text-gray-600">
                  총 {Object.keys(actualAnalysisData).length}개의 AI 모델이 분석에 참여했습니다.
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  평균 신뢰도: {(
                    Object.values(actualAnalysisData).reduce((sum, a) => sum + (a.confidence || 0), 0) / 
                    Object.keys(actualAnalysisData).length
                  ).toFixed(0)}%
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AIAnalysisModal;