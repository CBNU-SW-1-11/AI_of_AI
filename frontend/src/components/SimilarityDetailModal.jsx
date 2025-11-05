import React, { useState } from "react";
import { AlertTriangle, Check, Globe, List, Link as LinkIcon, BarChart4, Copy } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// 코드 복사 컴포넌트 (ChatBox.jsx와 동일)
const CodeBlock = ({ children, className, ...props }) => {
  const [copied, setCopied] = useState(false);
  
  const codeString = typeof children === 'string' ? children : 
    (Array.isArray(children) ? children.join('') : String(children));
  
  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(codeString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('복사 실패:', err);
    }
  };
  
  const isInline = !className || !className.includes('language-');
  
  if (isInline) {
    return <code className={className} {...props}>{children}</code>;
  }
  
  // 언어 이름 추출 (예: "language-python" -> "python")
  const languageMatch = className?.match(/language-(\w+)/);
  const language = languageMatch ? languageMatch[1] : '';
  
  return (
    <div className="relative group" style={{ marginBottom: '1rem' }}>
      <div className="relative">
        {/* 언어 레이블 (왼쪽 상단) */}
        {language && (
          <div className="absolute top-2 left-2 px-2 py-1 text-xs font-semibold text-gray-900 z-10">
            {language}
          </div>
        )}
        {/* 복사 버튼 (오른쪽 상단) */}
        <button
          onClick={handleCopy}
          className="absolute top-2 right-2 p-1.5 rounded bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors z-10"
          title={copied ? "복사됨!" : "코드 복사"}
        >
          {copied ? (
            <Check size={14} className="text-green-600" />
          ) : (
            <Copy size={14} />
          )}
        </button>
        <pre 
          className={className} 
          {...props} 
          style={{ 
            paddingTop: language ? '2.5rem' : '1rem',
            backgroundColor: '#f3f4f6',
            color: '#1f2937'
          }}
        >
          <code style={{ color: '#1f2937' }}>{children}</code>
        </pre>
      </div>
    </div>
  );
};

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
      <div className="bg-white rounded-lg w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* 헤더 - 상단 고정 */}
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-semibold text-gray-800">유사도 분석 상세 결과</h2>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-gray-600 text-2xl font-light transition-colors"
          >
            ×
          </button>
        </div>
        
        {/* 본문 - 스크롤 가능 */}
        <div className="flex-1 overflow-y-auto px-6 py-6">

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
                          <div className="text-sm text-gray-600 leading-relaxed similarity-markdown-content">
                            <ReactMarkdown 
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code: CodeBlock,
                                pre: ({ children, ...props }) => <pre {...props}>{children}</pre>
                              }}
                            >
                              {clusters.representativeResponses[idx].response}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 italic">유사 그룹 데이터가 없습니다.</p>
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
    </div>
  );
};

export default SimilarityDetailModal;

// 마크다운 스타일 추가
const markdownStyles = `
  .similarity-markdown-content {
    line-height: 1.6;
  }
  
  .similarity-markdown-content h1,
  .similarity-markdown-content h2,
  .similarity-markdown-content h3,
  .similarity-markdown-content h4,
  .similarity-markdown-content h5,
  .similarity-markdown-content h6 {
    font-weight: 600;
    margin-top: 1rem;
    margin-bottom: 0.5rem;
  }
  
  .similarity-markdown-content h1 { font-size: 1.5rem; }
  .similarity-markdown-content h2 { font-size: 1.25rem; }
  .similarity-markdown-content h3 { font-size: 1.125rem; }
  
  .similarity-markdown-content p {
    margin-bottom: 0.75rem;
  }
  
  .similarity-markdown-content ul,
  .similarity-markdown-content ol {
    margin-left: 1.5rem;
    margin-bottom: 0.75rem;
  }
  
  .similarity-markdown-content li {
    margin-bottom: 0.25rem;
  }
  
  .similarity-markdown-content code {
    background-color: #f3f4f6;
    padding: 0.125rem 0.25rem;
    border-radius: 0.25rem;
    font-size: 0.875em;
  }
  
  .similarity-markdown-content pre {
    background-color: #f3f4f6;
    padding: 1rem;
    border-radius: 0.5rem;
    overflow-x: auto;
    margin-bottom: 1rem;
  }
  
  .similarity-markdown-content pre code {
    background-color: transparent;
    padding: 0;
  }
  
  .similarity-markdown-content strong {
    font-weight: 700;
    color: #1f2937;
  }
  
  .similarity-markdown-content strong * {
    font-weight: inherit;
  }
  
  .similarity-markdown-content blockquote {
    border-left: 4px solid #e5e7eb;
    padding-left: 1rem;
    margin-left: 0;
    color: #6b7280;
    font-style: italic;
  }
  
  .similarity-markdown-content a {
    color: #3b82f6;
    text-decoration: underline;
  }
  
  .similarity-markdown-content a:hover {
    color: #2563eb;
  }
  
  .similarity-markdown-content hr {
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 1rem 0;
  }
`;

// 스타일을 동적으로 추가
if (typeof document !== 'undefined') {
  const styleId = 'similarity-markdown-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = markdownStyles;
    document.head.appendChild(style);
  }
}
