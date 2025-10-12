import React from 'react';
import { CheckCircle, XCircle, TrendingUp, ThumbsUp, ThumbsDown, AlertCircle } from 'lucide-react';

const AIAnalysisModal = ({ isOpen, onClose, analysisData }) => {
  if (!isOpen) return null;

  // analysisData 구조 변경에 대응
  const actualAnalysisData = analysisData?.analysisData || analysisData || {};
  const rationale = analysisData?.rationale || "";

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
      <div className="bg-white rounded-lg p-6 w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex justify-between items-center mb-6 pb-4 border-b border-gray-200">
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

        {/* Content */}
        <div className="space-y-6">
          {/* 분석 근거 섹션 - 강조 표시 */}
          {rationale && (
            <div className="border-2 border-blue-300 rounded-lg p-6 bg-blue-50 shadow-sm">
              <h3 className="text-xl font-bold text-blue-800 mb-4 flex items-center">
                <TrendingUp className="mr-2 text-blue-600" size={22} />
                📊 최적 답변 생성 근거
              </h3>
              <p className="text-gray-800 leading-relaxed whitespace-pre-line text-base">
                {rationale}
              </p>
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
                    <h4 className="font-semibold text-gray-800 text-sm">채택된 정보</h4>
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

                {/* 제외된 정보 */}
                <div className="border border-gray-200 bg-red-50 p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <ThumbsDown className="text-red-600" size={18} />
                    <h4 className="font-semibold text-gray-800 text-sm">제외된 정보</h4>
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
                    <p className="text-sm text-gray-500 italic">제외된 정보가 없습니다</p>
                  )}
                </div>
              </div>

              {/* 정확한 정보 & 틀린 정보 */}
              <div className="grid md:grid-cols-2 gap-4 mt-4">
                {/* 정확한 정보 */}
                <div className="border border-gray-200 bg-white p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle className="text-green-600" size={18} />
                    <h4 className="font-semibold text-gray-700 text-sm">정확한 정보</h4>
                  </div>
                  {analysis.pros && analysis.pros.length > 0 ? (
                    <ul className="space-y-2">
                      {analysis.pros.map((pro, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                          <span className="text-green-500 mt-0.5">✓</span>
                          <span className="leading-relaxed">{pro}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-gray-500">
                      {analysis.accuracy === '✅' ? '정확한 정보 제공' : '정보 없음'}
                    </p>
                  )}
                </div>

                {/* 틀린 정보 */}
                <div className="border border-gray-200 bg-white p-4 rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle className="text-red-600" size={18} />
                    <h4 className="font-semibold text-gray-700 text-sm">틀린 정보</h4>
                  </div>
                  {analysis.cons && analysis.cons.length > 0 && 
                   analysis.cons[0] !== '정확한 정보 제공' && 
                   analysis.cons[0] !== '없음' ? (
                    <ul className="space-y-2">
                      {analysis.cons.map((con, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                          <span className="text-red-500 mt-0.5">✗</span>
                          <span className="leading-relaxed">{con}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-gray-500">틀린 정보 없음</p>
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

        {/* Close Button */}
        <div className="mt-6 pt-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors font-medium"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
};

export default AIAnalysisModal;
