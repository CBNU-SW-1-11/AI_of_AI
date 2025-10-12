import React from 'react';
import { api } from '../utils/api';

const OptimalResponseRenderer = ({ content, relevantFrames, onFrameClick }) => {
  const parseOptimalResponse = (text) => {
    if (!text || typeof text !== 'string') return {};
    
    const sections = {};
    const lines = text.split('\n');
    let currentSection = '';
    let currentContent = [];
    
    for (const line of lines) {
      if (line.startsWith('## 통합 답변') || line.startsWith('## 🎯 통합 답변')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'integrated';
        currentContent = [];
      } else if (line.startsWith('## 각 AI 분석') || line.startsWith('## 📊 각 AI 분석') || line.includes('**각 AI 분석**')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'analysis';
        currentContent = [];
      } else if (line.startsWith('## 분석 근거') || line.startsWith('## 📝 분석 근거')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'rationale';
        currentContent = [];
      } else if (line.startsWith('## 최종 추천') || line.startsWith('## 🏆 최종 추천')) {
        if (currentSection) sections[currentSection] = currentContent.join('\n').trim();
        currentSection = 'recommendation';
        currentContent = [];
      } else if (line.startsWith('## 추가 인사이트') || line.startsWith('## 💡 추가 인사이트')) {
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
        if (currentAI) analyses[currentAI] = currentAnalysis;
        currentAI = line.replace('### ', '').trim();
        currentAnalysis = { pros: [], cons: [] };
      } else if (line.includes('- 장점:')) {
        currentAnalysis.pros.push(line.replace('- 장점:', '').trim());
      } else if (line.includes('- 단점:')) {
        currentAnalysis.cons.push(line.replace('- 단점:', '').trim());
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
  const analysisData = sections.analysis ? parseAIAnalysis(sections.analysis) : {};
  
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
          <div className="section-content">{sections.integrated}</div>
        </div>
      )}
      
      {sections.analysis && (
        <div className="optimal-section analysis-section">
          <h3 className="section-title">각 AI 분석</h3>
          <div className="analysis-grid">
            {Object.entries(analysisData).map(([aiName, analysis]) => (
              <div key={aiName} className="analysis-item">
                <h4 className="analysis-ai-name">{aiName}</h4>
                {analysis.pros.length > 0 && (
                  <div className="analysis-pros">
                    <strong>장점:</strong>
                    <ul>
                      {analysis.pros.map((pro, index) => (
                        <li key={index}>{pro}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {analysis.cons.length > 0 && (
                  <div className="analysis-cons">
                    <strong>단점:</strong>
                    <ul>
                      {analysis.cons.map((con, index) => (
                        <li key={index}>{con}</li>
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
        <div className="optimal-section rationale-section">
          <h3 className="section-title">분석 근거</h3>
          <div className="section-content">{sections.rationale}</div>
        </div>
      )}
      
      {sections.recommendation && (
        <div className="optimal-section recommendation-section">
          <h3 className="section-title">최종 추천</h3>
          <div className="section-content">{sections.recommendation}</div>
        </div>
      )}
      
      {sections.insights && (
        <div className="optimal-section insights-section">
          <h3 className="section-title">추가 인사이트</h3>
          <div className="section-content">{sections.insights}</div>
        </div>
      )}

      {relevantFrames && relevantFrames.length > 0 && (
        <div className="optimal-section frames-section">
          <h3 className="section-title">📸 관련 프레임</h3>
          <div className="frames-grid">
            {relevantFrames.map((frame, index) => (
              <div 
                key={index} 
                className="frame-card cursor-pointer"
                onClick={() => onFrameClick && onFrameClick(frame)}
              >
                <div className="frame-info">
                  <span className="frame-timestamp">⏰ {frame.timestamp.toFixed(1)}초</span>
                  <span className="frame-score">🎯 {frame.relevance_score}점</span>
                </div>
                <img
                  src={`${api.defaults.baseURL}${frame.image_url}`}
                  alt={`프레임 ${frame.image_id}`}
                  className="frame-image"
                  onError={(e) => {
                    console.error(`프레임 이미지 로드 실패: ${frame.image_url}`);
                    e.target.style.display = 'none';
                  }}
                />
                <div className="frame-tags">
                  {frame.persons && frame.persons.length > 0 && (
                    <span className="frame-tag person-tag">
                      👤 사람 {frame.persons.length}명
                    </span>
                  )}
                  {frame.objects && frame.objects.length > 0 && (
                    <span className="frame-tag object-tag">
                      📦 객체 {frame.objects.length}개
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default OptimalResponseRenderer;