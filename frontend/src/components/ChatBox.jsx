import React, { useState, useEffect, useRef } from "react";
import { Send, CirclePlus, Image as ImageIcon, File as FileIcon, X, BarChart3, Settings } from "lucide-react";
import { useChat } from "../context/ChatContext";
import SimilarityDetailModal from "./SimilarityDetailModal";
import { api } from "../utils/api";

// Optimal Response Renderer Component
const OptimalResponseRenderer = ({ content }) => {
  const parseOptimalResponse = (text) => {
    // content가 없거나 undefined인 경우 빈 객체 반환
    if (!text || typeof text !== 'string') {
      return {};
    }
    
    const sections = {};
    const lines = text.split('\n');
    let currentSection = '';
    let currentContent = [];
    
    for (const line of lines) {
      // 새로운 간결한 형식 지원
      if (line.startsWith('**최적 답변:**') || line.startsWith('**최적의 답변:**') || line.startsWith('## 🎯 정확한 답변') || line.startsWith('## 통합 답변') || line.startsWith('## 🎯 통합 답변')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'integrated';
        currentContent = [];
      } else if (line.startsWith('## 각 AI 분석') || line.startsWith('## 📊 각 AI 분석') || line.startsWith('**각 AI 분석:**') || line.startsWith('**각 LLM 검증 결과:**')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'analysis';
        currentContent = [];
      } else if (line.startsWith('**검증 결과:**') || line.startsWith('## 분석 근거') || line.startsWith('## 🔍 분석 근거') || line.startsWith('## 🔍 검증 결과')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'rationale';
        currentContent = [];
      } else if (line.startsWith('## 최종 추천') || line.startsWith('## 🏆 최종 추천')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'recommendation';
        currentContent = [];
      } else if (line.startsWith('## 추가 인사이트') || line.startsWith('## 💡 추가 인사이트') || line.startsWith('## ⚠️ 수정된 정보')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'insights';
        currentContent = [];
      } else if (line.trim() !== '') {
        currentContent.push(line);
      }
    }
    
    if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
    return sections;
  };

  const parseAIAnalysis = (analysisText) => {
    const analyses = {};
    const lines = analysisText.split('\n');
    let currentAI = '';
    let currentAnalysis = { pros: [], cons: [] };
    
    for (const line of lines) {
      if (line.startsWith('### ')) {
        if (currentAI) {
          analyses[currentAI] = currentAnalysis;
        }
        currentAI = line.replace('### ', '').trim();
        currentAnalysis = { pros: [], cons: [] };
      } else if (line.includes('- 장점:')) {
        currentAnalysis.pros.push(line.replace('- 장점:', '').trim());
      } else if (line.includes('- 단점:')) {
        currentAnalysis.cons.push(line.replace('- 단점:', '').trim());
      }
    }
    
    if (currentAI) {
      analyses[currentAI] = currentAnalysis;
    }
    
    return analyses;
  };

  const parseNewAIAnalysis = (analysisText) => {
    const analyses = {};
    const lines = analysisText.split('\n');
    let currentAI = '';
    let currentAnalysis = { pros: [], cons: [], confidence: 0, warnings: [] };
    
    for (const line of lines) {
      const trimmedLine = line.trim();
      
      // 새로운 형식: **GPT-3.5 Turbo:**, **Claude-3.5 Haiku:**, **Llama 3.1 8B:**
      if (trimmedLine.startsWith('**') && trimmedLine.endsWith(':**')) {
        // 이전 AI 분석 저장
        if (currentAI) {
          analyses[currentAI] = currentAnalysis;
        }
        
        // 새 AI 시작
        currentAI = trimmedLine.replace(/\*\*/g, '').replace(':**', '');
        currentAnalysis = { pros: [], cons: [], confidence: 0, warnings: [] };
      } else if (trimmedLine.includes('정확성:')) {
        // 새로운 형식: ✅ 정확성: ✅ 또는 ❌ 정확성: ❌
        const accuracy = trimmedLine.replace(/.*정확성:\s*/, '').trim();
        if (accuracy === '✅') {
          currentAnalysis.pros = ['정확한 정보 제공'];
          currentAnalysis.confidence = 90; // 높은 신뢰도
        } else if (accuracy === '❌') {
          currentAnalysis.pros = [];
          currentAnalysis.confidence = 20; // 낮은 신뢰도
        }
      } else if (trimmedLine.includes('오류:')) {
        // 새로운 형식: ❌ 오류: 오류 없음 또는 구체적인 오류 설명
        const error = trimmedLine.replace(/.*오류:\s*/, '').trim();
        if (error && error !== '오류 없음') {
          currentAnalysis.cons = [error];
        } else {
          currentAnalysis.cons = [];
        }
      } else if (trimmedLine.includes('✅ 정확한 정보:')) {
        const info = trimmedLine.replace('✅ 정확한 정보:', '').trim();
        if (info && info !== '기본 정보 제공') {
          currentAnalysis.pros = info.split(',').map(i => i.trim()).filter(i => i.length > 0);
        } else {
          currentAnalysis.pros = ['기본 정보 제공'];
        }
      } else if (trimmedLine.includes('❌ 틀린 정보:')) {
        const info = trimmedLine.replace('❌ 틀린 정보:', '').trim();
        if (info && info !== '없음') {
          currentAnalysis.cons = info.split(',').map(i => i.trim()).filter(i => i.length > 0);
        } else {
          currentAnalysis.cons = [];
        }
      } else if (trimmedLine.includes('📊 신뢰도:')) {
        const confidenceMatch = trimmedLine.match(/📊 신뢰도: (\d+)%/);
        if (confidenceMatch) {
          currentAnalysis.confidence = parseInt(confidenceMatch[1]);
        }
      } else if (trimmedLine.includes('⚠️ 충돌 경고:')) {
        const info = trimmedLine.replace('⚠️ 충돌 경고:', '').trim();
        if (info) {
          currentAnalysis.warnings = info.split(',').map(i => i.trim()).filter(i => i.length > 0);
        }
      }
    }
    
    // 마지막 AI 분석 저장
    if (currentAI) {
      analyses[currentAI] = currentAnalysis;
    }
    
    return analyses;
  };

  // content가 없으면 기본 메시지 표시
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
                   {sections.integrated}
                 </div>
               </div>
             )}
      
             {Object.keys(analysisData).length > 0 && (
               <div className="optimal-section ai-analysis">
                 <h3 className="section-title">
                   각 AI 분석
                 </h3>
          <div className="analysis-grid">
            {Object.entries(analysisData).map(([aiName, analysis]) => (
              <div key={aiName} className="ai-analysis-card">
                <h4 className="ai-name">{aiName}</h4>
                {analysis.pros.length > 0 && (
                  <div className="analysis-item pros">
                    <span className="pros-label">✅ 정확한 정보:</span>
                    <ul>
                      {analysis.pros.map((pro, index) => (
                        <li key={index}>{pro}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {analysis.cons.length > 0 && (
                  <div className="analysis-item cons">
                    <span className="cons-label">❌ 틀린 정보:</span>
                    <ul>
                      {analysis.cons.map((con, index) => (
                        <li key={index}>{con}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {analysis.confidence > 0 && (
                  <div className="analysis-item confidence">
                    <span className="confidence-label">📊 신뢰도:</span>
                    <span className={`confidence-value ${analysis.confidence >= 80 ? 'high' : analysis.confidence >= 60 ? 'medium' : 'low'}`}>
                      {analysis.confidence}%
                    </span>
                  </div>
                )}
                {analysis.warnings.length > 0 && (
                  <div className="analysis-item warnings">
                    <span className="warnings-label">⚠️ 충돌 경고:</span>
                    <ul>
                      {analysis.warnings.map((warning, index) => (
                        <li key={index}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      
             {sections.rationale && (
               <div className="optimal-section rationale">
                 <h3 className="section-title">
                   분석 근거
                 </h3>
                 <div className="section-content">
                   {sections.rationale}
                 </div>
               </div>
             )}
             
             {sections.recommendation && (
               <div className="optimal-section recommendation">
                 <h3 className="section-title">
                   최종 추천
                 </h3>
                 <div className="section-content">
                   {sections.recommendation}
                 </div>
               </div>
             )}
             
             {sections.insights && (
               <div className="optimal-section insights">
                 <h3 className="section-title">
                   추가 인사이트
                 </h3>
                 <div className="section-content">
                   {sections.insights}
                 </div>
               </div>
             )}
    </div>
  );
};

// PDF와 이미지 파일 허용 확장자 목록
const ALLOWED_FILE_EXTS = [
  ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"
];

const ChatBox = () => {
  const {
    messages = {},
    sendMessage,
    isLoading,
    selectedModels = [],
    // 선택 모델/워크플로우 기능 없음
    processImageUpload,     // 있으면 우선 사용
    processFileUpload       // 있으면 우선 사용
  } = useChat() || {};

  const [inputMessage, setInputMessage] = useState("");
  const messagesEndRefs = useRef({});

  // 심판 모델 선택 상태
  const [selectedJudgeModel, setSelectedJudgeModel] = useState("gpt-3.5-turbo");
  const [availableJudgeModels, setAvailableJudgeModels] = useState({});
  const [showJudgeModelSelector, setShowJudgeModelSelector] = useState(false);

  // 첨부(이미지/파일) 상태
  const [imageAttachments, setImageAttachments] = useState([]); // { id, file, url }
  const [fileAttachments, setFileAttachments] = useState([]);   // { id, file, name, size }
  const imageInputRef = useRef(null);
  const fileInputRef = useRef(null);

  // + 버튼 메뉴
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const plusBtnRef = useRef(null);

  // 심판 모델 목록 불러오기
  useEffect(() => {
    const fetchJudgeModels = async () => {
      try {
        const response = await api.get('/api/verification/models/');
        if (response.data.success) {
          setAvailableJudgeModels(response.data.models);
        }
      } catch (error) {
        console.warn('심판 모델 목록 조회 실패:', error);
      }
    };

    fetchJudgeModels();
  }, []);

  // 유사도 분석 관련 상태
  const [similarityData, setSimilarityData] = useState({});
  const [isSimilarityModalOpen, setIsSimilarityModalOpen] = useState(false);

  // 메시지 컬럼별 끝 ref 준비
  useEffect(() => {
    selectedModels.concat("optimal").forEach((modelId) => {
      if (!messagesEndRefs.current[modelId]) {
        messagesEndRefs.current[modelId] = React.createRef();
      }
    });
  }, [selectedModels]);

  // 새 메시지 추가 시 자동 스크롤
  useEffect(() => {
    selectedModels.concat("optimal").forEach((modelId) => {
      messagesEndRefs.current[modelId]?.current?.scrollIntoView({ behavior: "smooth" });
    });
  }, [messages, selectedModels]);

  // 바깥 클릭으로 메뉴 닫기
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

  // File -> Base64 dataURL
  const readFileAsDataURL = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = reject;
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(file);
    });

  // 이미지 onChange (이미지만 통과)
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

    // 같은 파일 다시 선택해도 change 발생하도록 초기화
    try { e.target.value = ""; } catch {}
    setIsMenuOpen(false);
  };

  // 파일 onChange (이미지 제외)
  const handleFileChange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    // PDF와 이미지 파일 모두 허용
    const allowedTypes = [
      'application/pdf',
      'image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/tiff'
    ];
    
    if (!allowedTypes.includes(file.type)) {
      alert("PDF 또는 이미지 파일만 업로드할 수 있습니다.");
      e.target.value = "";
      return;
    }

    // 확장자 제한(선택 사항) — accept로 1차 필터링하지만 JS에서도 2차 방어
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

  // 첨부 제거
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

  // 전송
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!sendMessage) return;

    const trimmed = inputMessage.trim();
    const hasAttachments = imageAttachments.length > 0 || fileAttachments.length > 0;
    if (!trimmed && !hasAttachments) return;

    const requestId = generateRequestId();

    try {
      // 1) 업로드 핸들러가 있으면 그쪽 경로를 우선 사용 (서버에 파일 전송)
      if (typeof processImageUpload === "function" || typeof processFileUpload === "function") {
        // 이미지는 개별 업로드
        if (typeof processImageUpload === "function") {
          for (const att of imageAttachments) {
            await processImageUpload(att.file, requestId, { caption: trimmed || "" });
          }
        }
        // 파일은 개별 업로드
        if (typeof processFileUpload === "function") {
          for (const att of fileAttachments) {
            await processFileUpload(att.file, requestId, { caption: trimmed || "" });
          }
        }
        // 텍스트만 남았으면 전송
        if (trimmed) {
          await sendMessage(trimmed, requestId, {});
        }
      } else {
        // 2) 폴백: Base64로 변환해서 옵션으로 전달
        const imagesBase64 = await Promise.all(
          imageAttachments.map(async (a) => {
            const dataUrl = await readFileAsDataURL(a.file); // "data:image/png;base64,...."
            return { name: a.file.name, type: a.file.type, size: a.file.size, dataUrl };
          })
        );
        const filesBase64 = await Promise.all(
          fileAttachments.map(async (a) => {
            const dataUrl = await readFileAsDataURL(a.file);
            return { name: a.file.name, type: a.file.type, size: a.file.size, dataUrl };
          })
        );

        // 텍스트에 첨부 메타를 추가(서버가 options를 무시해도 인지 가능)
        const attachmentNote = [
          ...imageAttachments.map(a => `📷 ${a.file.name}`),
          ...fileAttachments.map(a => `📎 ${a.file.name}`)
        ];
        const textWithNote =
          trimmed || (attachmentNote.length ? `(첨부 전송) ${attachmentNote.join(", ")}` : "");

        await sendMessage(textWithNote, requestId, {
          imagesBase64,
          filesBase64,
        });
      }

      // 초기화
      imageAttachments.forEach((a) => {
        if (a.url) try { URL.revokeObjectURL(a.url); } catch {}
      });
      setImageAttachments([]);
      setFileAttachments([]);
      setInputMessage("");
    } catch (err) {
      console.error(err);
      // 실패 시에도 첨부 유지 (사용자가 다시 시도 가능)
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
          gap: 0.3rem; /* 위/아래 균형 */
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
          align-items: center;
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
        }
        .input-field::placeholder {
          color: rgba(45, 62, 44, 0.5);
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
      `}</style>

      {/* 상단 모델 라벨만 유지 */}
      <div className="flex-shrink-0 flex chat-header w-full">
        {selectedModels.concat("optimal").map((modelId) => (
          <div
            key={modelId}
            className="px-4 py-2 text-lg font-semibold text-center border-r flex-1 whitespace-nowrap overflow-hidden text-ellipsis flex items-center justify-center"
            style={{ color: "#2d3e2c", borderRightColor: "rgba(139, 168, 138, 0.3)" }}
          >
            {modelId === "optimal" ? "최적의 답변" : modelId.toUpperCase()}
          </div>
        ))}
      </div>

      {/* 채팅 메시지 영역 */}
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
                
                // 유사도 분석 데이터 가져오기
                let hasSimilarityData = null;
                if (isOptimal && !isUser) {
                  // 메시지에 직접 포함된 유사도 분석 데이터 사용
                  hasSimilarityData = message.similarityData;
                  
                  // 디버깅용 로그
                  console.log('Optimal message ID:', message.id);
                  console.log('Optimal message:', message);
                  console.log('Has similarity data:', !!hasSimilarityData);
                  if (hasSimilarityData) {
                    console.log('Similarity data:', hasSimilarityData);
                  }
                }
                
                return (
                  <div key={`${modelId}-${index}`} className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
                    <div className={`${isUser ? "aiofai-user-message" : "aiofai-bot-message"} ${isOptimal && !isUser ? "optimal-response" : ""}`}>
                      {isOptimal && !isUser ? (
                        <div>
                          <OptimalResponseRenderer content={message.text} />
                          
                          {/* 유사도 분석 결과 버튼 (유사도 데이터가 있는 경우) */}
                          {hasSimilarityData && (
                            <div className="mt-3 flex justify-center">
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
                            </div>
                          )}
                        </div>
                      ) : (
                        <div>
                          {/* 사용자가 업로드한 파일들 표시 */}
                          {message.files && message.files.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                              {message.files.map((file, fileIndex) => (
                                <div key={fileIndex} className="relative">
                                  {file.type.startsWith('image/') ? (
                                    <div>
                                      <img
                                        src={file.dataUrl}
                                        alt={file.name}
                                        className="max-w-xs max-h-48 rounded-lg border border-gray-200 object-cover"
                                      />
                                      <div className="text-xs text-gray-500 mt-1 text-center">
                                        {file.name}
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="flex items-center gap-2 p-2 bg-gray-100 rounded-lg border border-gray-200">
                                      <div className="text-gray-600">
                                        📄
                                      </div>
                                      <span className="text-sm text-gray-700 truncate max-w-32">
                                        {file.name}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div>{message.text}</div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isLoading && (
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

      {/* 입력/첨부 영역 */}
      <div className="aiofai-input-area">
        {/* 첨부 프리뷰 스트립 */}
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

        {/* 숨겨진 파일 입력들 — accept로 1차 필터링 */}
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

        {/* 입력 박스 */}
        <form onSubmit={handleSendMessage} className="aiofai-input-box">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="메시지를 입력하세요..."
            className="input-field"
            disabled={isLoading}
          />

          {/* + 버튼 (메뉴 토글) */}
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

          {/* 전송 버튼 */}
          <button
            type="submit"
            disabled={
              isLoading ||
              (!inputMessage.trim() && imageAttachments.length === 0 && fileAttachments.length === 0)
            }
            className="aiofai-icon-button"
            title="전송"
          >
            <Send className="w-5 h-5" />
          </button>

          {/* + 메뉴 팝오버 */}
          {isMenuOpen && (
            <div className="plus-menu" ref={menuRef} role="menu">
              <button type="button" onClick={() => imageInputRef.current?.click()} role="menuitem">
                <ImageIcon className="w-4 h-4" />
                이미지 업로드
              </button>
              <button type="button" onClick={() => fileInputRef.current?.click()} role="menuitem">
                <FileIcon className="w-4 h-4" />
                파일 업로드
              </button>
            </div>
          )}
        </form>
      </div>

      {/* 유사도 분석 모달 */}
      <SimilarityDetailModal
        isOpen={isSimilarityModalOpen}
        onClose={() => setIsSimilarityModalOpen(false)}
        similarityData={similarityData}
      />
    </div>
  );
};

export default ChatBox;