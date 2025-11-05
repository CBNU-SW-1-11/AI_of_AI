import React from "react";
import { AlertTriangle, Check, Globe, BookOpen, List, Link as LinkIcon, BarChart4 } from "lucide-react";

const SimilarityDetailModal = ({ isOpen, onClose, similarityData }) => {
  if (!isOpen) return null;

  const {
    messageId,
    clusters,
    similarityMatrix,
    modelResponses,
    averageSimilarity,
    noDataAvailable,
    debugInfo,
    availableDataKeys,
    similarGroups,
    mainGroup,
    semanticTags = {},
    responseFeatures = {},
    detectedLanguages
  } = similarityData || {};

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
      <div className="bg-white rounded-lg p-6 w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* 헤더 */}
        <div className="flex justify-between items-center mb-6 pb-4 border-b border-gray-200">
          <h2 className="text-2xl font-semibold text-gray-800">유사도 분석 상세 결과</h2>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-gray-600 text-2xl font-light transition-colors"
          >
            ×
          </button>
        </div>

        {/* 데이터 없음 표시 */}
        {noDataAvailable ? (
          <div className="p-4 bg-yellow-50 text-yellow-800 rounded-lg">
            <p>아직 이 메시지에 대한 유사도 분석 데이터가 준비되지 않았습니다.</p>
            <p>잠시 후 다시 시도해주세요.</p>
            <p className="mt-4 text-sm font-semibold">디버그 정보:</p>
            <pre className="bg-gray-100 p-2 rounded text-xs overflow-auto mt-2">
              {JSON.stringify({ messageId, debugInfo, availableDataKeys }, null, 2)}
            </pre>
          </div>
        ) : (
          <div className="space-y-8">

            {/* 유사 그룹 */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                <BarChart4 className="mr-2 text-gray-600" size={20} />
                유사 그룹
              </h3>
              {clusters && clusters.similarGroups && clusters.similarGroups.length > 0 ? (
                <div className="space-y-4">
                  {clusters.similarGroups.map((group, idx) => (
                    <div key={idx} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="font-medium text-gray-800">
                          {idx === 0 ? "주요 그룹" : idx === 1 ? "부 그룹" : `그룹 ${idx + 1}`}
                        </h4>
                        <span className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
                          {Array.isArray(group) ? group.join(", ") : group}
                        </span>
                      </div>
                      {clusters.representativeResponses && clusters.representativeResponses[idx] && (
                        <div className="bg-gray-50 p-3 rounded border-l-4 border-gray-300">
                          <p className="text-sm font-medium text-gray-700 mb-1">대표 응답:</p>
                          <p className="text-sm text-gray-600 leading-relaxed">
                            {clusters.representativeResponses[idx].response}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 italic">유사 그룹 데이터가 없습니다.</p>
              )}
            </div>

            {/* 모델별 응답 */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                <BookOpen className="mr-2 text-gray-600" size={20} />
                모델별 응답
              </h3>
              {modelResponses && Object.keys(modelResponses).length > 0 ? (
                <div className="grid grid-cols-1 gap-4">
                  {Object.entries(modelResponses).map(([model, response]) => (
                    <div key={model} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="font-medium text-gray-800">{model.toUpperCase()}</h4>
                        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                          {response.length}자
                        </span>
                      </div>
                      <p className="text-gray-600 leading-relaxed">{response}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 italic">모델별 응답 데이터가 없습니다.</p>
              )}
            </div>

            {/* 평균 유사도 */}
            {averageSimilarity && (
              <div className="mb-8">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <Check className="mr-2 text-gray-600" size={20} />
                  전체 유사도
                </h3>
                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-gray-700">평균 유사도</span>
                    <span className="text-lg font-semibold text-gray-800">
                      {(averageSimilarity * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div 
                      className="bg-gray-600 h-3 rounded-full transition-all duration-300" 
                      style={{ width: `${averageSimilarity * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            )}



            {/* 유사도 행렬 */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                <BarChart4 className="mr-2 text-gray-600" size={20} />
                유사도 행렬
              </h3>
              {similarityMatrix ? (
                <div className="overflow-x-auto border border-gray-200 rounded-lg">
                  <table className="min-w-full">
                    <thead>
                      <tr className="bg-gray-50 border-b border-gray-200">
                        <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">모델</th>
                        {Object.keys(similarityMatrix).map(m => (
                          <th key={m} className="px-4 py-3 text-center text-sm font-medium text-gray-700">
                            {m.toUpperCase()}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {Object.entries(similarityMatrix).map(([m, sims]) => (
                        <tr key={m}>
                          <td className="px-4 py-3 font-medium text-gray-800 bg-gray-50">
                            {m.toUpperCase()}
                          </td>
                          {Object.values(sims).map((val, i) => {
                            const pct = parseFloat(val) * 100;
                            let textColor = "text-gray-600";
                            if (pct >= 70) textColor = "text-green-600 font-semibold";
                            else if (pct >= 50) textColor = "text-blue-600";
                            else if (pct >= 30) textColor = "text-orange-600";
                            
                            return (
                              <td key={i} className={`px-4 py-3 text-center text-sm ${textColor}`}>
                                {pct.toFixed(1)}%
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-500 italic">유사도 행렬 데이터가 없습니다.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SimilarityDetailModal;
