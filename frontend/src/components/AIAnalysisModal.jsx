import React from 'react';
import { CheckCircle, XCircle, TrendingUp, ThumbsUp, ThumbsDown } from 'lucide-react';

const AIAnalysisModal = ({ isOpen, onClose, analysisData }) => {
  if (!isOpen) return null;

  // analysisData 구조 변경에 대응
  let rawAnalysisData = analysisData?.analysisData || analysisData || {};
  const rationale = analysisData?.rationale || "";
  
  // 백엔드 데이터 형식 변환 (채택된_정보, 제외된_정보 -> adopted, rejected)
  // 백엔드: { "GPT-4o-Mini": { "정확성": "✅", "채택된_정보": [...], "제외된_정보": [...] } }
  // 프론트엔드: { "GPT-4o-Mini": { "accuracy": "✅", "adopted": [...], "rejected": [...] } }
  const actualAnalysisData = {};
  Object.entries(rawAnalysisData).forEach(([modelName, data]) => {
    if (data && typeof data === 'object') {
      actualAnalysisData[modelName] = {
        accuracy: data.정확성 || data.accuracy || '✅',
        confidence: parseInt(data.신뢰도 || data.confidence || '0'),
        adopted: data.채택된_정보 || data.adopted || [],
        rejected: data.제외된_정보 || data.rejected || [],
        error: data.오류 || data.error || '정확한 정보 제공'
      };
    }
  });
  
  console.log('AIAnalysisModal - rawAnalysisData:', JSON.stringify(rawAnalysisData, null, 2));
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
                <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                  {analysis.accuracy === '✅' ? (
                    <CheckCircle className="text-green-600" size={22} />
                  ) : (
                    <XCircle className="text-red-600" size={22} />
                  )}
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
                          <span className="leading-relaxed">{item}</span>
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
                          <span className="leading-relaxed">{item}</span>
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
