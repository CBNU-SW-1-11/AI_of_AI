import React, { useState, useEffect, useRef } from "react";
import { Send, CirclePlus, Image as ImageIcon, File as FileIcon, X, BarChart3, Video, Brain, Copy, Check, RotateCw } from "lucide-react";
import { useChat } from "../context/ChatContext";
import SimilarityDetailModal from "./SimilarityDetailModal";
import AIAnalysisModal from "./AIAnalysisModal";
import { api } from "../utils/api";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
          ref={codeRef} 
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

// 반응형 표 컴포넌트
const ResponsiveTable = ({ children, ...props }) => {
  return (
    <div style={{ 
      width: '100%', 
      overflowX: 'auto', 
      marginBottom: '1rem',
      borderRadius: '8px',
      border: '1px solid #e5e7eb'
    }}>
      <table {...props} style={{ 
        width: '100%', 
        borderCollapse: 'collapse',
        fontSize: '0.875rem',
        minWidth: 'max-content'
      }}>
        {children}
      </table>
    </div>
  );
};

const TableHead = ({ children, ...props }) => (
  <thead {...props} style={{ backgroundColor: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
    {children}
  </thead>
);

const TableBody = ({ children, ...props }) => (
  <tbody {...props}>
    {children}
  </tbody>
);

const TableRow = ({ children, ...props }) => (
  <tr {...props} style={{ borderBottom: '1px solid #e5e7eb' }}>
    {children}
  </tr>
);

const TableHeader = ({ children, ...props }) => (
  <th {...props} style={{ 
    padding: '12px 16px', 
    textAlign: 'left', 
    fontWeight: '600',
    color: '#374151',
    whiteSpace: 'nowrap'
  }}>
    {children}
  </th>
);

const TableCell = ({ children, ...props }) => (
  <td {...props} style={{ 
    padding: '12px 16px', 
    color: '#6b7280',
    verticalAlign: 'top'
  }}>
    {children}
  </td>
);

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

// Optimal Response Renderer Component
const OptimalResponseRenderer = ({ content }) => {
  const parseOptimalResponse = (text) => {
    if (!text || typeof text !== 'string') {
      return {};
    }
    
    const sections = {};
    const lines = text.split('\n');
    let currentSection = '';
    let currentContent = [];
    
    for (const line of lines) {
      const trimmedLine = line.trim();
      
      // 최적의 답변 섹션 감지
      if (
        trimmedLine.match(/^(##\s*)?(🎯\s*)?(최적의?\s*답변|통합\s*답변|정확한\s*답변)/i) ||
        trimmedLine.match(/^\*\*(최적의?\s*답변|최적답변):\*\*/i)
      ) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'integrated';
        currentContent = [];
      } 
      // 답변 생성 근거 섹션 감지 (채팅 창에서 제외)
      else if (
        trimmedLine.match(/^(##\s*)?(📊\s*)?답변\s*생성\s*근거/i) ||
        trimmedLine.match(/^\*\*(📊\s*)?답변\s*생성\s*근거:\*\*/i) ||
        trimmedLine.match(/^(##\s*)?(📝\s*)?분석\s*근거/i) ||
        trimmedLine.match(/^(##\s*)?(🔍\s*)?검증\s*결과/i) ||
        trimmedLine.match(/^\*\*검증\s*결과:\*\*/i)
      ) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'rationale'; // 모달에서만 사용, 채팅 창에서는 렌더링 안 함
        currentContent = [];
      } 
      // 각 LLM 검증 결과 섹션 감지 (채팅 창에서 제외)
      else if (
        trimmedLine.match(/^(##\s*)?(📊\s*)?각\s*(AI|LLM)\s*(검증\s*결과|분석)/i) ||
        trimmedLine.match(/^\*\*각\s*(AI|LLM)\s*(검증\s*결과|분석):\*\*/i)
      ) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'analysis'; // 모달에서만 사용, 채팅 창에서는 렌더링 안 함
        currentContent = [];
      } 
      // 최종 추천 섹션
      else if (
        trimmedLine.match(/^(##\s*)?(🏆\s*)?최종\s*추천/i)
      ) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'recommendation';
        currentContent = [];
      } 
      // 추가 인사이트 섹션
      else if (
        trimmedLine.match(/^(##\s*)?(💡\s*)?추가\s*인사이트/i) ||
        trimmedLine.match(/^(##\s*)?(⚠️\s*)?수정된\s*정보/i)
      ) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'insights';
        currentContent = [];
      } 
      // 내용이 있는 경우에만 추가
      else if (trimmedLine !== '') {
        // 섹션이 아직 정해지지 않았다면 integrated로 시작
        if (!currentSection) {
          currentSection = 'integrated';
        }
        currentContent.push(line);
      }
    }
    
    if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
    return sections;
  };

  const parseNewAIAnalysis = (analysisText) => {
    const analyses = {};
    const lines = analysisText.split('\n');
    let currentAI = '';
    let currentAnalysis = { pros: [], cons: [], confidence: 0, warnings: [], adopted: [], rejected: [] };
    
    for (const line of lines) {
      const trimmedLine = line.trim();
      
      if (trimmedLine.startsWith('**') && (trimmedLine.endsWith(':**') || trimmedLine.endsWith('**'))) {
        if (currentAI) {
          analyses[currentAI] = currentAnalysis;
        }
        
        currentAI = trimmedLine.replace(/\*\*/g, '').replace(':**', '').replace('**', '');
        currentAnalysis = { pros: [], cons: [], confidence: 0, warnings: [], adopted: [], rejected: [] };
      } else if (trimmedLine.includes('정확성:')) {
        const accuracy = trimmedLine.replace(/.*정확성:\s*/, '').trim();
        if (accuracy === '✅') {
          currentAnalysis.pros = currentAnalysis.pros.length ? currentAnalysis.pros : ['정확한 정보 제공'];
          if (!currentAnalysis.confidence) currentAnalysis.confidence = 90;
        } else if (accuracy === '❌') {
          if (!currentAnalysis.confidence) currentAnalysis.confidence = 20;
        }
      } else if (trimmedLine.includes('오류:')) {
        const error = trimmedLine.replace(/.*오류:\s*/, '').trim();
        if (error && error !== '오류 없음') {
          currentAnalysis.cons = [error];
        }
      } else if (trimmedLine.includes('✅ 참고한 정보:')) {
        const info = trimmedLine.replace('✅ 참고한 정보:', '').trim();
        if (info && info !== '기본 정보 제공') {
          currentAnalysis.pros = info.split(',').map(i => i.trim()).filter(i => i.length > 0);
        } else {
          currentAnalysis.pros = ['기본 정보 제공'];
        }
      } else if (trimmedLine.includes('❌ 제외한 정보:')) {
        const info = trimmedLine.replace('❌제외한 정보:', '').trim();
        if (info && info !== '없음') {
          currentAnalysis.cons = info.split(',').map(i => i.trim()).filter(i => i.length > 0);
        } else {
          currentAnalysis.cons = [];
        }
      } else if (trimmedLine.includes('📊 신뢰도:')) {
        const confidenceMatch = trimmedLine.match(/📊 신뢰도:\s*(\d+)%/);
        if (confidenceMatch) {
          currentAnalysis.confidence = parseInt(confidenceMatch[1]);
        }
      } else if (trimmedLine.includes('⚠️ 충돌 경고:')) {
        const info = trimmedLine.replace('⚠️ 충돌 경고:', '').trim();
        if (info) {
          currentAnalysis.warnings = info.split(',').map(i => i.trim()).filter(i => i.length > 0);
        }
      } else if (trimmedLine.startsWith('✅ 참고한 정보:')) {
        const info = trimmedLine.replace('✅ 참고한 정보:', '').trim();
        if (info && info !== '없음' && info !== '없습니다') {
          currentAnalysis.adopted.push(info);
        }
      } else if (trimmedLine.startsWith('❌ 제외한 정보:')) {
        const info = trimmedLine.replace('❌ 제외한 정보:', '').trim();
        if (info && info !== '없음' && info !== '없습니다') {
          currentAnalysis.rejected.push(info);
        }
      }
    }
    
    if (currentAI) {
      analyses[currentAI] = currentAnalysis;
    }
    
    return analyses;
  };

  if (!content || typeof content !== 'string') {
    return (
      <div className="optimal-response-container">
        <div className="optimal-section integrated-answer">
          <h3 className="section-title">
            최적 답변
          </h3>
          <div className="section-content">
            최적의 답변을 생성 중입니다...
          </div>
        </div>
      </div>
    );
  }

  const sections = parseOptimalResponse(content);
  const analysisData = sections.analysis ? parseNewAIAnalysis(sections.analysis) : {};

  return (
    <div className="optimal-response-container">
      {sections.integrated && (
        <div className="optimal-section integrated-answer">
          <h3 className="section-title">
            최적 답변
          </h3>
          <div className="section-content">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
                pre: ({ children, ...props }) => {
                  // pre 태그는 CodeBlock에서 처리하므로 여기서는 그대로 전달
                  return <pre {...props}>{children}</pre>;
                },
                table: ResponsiveTable,
                thead: TableHead,
                tbody: TableBody,
                tr: TableRow,
                th: TableHeader,
                td: TableCell
              }}
            >
              {sections.integrated}
            </ReactMarkdown>
            <CopyAllButton content={sections.integrated} />
          </div>
        </div>
      )}
      {/* 분석 근거 및 각 AI 검증 결과는 모달에서만 표시 */}
      
      {/* 분석 모달 버튼은 유지 */}
      
      {sections.recommendation && (
        <div className="optimal-section recommendation">
          <h3 className="section-title">
            최종 추천
          </h3>
          <div className="section-content">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
                pre: ({ children, ...props }) => <pre {...props}>{children}</pre>,
                table: ResponsiveTable,
                thead: TableHead,
                tbody: TableBody,
                tr: TableRow,
                th: TableHeader,
                td: TableCell
              }}
            >
              {sections.recommendation}
            </ReactMarkdown>
            <CopyAllButton content={sections.recommendation} />
          </div>
        </div>
      )}
      
      {sections.insights && (
        <div className="optimal-section insights">
          <h3 className="section-title">
            추가 인사이트
          </h3>
          <div className="section-content">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
                pre: ({ children, ...props }) => <pre {...props}>{children}</pre>,
                table: ResponsiveTable,
                thead: TableHead,
                tbody: TableBody,
                tr: TableRow,
                th: TableHeader,
                td: TableCell
              }}
            >
              {sections.insights}
            </ReactMarkdown>
            <CopyAllButton content={sections.insights} />
          </div>
        </div>
      )}
    </div>
  );
};

const ALLOWED_FILE_EXTS = [
  ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"
];

const ChatBox = () => {
  const navigate = useNavigate();
  
  const {
    messages = {},
    sendMessage,
    isLoading,
    loadingModels = new Set(),
    selectedModels = [],
    currentConversationId
  } = useChat() || {};

  const [inputMessage, setInputMessage] = useState("");
  const messagesEndRefs = useRef({});
  const textareaRef = useRef(null);

  const [imageAttachments, setImageAttachments] = useState([]);
  const [fileAttachments, setFileAttachments] = useState([]);
  const imageInputRef = useRef(null);
  const fileInputRef = useRef(null);

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const plusBtnRef = useRef(null);

  const [similarityData, setSimilarityData] = useState({});
  const [isSimilarityModalOpen, setIsSimilarityModalOpen] = useState(false);
  const [aiAnalysisData, setAiAnalysisData] = useState({});
  const [isAIAnalysisModalOpen, setIsAIAnalysisModalOpen] = useState(false);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    
    textarea.style.height = 'auto';
    const scrollHeight = textarea.scrollHeight;
    const maxHeight = 120;
    
    if (scrollHeight > maxHeight) {
      textarea.style.height = `${maxHeight}px`;
    } else {
      textarea.style.height = `${scrollHeight}px`;
    }
  }, [inputMessage]);

  useEffect(() => {
    selectedModels.concat("optimal").forEach((modelId) => {
      if (!messagesEndRefs.current[modelId]) {
        messagesEndRefs.current[modelId] = React.createRef();
      }
    });
  }, [selectedModels]);

  useEffect(() => {
    selectedModels.concat("optimal").forEach((modelId) => {
      messagesEndRefs.current[modelId]?.current?.scrollIntoView({ behavior: "smooth" });
    });
  }, [messages, selectedModels]);

  useEffect(() => {
    const onDocClick = (e) => {
      if (!isMenuOpen) return;
      const menuEl = menuRef.current;
      const btnEl = plusBtnRef.current;
      if (menuEl && btnEl && !menuEl.contains(e.target) && !btnEl.contains(e.target)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [isMenuOpen]);

  const generateId = () => `att-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  const generateRequestId = () => `req-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;

  const readFileAsDataURL = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = reject;
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(file);
    });

  const handleImageChange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    if (!file.type?.startsWith("image/")) {
      alert("이미지 파일만 선택할 수 있어요.");
      e.target.value = "";
      return;
    }

    const url = URL.createObjectURL(file);
    setImageAttachments((prev) => [...prev, { id: generateId(), file, url }]);

    try { e.target.value = ""; } catch {}
    setIsMenuOpen(false);
  };

  const handleFileChange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    const allowedTypes = [
      'application/pdf',
      'image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/tiff'
    ];
    
    if (!allowedTypes.includes(file.type)) {
      alert("PDF 또는 이미지 파일만 업로드할 수 있습니다.");
      e.target.value = "";
      return;
    }

    const lowerName = file.name.toLowerCase();
    const allowed = ALLOWED_FILE_EXTS.some(ext => lowerName.endsWith(ext));
    if (!allowed) {
      alert(`허용되지 않는 파일 형식입니다. 허용: ${ALLOWED_FILE_EXTS.join(", ")}`);
      e.target.value = "";
      return;
    }

    setFileAttachments((prev) => [
      ...prev,
      { id: generateId(), file, name: file.name, size: file.size },
    ]);
    try { e.target.value = ""; } catch {}
    setIsMenuOpen(false);
  };

  const removeImage = (id) => {
    setImageAttachments((prev) => {
      const target = prev.find((p) => p.id === id);
      if (target?.url) {
        try { URL.revokeObjectURL(target.url); } catch {}
      }
      return prev.filter((p) => p.id !== id);
    });
  };
  
  const removeFile = (id) => {
    setFileAttachments((prev) => prev.filter((p) => p.id !== id));
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!sendMessage || !currentConversationId) return;

    const trimmed = inputMessage.trim();
    const hasAttachments = imageAttachments.length > 0 || fileAttachments.length > 0;
    if (!trimmed && !hasAttachments) return;

    const requestId = generateRequestId();

    const messageToSend = trimmed;
    const imagesToSend = [...imageAttachments];
    const filesToSend = [...fileAttachments];
    
    // 즉시 초기화 (중복 전송 방지)
    setInputMessage("");
    setImageAttachments([]);
    setFileAttachments([]);
    
    // textarea ref를 통한 강제 초기화 (한글 조합 중인 문자 제거)
    if (textareaRef.current) {
      textareaRef.current.value = "";
    }

    try {
      // 항상 Base64 방식으로 통일
      console.log('Using Base64 fallback method');
      const imagesBase64 = await Promise.all(
        imagesToSend.map(async (a) => {
          const dataUrl = await readFileAsDataURL(a.file);
          return { name: a.file.name, type: a.file.type, size: a.file.size, dataUrl };
        })
      );
      const filesBase64 = await Promise.all(
        filesToSend.map(async (a) => {
          const dataUrl = await readFileAsDataURL(a.file);
          return { name: a.file.name, type: a.file.type, size: a.file.size, dataUrl };
        })
      );

      console.log('Images Base64:', imagesBase64.length);
      console.log('Files Base64:', filesBase64.length);
      console.log('Message text:', messageToSend);

      await sendMessage(messageToSend, requestId, {
        imagesBase64,
        filesBase64,
      });

      // URL 정리
      imagesToSend.forEach((a) => {
        if (a.url) try { URL.revokeObjectURL(a.url); } catch {}
      });
    } catch (err) {
      console.error(err);
      // 에러 발생 시 복원
      setInputMessage(messageToSend);
      setImageAttachments(imagesToSend);
      setFileAttachments(filesToSend);
      
      // textarea ref도 복원
      if (textareaRef.current) {
        textareaRef.current.value = messageToSend;
      }
    }
  };

  const loadingText = isLoading ? "분석중…" : "";

  return (
    <div className="h-full w-full flex flex-col" style={{ background: "rgba(245, 242, 234, 0.4)" }}>
      <style jsx>{`
        .chat-header {
          background: rgba(245, 242, 234, 0.4);
          backdrop-filter: blur(10px);
          border-bottom: 1px solid rgba(139, 168, 138, 0.15);
          height: 60px;
        }
        .chat-column {
          background: rgba(255, 255, 255, 0.3);
          backdrop-filter: blur(5px);
        }
        .chat-container {
          height: calc(100% - 180px);
        }
        .aiofai-input-area {
          background: rgba(245, 242, 234, 0.4);
          backdrop-filter: blur(10px);
          border-top: 1px solid rgba(139, 168, 138, 0.15);
          padding: 0.75rem 1.2rem;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 0.3rem;
        }
        .aiofai-user-message {
          background: linear-gradient(135deg, #5d7c5b, #8ba88a);
          color: #ffffff;
          padding: 1.2rem 1.5rem;
          border-radius: 24px 24px 8px 24px;
          max-width: 85%;
          box-shadow: 0 8px 32px rgba(93, 124, 91, 0.3);
          font-weight: 500;
          line-height: 1.5;
          position: relative;
          min-height: 20px;
        }
        .aiofai-bot-message {
          background: rgba(255, 255, 255, 0.8);
          backdrop-filter: blur(10px);
          color: #2d3e2c;
          border: 1px solid rgba(139, 168, 138, 0.2);
          padding: 1.2rem 1.5rem;
          border-radius: 24px 24px 24px 8px;
          max-width: 85%;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
          line-height: 1.6;
          position: relative;
          min-height: 20px;
        }
        .optimal-response {
          background: rgba(255, 255, 255, 0.95) !important;
          border: 2px solid rgba(139, 168, 138, 0.3) !important;
          padding: 1.5rem !important;
          border-radius: 16px !important;
          max-width: 95% !important;
          box-shadow: 0 8px 32px rgba(139, 168, 138, 0.15) !important;
        }
        .optimal-response-container {
          width: 100%;
        }
        .optimal-section {
          margin-bottom: 1.5rem;
          padding: 1rem;
          border-bottom: 1px solid #e5e7eb;
        }
        .optimal-section:last-child {
          margin-bottom: 0;
          border-bottom: none;
        }
        .section-title {
          margin: 0 0 1rem 0;
          font-size: 1rem;
          font-weight: 600;
          color: #374151;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .section-content {
          color: #374151;
          line-height: 1.6;
          font-size: 0.95rem;
        }
        /* 마크다운 스타일 */
        .section-content h1, .section-content h2, .section-content h3, .section-content h4, .section-content h5, .section-content h6 {
          margin-top: 1.5rem;
          margin-bottom: 0.75rem;
          font-weight: 600;
          line-height: 1.25;
        }
        .section-content h1 { font-size: 1.5rem; }
        .section-content h2 { font-size: 1.25rem; }
        .section-content h3 { font-size: 1.125rem; }
        .section-content p {
          margin-bottom: 1rem;
        }
        .section-content ul, .section-content ol {
          margin-bottom: 1rem;
          padding-left: 1.5rem;
        }
        .section-content li {
          margin-bottom: 0.5rem;
        }
        .section-content code {
          background-color: #f3f4f6;
          padding: 0.125rem 0.375rem;
          border-radius: 0.25rem;
          font-size: 0.875em;
          font-family: 'Courier New', monospace;
        }
        .section-content pre {
          background-color: #f3f4f6;
          color: #1f2937;
          padding: 1rem;
          border-radius: 0.5rem;
          overflow-x: auto;
          margin-bottom: 1rem;
          position: relative;
        }
        .section-content pre code {
          background-color: transparent;
          padding: 0;
          color: inherit;
        }
        .section-content code {
          background-color: #f3f4f6;
          padding: 0.125rem 0.375rem;
          border-radius: 0.25rem;
          font-size: 0.875em;
          font-family: 'Courier New', monospace;
        }
        .section-content pre code {
          background-color: transparent;
          padding: 0;
          color: #1f2937;
        }
        .section-content blockquote {
          border-left: 4px solid #d1d5db;
          padding-left: 1rem;
          margin-left: 0;
          margin-bottom: 1rem;
          color: #6b7280;
        }
        .section-content strong {
          font-weight: 700;
          color: #1f2937;
        }
        .section-content strong * {
          font-weight: inherit;
        }
        .section-content em {
          font-style: italic;
        }
        .section-content a {
          color: #2563eb;
          text-decoration: underline;
        }
        .section-content hr {
          border: none;
          border-top: 1px solid #e5e7eb;
          margin: 1.5rem 0;
        }
        .aiofai-bot-message h1, .aiofai-bot-message h2, .aiofai-bot-message h3,
        .aiofai-bot-message h4, .aiofai-bot-message h5, .aiofai-bot-message h6 {
          margin-top: 1.5rem;
          margin-bottom: 0.75rem;
          font-weight: 600;
          line-height: 1.25;
        }
        .aiofai-bot-message h1 { font-size: 1.5rem; }
        .aiofai-bot-message h2 { font-size: 1.25rem; }
        .aiofai-bot-message h3 { font-size: 1.125rem; }
        .aiofai-bot-message p {
          margin-bottom: 1rem;
        }
        .aiofai-bot-message ul, .aiofai-bot-message ol {
          margin-bottom: 1rem;
          padding-left: 1.5rem;
        }
        .aiofai-bot-message li {
          margin-bottom: 0.5rem;
        }
        .aiofai-bot-message code {
          background-color: #f3f4f6;
          padding: 0.125rem 0.375rem;
          border-radius: 0.25rem;
          font-size: 0.875em;
          font-family: 'Courier New', monospace;
        }
        .aiofai-bot-message pre {
          background-color: #f3f4f6;
          color: #1f2937;
          padding: 1rem;
          border-radius: 0.5rem;
          overflow-x: auto;
          margin-bottom: 1rem;
          position: relative;
        }
        .aiofai-bot-message code {
          background-color: #f3f4f6;
          padding: 0.125rem 0.375rem;
          border-radius: 0.25rem;
          font-size: 0.875em;
          font-family: 'Courier New', monospace;
        }
        .aiofai-bot-message pre code {
          background-color: transparent;
          padding: 0;
          color: #1f2937;
        }
        .aiofai-bot-message blockquote {
          border-left: 4px solid #d1d5db;
          padding-left: 1rem;
          margin-left: 0;
          margin-bottom: 1rem;
          color: #6b7280;
        }
        .aiofai-bot-message strong {
          font-weight: 700;
          color: #1f2937;
        }
        .aiofai-bot-message strong * {
          font-weight: inherit;
        }
        .aiofai-bot-message em {
          font-style: italic;
        }
        .aiofai-bot-message a {
          color: #2563eb;
          text-decoration: underline;
        }
        .aiofai-bot-message hr {
          border: none;
          border-top: 1px solid #e5e7eb;
          margin: 1.5rem 0;
        }
        .analysis-grid {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        .ai-analysis-card {
          border-radius: 4px;
          padding: 1rem;
          border: 1px solid #e5e7eb;
          margin-bottom: 1rem;
          background: #f9fafb;
        }
        .confidence-value {
          font-weight: bold;
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          margin-left: 0.5rem;
        }
        .confidence-value.high {
          background-color: #dcfce7;
          color: #166534;
        }
        .confidence-value.medium {
          background-color: #fef3c7;
          color: #92400e;
        }
        .confidence-value.low {
          background-color: #fee2e2;
          color: #991b1b;
        }
        .warnings-label {
          color: #dc2626;
          font-weight: 600;
        }
        .analysis-item.warnings {
          border-left: 3px solid #dc2626;
          padding-left: 0.75rem;
          background-color: #fef2f2;
        }
        .ai-analysis-card:last-child {
          margin-bottom: 0;
        }
        .ai-name {
          margin: 0 0 0.75rem 0;
          font-size: 0.9rem;
          font-weight: 600;
          color: #374151;
          border-bottom: 1px solid #d1d5db;
          padding-bottom: 0.5rem;
        }
        .analysis-item {
          margin-bottom: 0.75rem;
        }
        .analysis-item:last-child {
          margin-bottom: 0;
        }
        .pros-label {
          color: #374151;
          font-weight: 600;
          font-size: 0.9rem;
        }
        .cons-label {
          color: #374151;
          font-weight: 600;
          font-size: 0.9rem;
        }
        .analysis-item ul {
          margin: 0.5rem 0 0 1rem;
          padding: 0;
        }
        .analysis-item li {
          margin-bottom: 0.25rem;
          font-size: 0.9rem;
          line-height: 1.5;
          color: #4b5563;
        }
        .integrated-answer,
        .rationale,
        .recommendation,
        .insights {
          border-bottom-color: #e5e7eb;
        }
        .aiofai-input-box {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          display: flex;
          align-items: flex-end;
          padding: 0.4rem;
          gap: 0.4rem;
          max-width: 51.2rem;
          margin: 0 auto;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          width: 90%;
          position: relative;
        }
        .aiofai-input-box:focus-within {
          border-color: #8ba88a;
          box-shadow: 0 0 0 3px rgba(93, 124, 91, 0.1);
        }
        .input-field {
          flex: 1;
          border: none;
          outline: none;
          padding: 0.6rem;
          background: transparent;
          color: #2d3e2c;
          font-size: 1rem;
          border-radius: 12px;
          resize: none;
          min-height: 24px;
          max-height: 120px;
          overflow-y: auto;
          font-family: inherit;
          line-height: 1.5;
        }
        .input-field::placeholder {
          color: rgba(45, 62, 44, 0.5);
        }
        .input-field::-webkit-scrollbar {
          width: 6px;
        }
        .input-field::-webkit-scrollbar-track {
          background: transparent;
        }
        .input-field::-webkit-scrollbar-thumb {
          background: rgba(139, 168, 138, 0.3);
          border-radius: 3px;
        }
        .input-field::-webkit-scrollbar-thumb:hover {
          background: rgba(139, 168, 138, 0.5);
        }
        .aiofai-icon-button {
          color: #2d3e2c;
          padding: 8px;
          border-radius: 10px;
          transition: all 0.2s ease;
          cursor: pointer;
          border: none;
          background: transparent;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .aiofai-icon-button:hover {
          background: rgba(139, 168, 138, 0.12);
        }
        .aiofai-icon-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .attachment-strip {
          width: 90%;
          max-width: 51.2rem;
          margin: 0 auto;
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }
        .attachment-chip {
          position: relative;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          border: 1px solid rgba(139, 168, 138, 0.3);
          background: rgba(255, 255, 255, 0.85);
          backdrop-filter: blur(6px);
          border-radius: 12px;
          padding: 6px 10px 6px 6px;
        }
        .attachment-thumb {
          width: 56px;
          height: 56px;
          border-radius: 8px;
          object-fit: cover;
          border: 1px solid rgba(139, 168, 138, 0.25);
        }
        .chip-close {
          position: absolute;
          top: -8px;
          right: -8px;
          width: 22px;
          height: 22px;
          border-radius: 9999px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          background: white;
          border: 1px solid rgba(139, 168, 138, 0.3);
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
          cursor: pointer;
        }
        .chip-close:hover {
          background: rgba(255,255,255,0.9);
        }
        .file-label {
          max-width: 220px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          color: #2d3e2c;
          font-size: 0.9rem;
        }
        .plus-menu {
          position: absolute;
          bottom: 52px;
          right: 8px;
          min-width: 180px;
          background: rgba(255,255,255,0.98);
          border: 1px solid rgba(139,168,138,0.25);
          border-radius: 12px;
          box-shadow: 0 8px 28px rgba(0,0,0,0.12);
          padding: 6px;
          z-index: 50;
        }
        .plus-menu button {
          width: 100%;
          text-align: left;
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 10px;
          border-radius: 10px;
          border: none;
          background: transparent;
          color: #2d3e2c;
          cursor: pointer;
        }
        .plus-menu button:hover {
          background: rgba(139,168,138,0.12);
        }
        .plus-menu button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>

      <div className="flex-shrink-0 flex chat-header w-full">
        {selectedModels.concat("optimal").map((modelId) => {
          const getModelDisplay = (id) => {
            if (id === "optimal") return { main: "최적의 답변", sub: null };
            
            // Gemini 모델
            if (id.startsWith("gemini-")) {
              const version = id.replace("gemini-", "");
              return { main: "GEMINI", sub: `-${version}` };
            }
            // Claude 모델
            if (id.startsWith("claude-")) {
              const version = id.replace("claude-", "");
              return { main: "CLAUDE", sub: `-${version}` };
            }
            // GPT 모델
            if (id.startsWith("gpt-")) {
              const version = id.replace("gpt-", "");
              return { main: "GPT", sub: `-${version}` };
            }
            // Clova 모델
            if (id.startsWith("clova-")) {
              const version = id.replace("clova-", "");
              return { main: "CLOVA", sub: `-${version}` };
            }
            
            return { main: id.toUpperCase(), sub: null };
          };
          
          const { main, sub } = getModelDisplay(modelId);
          
          return (
            <div
              key={modelId}
              className="px-4 py-2 text-center border-r flex-1 flex items-center justify-center"
              style={{ color: "#2d3e2c", borderRightColor: "rgba(139, 168, 138, 0.3)" }}
            >
              <div className="flex items-baseline gap-0">
                <div className="text-lg font-bold">{main}</div>
                {sub && <div className="text-xs text-gray-700">{sub}</div>}
              </div>
            </div>
          );
        })}
      </div>

      <div
        className="chat-container grid overflow-hidden"
        style={{ gridTemplateColumns: `repeat(${selectedModels.length + 1}, minmax(0, 1fr))` }}
      >
        {selectedModels.concat("optimal").map((modelId) => (
          <div key={modelId} className="border-r flex-1 overflow-y-auto chat-column">
            <div className="h-full px-4 py-3">
              {messages[modelId]?.map((message, index) => {
                const isUser = !!message.isUser;
                const isOptimal = modelId === "optimal";
                
                if (!message || (!message.text && !message.files)) {
                  console.warn('Invalid message detected:', message);
                  return null;
                }
                
                let hasSimilarityData = null;
                if (isOptimal && !isUser) {
                  hasSimilarityData = message.similarityData;
                }
                
                return (
                  <div key={`${modelId}-${index}`} className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4 flex-col ${isUser ? "items-end" : "items-start"}`}>
                    {message.files && message.files.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-2 max-w-[85%]">
                        {message.files.map((file, fileIndex) => {
                          const handleFileDownload = () => {
                            if (!file.dataUrl) return;
                            
                            try {
                              // Base64 데이터를 Blob으로 변환
                              const base64Data = file.dataUrl.split(',')[1] || file.dataUrl;
                              const byteCharacters = atob(base64Data);
                              const byteNumbers = new Array(byteCharacters.length);
                              for (let i = 0; i < byteCharacters.length; i++) {
                                byteNumbers[i] = byteCharacters.charCodeAt(i);
                              }
                              const byteArray = new Uint8Array(byteNumbers);
                              const blob = new Blob([byteArray], { type: file.type || 'application/octet-stream' });
                              
                              // 다운로드 링크 생성
                              const url = URL.createObjectURL(blob);
                              const link = document.createElement('a');
                              link.href = url;
                              link.download = file.name || 'download';
                              document.body.appendChild(link);
                              link.click();
                              document.body.removeChild(link);
                              URL.revokeObjectURL(url);
                            } catch (error) {
                              console.error('파일 다운로드 실패:', error);
                              alert('파일 다운로드에 실패했습니다.');
                            }
                          };
                          
                          return (
                            <div key={fileIndex} className="relative">
                              {file.type && file.type.startsWith('image/') ? (
                                <div>
                                  {file.dataUrl ? (
                                    <img
                                      src={file.dataUrl}
                                      alt={file.name || 'image'}
                                      className="rounded-lg border border-gray-300 object-contain cursor-pointer"
                                      style={{ maxWidth: '300px', maxHeight: '300px' }}
                                      loading="eager"
                                      onClick={handleFileDownload}
                                      title="클릭하여 원본 파일 다운로드"
                                      onError={(e) => {
                                        e.target.style.display = 'none';
                                        console.warn('Image load failed:', file.name);
                                      }}
                                    />
                                  ) : (
                                    <div className="rounded-lg border border-gray-300 bg-gray-50 p-8 text-center">
                                      <div className="text-gray-400 text-4xl mb-2">📷</div>
                                      <div className="text-xs text-gray-500">{file.name || '이미지'}</div>
                                      {file._largeFile && (
                                        <div className="text-xs text-gray-400 mt-1">(큰 파일로 저장되지 않음)</div>
                                      )}
                                    </div>
                                  )}
                                  <div className="text-xs text-gray-500 mt-1 text-center">
                                    {file.name || '이미지'}
                                  </div>
                                </div>
                              ) : (
                                <div 
                                  className="flex items-center gap-2 p-3 bg-gray-100 rounded-lg border border-gray-300 cursor-pointer hover:bg-gray-200 transition-colors"
                                  onClick={file.dataUrl ? handleFileDownload : undefined}
                                  title={file.dataUrl ? "클릭하여 원본 파일 다운로드" : file._largeFile ? "큰 파일로 인해 저장되지 않았습니다" : "파일"}
                                >
                                  <div className="text-gray-600 text-2xl">
                                    📄
                                  </div>
                                  <span className="text-sm text-gray-700 font-medium">
                                    {file.name || '파일'}
                                  </span>
                                  {file._largeFile && (
                                    <span className="text-xs text-gray-500 ml-1">
                                      (저장되지 않음)
                                    </span>
                                  )}
                                  {file.dataUrl && (
                                    <svg 
                                      className="w-4 h-4 text-gray-500 ml-1" 
                                      fill="none" 
                                      stroke="currentColor" 
                                      viewBox="0 0 24 24"
                                    >
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    
                    {message.text && (
                      <div className={`${isUser ? "aiofai-user-message" : "aiofai-bot-message"} ${isOptimal && !isUser ? "optimal-response" : ""}`}>
                        {isOptimal && !isUser ? (
                          <div>
                            <OptimalResponseRenderer 
                              content={message.text}
                              similarityData={message.similarityData}
                              selectedModels={selectedModels}
                            />
                            
                            {/* Parse AI analysis data */}
                            {(() => {
                              const normalizeModelName = (name) => {
                                if (!name) return '';
                                return String(name).toLowerCase().replace(/\s+/g, '-').replace(/_+/g, '-');
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

                              const selectedModelSet = new Set(
                                (selectedModels || []).map(normalizeModelName)
                              );

                              const filterAnalysisBySelection = (analysisData) => {
                                if (!analysisData || typeof analysisData !== 'object') return {};
                                if (selectedModelSet.size === 0) return analysisData;
                                
                                console.log('🔍 filterAnalysisBySelection - analysisData keys:', Object.keys(analysisData));
                                console.log('🔍 filterAnalysisBySelection - selectedModelSet:', Array.from(selectedModelSet));
                                
                                return Object.fromEntries(
                                  Object.entries(analysisData).filter(([backendModelName]) => {
                                    // 백엔드 모델 이름을 프론트엔드 모델 ID로 변환
                                    const frontendModelId = backendToFrontendModelId(backendModelName);
                                    const normalizedBackendName = normalizeModelName(frontendModelId);
                                    
                                    const isIncluded = selectedModelSet.has(normalizedBackendName);
                                    console.log(`🔍 filterAnalysisBySelection - "${backendModelName}" -> "${frontendModelId}" -> "${normalizedBackendName}" -> 포함? ${isIncluded}`);
                                    
                                    return isIncluded;
                                  })
                                );
                              };

                              const parseOptimalResponseForAnalysis = (text) => {
                                if (!text) return {};
                                const sections = {};
                                const lines = text.split('\n');
                                let currentSection = '';
                                let currentContent = [];
                                
                                for (const line of lines) {
                                  if (line.startsWith('**각 LLM 검증 결과:**') || line.startsWith('**각 AI 분석:**')) {
                                    if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
                                    currentSection = 'analysis';
                                    currentContent = [];
                                  } else if (line.startsWith('**📊 답변 생성 근거:**')) {
                                    if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
                                    currentSection = 'rationale';
                                    currentContent = [];
                                  } else if (line.startsWith('**⚠️') || line.startsWith('⚠️')) {
                                    if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
                                    currentSection = 'contradictions';
                                    currentContent = [];
                                  } else if (line.trim() !== '') {
                                    currentContent.push(line);
                                  }
                                }
                                if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
                                return sections;
                              };
                              
                              const parseAIAnalysisData = (analysisText) => {
                                const analyses = {};
                                const lines = analysisText.split('\n');
                                let currentAI = '';
                                let currentAnalysis = { 
                                  accuracy: '✅', 
                                  pros: [], 
                                  cons: [], 
                                  confidence: 0,
                                  adopted: [],
                                  rejected: []
                                };
                                
                                for (const line of lines) {
                                  const trimmedLine = line.trim();
                                  
                                  if (trimmedLine.startsWith('**') && (trimmedLine.endsWith(':**') || trimmedLine.endsWith('**'))) {
                                    if (currentAI) {
                                      analyses[currentAI] = currentAnalysis;
                                    }
                                    currentAI = trimmedLine.replace(/\*\*/g, '').replace(':**', '').replace('**', '');
                                    currentAnalysis = { 
                                      accuracy: '✅', 
                                      pros: [], 
                                      cons: [], 
                                      confidence: 0,
                                      adopted: [],
                                      rejected: []
                                    };
                                  } else if (trimmedLine.includes('✅ 정확성:')) {
                                    currentAnalysis.accuracy = trimmedLine.includes('✅ 정확성: ✅') ? '✅' : '❌';
                                  } else if (trimmedLine.includes('❌ 오류:')) {
                                    const error = trimmedLine.replace('❌ 오류:', '').trim();
                                    if (error && error !== '오류 없음' && error !== '정확한 정보 제공') {
                                      currentAnalysis.cons = [error];
                                    }
                                  } else if (trimmedLine.includes('📊 신뢰도:')) {
                                    const match = trimmedLine.match(/📊 신뢰도:\s*(\d+)%/);
                                    if (match) {
                                      currentAnalysis.confidence = parseInt(match[1]);
                                    }
                                  } else if (trimmedLine.startsWith('✅ 채택된 정보:')) {
                                    const info = trimmedLine.replace('✅ 채택된 정보:', '').trim();
                                    if (info && info !== '없음' && info !== '없습니다') {
                                      currentAnalysis.adopted.push(info);
                                    }
                                  } else if (trimmedLine.startsWith('❌ 제외된 정보:')) {
                                    const info = trimmedLine.replace('❌ 제외된 정보:', '').trim();
                                    if (info && info !== '없음' && info !== '없습니다') {
                                      currentAnalysis.rejected.push(info);
                                    }
                                  }
                                }
                                
                                if (currentAI) {
                                  analyses[currentAI] = currentAnalysis;
                                }
                                
                                // "⚠️ 발견된 상호모순" 제거
                                const keysToRemove = ["⚠️ 발견된 상호모순", "⚠️ 발견된 상호모순:", "발견된 상호모순"];
                                keysToRemove.forEach(key => {
                                  if (analyses[key]) delete analyses[key];
                                });
                                
                                return analyses;
                              };
                              
                              const parsed = parseOptimalResponseForAnalysis(message.text);

                              const filteredBackendAnalysis = filterAnalysisBySelection(message.analysisData);
                              const backendAnalysisCount = Object.keys(filteredBackendAnalysis || {}).length;

                              let analysisFromText = {};
                              if ((!message.analysisData || backendAnalysisCount === 0) && parsed.analysis) {
                                analysisFromText = filterAnalysisBySelection(parseAIAnalysisData(parsed.analysis));
                              }

                              const hasAnalysis =
                                backendAnalysisCount > 0 ||
                                (analysisFromText && Object.keys(analysisFromText).length > 0);
                              
                              return (hasSimilarityData || hasAnalysis) && (
                                <div className="mt-3 flex justify-center gap-2">
                                  {hasSimilarityData && (
                                    <button
                                      onClick={() => {
                                        setSimilarityData(hasSimilarityData);
                                        setIsSimilarityModalOpen(true);
                                      }}
                                      className="flex items-center gap-2 px-3 py-2 text-sm bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg transition-colors font-medium"
                                      title="유사도 분석 결과 보기"
                                    >
                                      <BarChart3 size={16} />
                                      유사도 분석 결과
                                    </button>
                                  )}
                                  {hasAnalysis && (
                                    <button
                                      onClick={() => {
                                        let analysisData = filteredBackendAnalysis;
                                        let rationale = message.rationale;

                                        if ((!analysisData || Object.keys(analysisData).length === 0) && parsed.analysis) {
                                          analysisData = analysisFromText;
                                          rationale = rationale || parsed.rationale || "";
                                        }

                                        console.log('Setting AI analysis data:');
                                        console.log('- analysisData:', JSON.stringify(analysisData, null, 2));
                                        console.log('- rationale:', rationale);
                                        console.log('- verificationSource:', message.verificationSource);
                                        
                                        setAiAnalysisData({
                                          analysisData: analysisData,
                                          rationale: rationale || "",
                                          selectedModels: selectedModels,
                                          verificationSource: message.verificationSource || null
                                        });
                                        setIsAIAnalysisModalOpen(true);
                                      }}
                                      className="flex items-center gap-2 px-3 py-2 text-sm bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg transition-colors font-medium"
                                      title="각 AI 분석 결과 보기"
                                    >
                                      <Brain size={16} />
                                      각 AI 분석
                                    </button>
                                  )}
                                </div>
                              );
                            })()}
                          </div>
                        ) : (
                          <div>
                            <ReactMarkdown 
                              remarkPlugins={[remarkGfm]}
                              components={{
                                code: CodeBlock,
                                pre: ({ children, ...props }) => <pre {...props}>{children}</pre>,
                                table: ResponsiveTable,
                                thead: TableHead,
                                tbody: TableBody,
                                tr: TableRow,
                                th: TableHeader,
                                td: TableCell
                              }}
                            >
                              {message.text}
                            </ReactMarkdown>
                            {!message.isUser && !message.isError && <CopyAllButton content={message.text} />}
                            {message.isError && (
                              <button
                                onClick={() => {
                                  // 오류 발생 시 마지막 사용자 메시지 찾기
                                  const userMessages = messages[modelId]?.filter(msg => msg.isUser) || [];
                                  const lastUserMessage = userMessages[userMessages.length - 1];
                                  if (lastUserMessage) {
                                    // 마지막 사용자 메시지 재전송
                                    const messageText = lastUserMessage.text || '';
                                    const files = lastUserMessage.files || [];
                                    
                                    // 파일 데이터 준비
                                    const filesBase64 = files.map(f => ({
                                      name: f.name,
                                      type: f.type,
                                      size: f.size,
                                      dataUrl: f.dataUrl
                                    }));
                                    
                                    sendMessage(messageText, null, {
                                      filesBase64: filesBase64.filter(f => f.dataUrl),
                                      imagesBase64: filesBase64.filter(f => f.type?.startsWith('image/')),
                                      videosBase64: filesBase64.filter(f => f.type?.startsWith('video/'))
                                    });
                                  }
                                }}
                                className="flex items-center justify-center p-2 rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors mt-2"
                                title="질문 재전송"
                              >
                                <RotateCw size={18} className="text-gray-600" />
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {loadingModels.has(modelId) && (
                <div className="flex justify-start mb-4">
                  <div className="bg-gray-100 text-gray-800 p-4 rounded-2xl">
                    {loadingText || "입력 중..."}
                  </div>
                </div>
              )}

              <div className="h-3" />
              <div ref={messagesEndRefs.current[modelId]} />
            </div>
          </div>
        ))}
      </div>

      <div className="aiofai-input-area">
        {(imageAttachments.length > 0 || fileAttachments.length > 0) && (
          <div className="attachment-strip">
            {imageAttachments.map((att) => (
              <div key={att.id} className="attachment-chip">
                <img src={att.url} alt="attachment" className="attachment-thumb" />
                <button type="button" className="chip-close" aria-label="이미지 제거" onClick={() => removeImage(att.id)}>
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
            {fileAttachments.map((att) => (
              <div key={att.id} className="attachment-chip">
                <FileIcon className="w-5 h-5" />
                <span className="file-label" title={att.name}>{att.name}</span>
                <button type="button" className="chip-close" aria-label="파일 제거" onClick={() => removeFile(att.id)}>
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          onChange={handleImageChange}
          style={{ display: "none" }}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,.bmp,.tiff,image/*,application/pdf"
          onChange={handleFileChange}
          style={{ display: "none" }}
        />

        <form onSubmit={handleSendMessage} className="aiofai-input-box">
          <textarea
            ref={textareaRef}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!isLoading) {
                  // 한글 조합 중인지 확인
                  if (e.nativeEvent.isComposing) {
                    return;
                  }
                  handleSendMessage(e);
                }
              }
            }}
            placeholder="메시지를 입력하세요..."
            className="input-field"
            rows={1}
          />

          <button
            type="button"
            ref={plusBtnRef}
            className="aiofai-icon-button"
            onClick={() => setIsMenuOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={isMenuOpen}
            title="첨부 추가"
            disabled={isLoading}
          >
            <CirclePlus className="w-5 h-5" />
          </button>

          <button
            type="submit"
            disabled={isLoading}
            className="aiofai-icon-button"
            title={isLoading ? "분석 중..." : "전송"}
          >
            <Send className="w-5 h-5" />
          </button>

          {isMenuOpen && (
            <div className="plus-menu" ref={menuRef} role="menu">
              <button type="button" onClick={() => imageInputRef.current?.click()} role="menuitem" disabled={isLoading}>
                <ImageIcon className="w-4 h-4" />
                이미지 업로드
              </button>
              <button type="button" onClick={() => fileInputRef.current?.click()} role="menuitem" disabled={isLoading}>
                <FileIcon className="w-4 h-4" />
                파일 업로드
              </button>
              <button 
                type="button" 
                onClick={() => {
                  setIsMenuOpen(false);
                  navigate('/video-chat');
                }} 
                role="menuitem" 
                disabled={isLoading}
              >
                <Video className="w-4 h-4" />
                영상 업로드
              </button>
            </div>
          )}
        </form>
      </div>

      <SimilarityDetailModal
        isOpen={isSimilarityModalOpen}
        onClose={() => setIsSimilarityModalOpen(false)}
        similarityData={similarityData}
      />
      
      <AIAnalysisModal
        isOpen={isAIAnalysisModalOpen}
        onClose={() => setIsAIAnalysisModalOpen(false)}
        analysisData={aiAnalysisData}
        selectedModels={selectedModels}
      />
    </div>
  );
};

export default ChatBox;