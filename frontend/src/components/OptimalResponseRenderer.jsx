import React, { useState, useRef, useEffect, useMemo } from 'react';
import { api } from '../utils/api';
import AIAnalysisModal from './AIAnalysisModal';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check } from 'lucide-react';

// 코드 복사 컴포넌트
const CodeBlock = ({ children, className, ...props }) => {
  const [copied, setCopied] = useState(false);
  const codeRef = useRef(null);
  
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
  
  return (
    <div className="relative group" style={{ marginBottom: '1rem' }}>
      <pre 
        className={className} 
        {...props} 
        ref={codeRef}
        style={{
          backgroundColor: '#f3f4f6',
          color: '#1f2937'
        }}
      >
        <code style={{ color: '#1f2937' }}>{children}</code>
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-2 rounded bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors"
        title={copied ? "복사됨!" : "코드 복사"}
        style={{ 
          zIndex: 10
        }}
      >
        {copied ? (
          <Check size={14} className="text-green-600" />
        ) : (
          <Copy size={14} />
        )}
      </button>
    </div>
  );
};

// 전체 복사 컴포넌트 (아이콘만)
const CopyAllButton = ({ content }) => {
  const [copied, setCopied] = useState(false);
  
  const handleCopyAll = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('전체 복사 실패:', err);
    }
  };
  
  if (!content || content.trim().length === 0) return null;
  
  return (
    <button
      onClick={handleCopyAll}
      className="flex items-center justify-center p-2 rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors mt-2"
      title={copied ? "복사됨!" : "전체 복사"}
    >
      {copied ? (
        <Check size={16} className="text-green-600" />
      ) : (
        <Copy size={16} className="text-gray-600" />
      )}
    </button>
  );
};

const FRAME_PREVIEW_LIMIT = 3;

const FramePreviewList = ({ frames, onFrameClick, maxInitial = FRAME_PREVIEW_LIMIT }) => {
  const safeFrames = useMemo(() => {
    if (!Array.isArray(frames)) return [];
    return [...frames].sort((a, b) => {
      const scoreDiff = (b?.relevance_score ?? 0) - (a?.relevance_score ?? 0);
      if (scoreDiff !== 0) return scoreDiff;
      return (a?.timestamp ?? 0) - (b?.timestamp ?? 0);
    });
  }, [frames]);

  const limitedCount = Math.min(safeFrames.length, maxInitial ?? safeFrames.length);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (limitedCount === 0) {
      if (currentIndex !== 0) setCurrentIndex(0);
    } else if (currentIndex >= limitedCount) {
      setCurrentIndex(0);
    }
  }, [limitedCount, currentIndex]);

  if (limitedCount === 0) return null;

  const limitedFrames = safeFrames.slice(0, limitedCount);
  const total = limitedFrames.length;
  const safeIndex = Math.min(currentIndex, total - 1);
  const currentFrame = limitedFrames[safeIndex];

  const goPrev = () => setCurrentIndex(prev => (prev - 1 + total) % total);
  const goNext = () => setCurrentIndex(prev => (prev + 1) % total);
  
  return (
    <div className="relative">
      <div
        className="frame-card cursor-pointer hover:border-blue-300 transition-colors duration-200"
        onClick={() => onFrameClick && onFrameClick(currentFrame)}
      >
        <div className="relative">
          <img
            src={`${api.defaults.baseURL}${currentFrame.image_url}`}
            alt={`프레임 ${currentFrame.image_id}`}
            className="frame-image"
            onError={(e) => {
              console.error(`프레임 이미지 로드 실패: ${currentFrame.image_url}`);
              e.target.style.display = 'none';
            }}
          />
          {total > 1 && (
            <>
              <button
                type="button"
                className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-700 rounded-full p-1 shadow transition"
                onClick={(e) => {
                  e.stopPropagation();
                  goPrev();
                }}
              >
                ‹
              </button>
              <button
                type="button"
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-700 rounded-full p-1 shadow transition"
                onClick={(e) => {
                  e.stopPropagation();
                  goNext();
                }}
              >
                ›
              </button>
            </>
          )}
        </div>
        <div className="frame-info">
          <span className="frame-timestamp">⏰ {currentFrame.timestamp.toFixed(1)}초</span>
          <span className="frame-score">🎯 {currentFrame.relevance_score}점</span>
        </div>
        <div className="flex justify-between items-center px-2 pb-2 text-xs text-gray-500">
          <span>프레임 #{currentFrame.image_id}</span>
          <span>{safeIndex + 1}/{total}</span>
        </div>
        <div className="frame-tags">
          {currentFrame.persons && currentFrame.persons.length > 0 && (
            <span className="frame-tag person-tag">
              👤 사람 {currentFrame.persons.length}명
            </span>
          )}
          {currentFrame.objects && currentFrame.objects.length > 0 && (
            <span className="frame-tag object-tag">
              📦 객체 {currentFrame.objects.length}개
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

const OptimalResponseRenderer = ({ content, relevantFrames, onFrameClick, similarityData, selectedModels = [] }) => {
  const [isAnalysisModalOpen, setIsAnalysisModalOpen] = useState(false);
  const parseOptimalResponse = (text) => {
    if (!text || typeof text !== 'string') return {};

    const normalized = text.replace(/\r\n/g, '\n');
    const sections = {};
    const lines = normalized.split('\n');
    let currentSection = null;
    let buffer = [];

    const commitSection = () => {
      if (!currentSection) return;
      const content = buffer.join('\n').trim();
      if (content) {
        sections[currentSection] = content;
      }
      buffer = [];
    };

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        if (currentSection) buffer.push('');
        continue;
      }

      // 최적의 답변 섹션 감지
      if (
        trimmed.match(/^(##\s*)?(🎯\s*)?(최적의?\s*답변|통합\s*답변|정확한\s*답변)/i) ||
        trimmed.match(/^\*\*(최적의?\s*답변|최적답변):\*\*/i)
      ) {
        commitSection();
        currentSection = 'integrated';
        continue;
      }
      // 답변 생성 근거 섹션 감지 (채팅 창에서 제외)
      else if (
        trimmed.match(/^(##\s*)?(📊\s*)?답변\s*생성\s*근거/i) ||
        trimmed.match(/^\*\*(📊\s*)?답변\s*생성\s*근거:\*\*/i) ||
        trimmed.match(/^(##\s*)?(📝\s*)?분석\s*근거/i) ||
        trimmed.match(/^(##\s*)?(🔍\s*)?검증\s*결과/i) ||
        trimmed.match(/^\*\*검증\s*결과:\*\*/i)
      ) {
        commitSection();
        currentSection = 'rationale'; // 모달에서만 사용, 채팅 창에서는 렌더링 안 함
        continue;
      }
      // 각 LLM 검증 결과 섹션 감지 (채팅 창에서 제외)
      else if (
        trimmed.match(/^(##\s*)?(📊\s*)?각\s*(AI|LLM)\s*(검증\s*결과|분석)/i) ||
        trimmed.match(/^\*\*각\s*(AI|LLM)\s*(검증\s*결과|분석):\*\*/i)
      ) {
        commitSection();
        currentSection = 'analysis'; // 모달에서만 사용, 채팅 창에서는 렌더링 안 함
        continue;
      }
      // 최종 추천 섹션
      else if (
        trimmed.match(/^(##\s*)?(🏆\s*)?최종\s*추천/i)
      ) {
        commitSection();
        currentSection = 'recommendation';
        continue;
      }
      // 추가 인사이트 섹션
      else if (
        trimmed.match(/^(##\s*)?(💡\s*)?추가\s*인사이트/i) ||
        trimmed.match(/^(##\s*)?(⚠️\s*)?수정된\s*정보/i)
      ) {
        commitSection();
        currentSection = 'insights';
        continue;
      }

      if (currentSection) {
        buffer.push(line);
      } else {
        // 아직 섹션을 만나기 전의 내용은 통합 답변으로 간주
        currentSection = 'integrated';
        buffer.push(line);
      }
    }

    commitSection();

    if (!sections.integrated && normalized.trim()) {
      sections.integrated = normalized.trim();
    }

    return sections;
  };

  const parseAIAnalysis = (analysisText) => {
    const analyses = {};
    const lines = analysisText.split('\n');
    let currentAI = '';
    let currentAnalysis = { pros: [], cons: [] };
    
    for (const line of lines) {
      const trimmedLine = line.trim();

      if (/^(?:###|####)\s+/.test(trimmedLine)) {
        if (currentAI) analyses[currentAI] = currentAnalysis;
        currentAI = trimmedLine.replace(/^(?:###|####)\s+/, '').trim();
        currentAnalysis = { pros: [], cons: [] };
      } else if (trimmedLine.includes('- 장점:')) {
        currentAnalysis.pros.push(trimmedLine.replace('- 장점:', '').trim());
      } else if (trimmedLine.includes('- 단점:')) {
        currentAnalysis.cons.push(trimmedLine.replace('- 단점:', '').trim());
      } else if (trimmedLine.startsWith('-')) {
        currentAnalysis.pros.push(trimmedLine.slice(1).trim());
      }
    }
    
    if (currentAI) analyses[currentAI] = currentAnalysis;
    return analyses;
  };

  if (!content || typeof content !== 'string') {
    return (
      <div className="optimal-response-container">
        <div className="optimal-section integrated-answer">
          <h3 className="section-title">최적 답변</h3>
          <div className="section-content">최적의 답변을 생성 중입니다...</div>
        </div>
      </div>
    );
  }

  const sections = parseOptimalResponse(content);
  console.log('OptimalResponseRenderer - parsed sections:', sections);
  const analysisData = sections.analysis ? parseAIAnalysis(sections.analysis) : {};
  const hasStructuredAnalysis = analysisData && Object.keys(analysisData).some(key => {
    const value = analysisData[key];
    return value && (value.pros.length > 0 || value.cons.length > 0);
  });
  
  // 헤더가 없는 경우 처리
  if (!sections.integrated && content.trim()) {
    // '---' 구분자 이전의 내용을 메인 답변으로 사용
    const mainContent = content.split('---')[0].trim();
    if (mainContent) {
      sections.integrated = mainContent;
    } else {
      sections.integrated = content.trim();
    }
  }

  return (
    <div className="optimal-response-container">
      {sections.integrated && (
        <div className="optimal-section integrated-answer">
          <h3 className="section-title">최적 답변</h3>
          <div className="section-content">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
                pre: ({ children, ...props }) => <pre {...props}>{children}</pre>
              }}
            >
              {sections.integrated}
            </ReactMarkdown>
            <CopyAllButton content={sections.integrated} />
          </div>
        </div>
      )}
      
      {sections.recommendation && (
        <div className="optimal-section recommendation-section">
          <h3 className="section-title">최종 추천</h3>
          <div className="section-content">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
                pre: ({ children, ...props }) => <pre {...props}>{children}</pre>
              }}
            >
              {sections.recommendation}
            </ReactMarkdown>
            <CopyAllButton content={sections.recommendation} />
          </div>
        </div>
      )}
      
      {sections.insights && (
        <div className="optimal-section insights-section">
          <h3 className="section-title">추가 인사이트</h3>
          <div className="section-content">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
                pre: ({ children, ...props }) => <pre {...props}>{children}</pre>
              }}
            >
              {sections.insights}
            </ReactMarkdown>
            <CopyAllButton content={sections.insights} />
          </div>
        </div>
      )}

      {relevantFrames && relevantFrames.length > 0 && (
        <div className="optimal-section frames-section">
          <h3 className="section-title">📸 관련 프레임</h3>
          <FramePreviewList frames={relevantFrames} onFrameClick={onFrameClick} />
        </div>
      )}

      {/* AI 분석 모달 */}
      {similarityData && (
        <AIAnalysisModal
          isOpen={isAnalysisModalOpen}
          onClose={() => setIsAnalysisModalOpen(false)}
          similarityData={similarityData}
          selectedModels={selectedModels}
        />
      )}
    </div>
  );
};

export default OptimalResponseRenderer;