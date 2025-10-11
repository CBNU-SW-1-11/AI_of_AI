import React, { useState, useMemo } from 'react';
import { X, Sparkles } from 'lucide-react';

const ModelSelectionModal = ({ isOpen, onClose, selectedModels, onModelSelect }) => {
  // 1) 카테고리별 모델 그룹 (Gemini, Claude, Clova, GPT 순서)
  const modelGroups = {
    Gemini: [
      { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', description: 'Google의 최고 성능 모델', price: 'expensive' },
      { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', description: 'Google의 빠른 고성능 모델', price: 'medium' },
      { id: 'gemini-2.0-flash-exp', name: 'Gemini 2.0 Flash Exp', description: 'Google의 실험 버전', price: 'expensive' },
      { id: 'gemini-2.0-flash-lite', name: 'Gemini 2.0 Flash Lite', description: 'Google의 경량 모델', price: 'cheap' },
    ],
    Claude: [
      { id: 'claude-4-opus', name: 'Claude 4 Opus', description: 'Anthropic의 차세대 최고 성능', price: 'expensive' },
      { id: 'claude-3.7-sonnet', name: 'Claude 3.7 Sonnet', description: 'Anthropic의 고급 추론 모델', price: 'expensive' },
      { id: 'claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', description: 'Anthropic의 균형잡힌 모델', price: 'medium' },
      { id: 'claude-3.5-haiku', name: 'Claude 3.5 Haiku', description: 'Anthropic의 빠른 모델', price: 'cheap' },
      { id: 'claude-3-opus', name: 'Claude 3 Opus', description: 'Anthropic의 강력한 모델', price: 'expensive' },
    ],
    Clova: [
      { id: 'clova-hcx-003', name: 'HCX-003', description: 'Naver의 고성능 한국어 AI', price: 'expensive' },
      { id: 'clova-hcx-dash-001', name: 'HCX-DASH-001', description: 'Naver의 빠른 한국어 AI', price: 'cheap' },
    ],
    GPT: [
      { id: 'gpt-5', name: 'GPT-5', description: 'OpenAI의 차세대 AI', price: 'expensive' },
      { id: 'gpt-5-mini', name: 'GPT-5 Mini', description: 'GPT-5의 경량 버전', price: 'medium' },
      { id: 'gpt-4.1', name: 'GPT-4.1', description: 'OpenAI의 개선된 GPT-4', price: 'expensive' },
      { id: 'gpt-4.1-mini', name: 'GPT-4.1 Mini', description: 'GPT-4.1 경량 버전', price: 'medium' },
      { id: 'gpt-4o', name: 'GPT-4o', description: 'OpenAI의 옴니 모델', price: 'expensive' },
      { id: 'gpt-4o-mini', name: 'GPT-4o Mini', description: '경량화된 고성능 모델', price: 'cheap' },
      { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', description: 'GPT-4 터보 버전', price: 'expensive' },
      { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', description: '빠르고 효율적인 모델', price: 'cheap' },
    ],
  };

  // 2) 추천 카테고리별 3개 모델 세트
  const recommendedCategories = {
    '이미지 분석': ['gpt-4o', 'gemini-2.5-flash', 'claude-4-opus'],
    '문서 분석': ['claude-4-opus', 'gpt-4.1', 'clova-hcx-003'],
    '코드 작성': ['gpt-5', 'claude-3.7-sonnet', 'gemini-2.5-pro'],
    '글쓰기 / 창작': ['claude-3.7-sonnet', 'gpt-5', 'gemini-2.5-flash'],
    '속도 / 실시간': ['gemini-2.5-flash', 'gpt-4o-mini', 'claude-3.5-haiku'],
    '비용 효율': ['gpt-4o-mini', 'gemini-2.0-flash-lite', 'claude-3.5-haiku'],
    '영상분석': ['gpt-4o', 'claude-3.7-sonnet', 'gemini-2.5-flash'],
  };

  // 3) 모델 id → 표시 이름 매핑 (modelGroups 선언 이후)
  const modelNameById = useMemo(() => {
    const map = {};
    Object.values(modelGroups).flat().forEach((m) => (map[m.id] = m.name));
    return map;
  }, []);

  // 4) 탭/선택 상태
  const [activeTab, setActiveTab] = useState('category'); // 'category' | 'manual'
  const [selectedCategory, setSelectedCategory] = useState(null);

  // 5) 개별 선택 토글 (최소 1개, 최대 3개)
  const handleModelToggle = (modelId) => {
    if (selectedModels.includes(modelId)) {
      if (selectedModels.length > 1) onModelSelect(selectedModels.filter((id) => id !== modelId));
    } else {
      if (selectedModels.length < 3) onModelSelect([...selectedModels, modelId]);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      {/* 폭: 한 줄로 보기 좋은 정도로만 확장 */}
      <div className="bg-white rounded-lg w-[490px] max-w-[95vw] max-h-[75vh] flex flex-col relative">
        <div className="p-6">
          <X className="absolute top-3 right-3 w-6 h-6 cursor-pointer text-gray-500 hover:text-gray-700" onClick={onClose} />
          <h3 className="text-xl font-bold mb-2 text-left" style={{ color: '#2d3e2c' }}>AI 모델 선택</h3>
          <p className="text-sm text-gray-600 mb-0.1 text-left">최소 1개, 최대 3개의 AI 모델을 선택하세요</p>
        </div>

        <div className="flex-1 overflow-y-auto px-6 border-t">
          {/* 탭 버튼 */}
          <div className="pt-4 pb-3">
            <div className="flex gap-2 bg-gray-100 p-1 rounded-lg">
              <button
                onClick={() => setActiveTab('category')}
                className={`flex-1 py-2 px-4 rounded-md font-semibold transition-all ${
                  activeTab === 'category' ? 'bg-white shadow-sm' : 'text-gray-600'
                }`}
                style={activeTab === 'category' ? { color: '#2d3e2c' } : {}}
              >
                <Sparkles className="inline w-4 h-4 mr-1" />
                추천 선택
              </button>
              <button
                onClick={() => setActiveTab('manual')}
                className={`flex-1 py-2 px-4 rounded-md font-semibold transition-all ${
                  activeTab === 'manual' ? 'bg-white shadow-sm' : 'text-gray-600'
                }`}
                style={activeTab === 'manual' ? { color: '#2d3e2c' } : {}}
              >
                직접 선택
              </button>
            </div>
          </div>

          {/* 콘텐츠 */}
          {activeTab === 'category' ? (
            // ===== 추천선택 (직접선택과 같은 색/인디케이터) =====
            <div className="pb-4">
              <p className="text-xs text-gray-600 mb-3">
                카테고리를 선택하면 해당 카테고리의 3개 모델이 자동으로 선택됩니다.
              </p>
              <div className="space-y-2">
                {Object.entries(recommendedCategories).map(([cat, ids]) => {
                  const isSelected = selectedCategory === cat;
                  return (
                    <div
                      key={cat}
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        onModelSelect(ids);
                        setSelectedCategory(cat);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          onModelSelect(ids);
                          setSelectedCategory(cat);
                        }
                      }}
                      className={`flex items-center p-3 rounded-lg border cursor-pointer transition-all duration-200
                        ${isSelected ? '' : 'border-gray-200'}`}
                      style={
                        isSelected
                          ? { borderColor: 'rgba(139, 168, 138, 0.4)', backgroundColor: 'rgba(139, 168, 138, 0.05)' }
                          : {}
                      }
                      onMouseEnter={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.backgroundColor = 'rgba(139, 168, 138, 0.05)';
                          e.currentTarget.style.borderColor = 'rgba(139, 168, 138, 0.4)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.backgroundColor = 'transparent';
                          e.currentTarget.style.borderColor = '#d1d5db';
                        }
                      }}
                    >
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <div className="font-semibold" style={{ color: '#2d3e2c' }}>{cat}</div>

                          {/* 오른쪽 동그라미 인디케이터 (직접선택과 동일) */}
                          <div className="ml-2">
                            {isSelected && (
                              <div
                                className="w-4 h-4 rounded-full flex items-center justify-center"
                                style={{ background: '#5d7c5b' }}
                              >
                                <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* 칩: 한 줄 유지(넘치면 가로 스크롤), 메달 이모지 없음 */}
                        <div className="mt-2 flex gap-2 flex-nowrap overflow-x-auto">
                          {ids.map((id) => (
                            <span
                              key={id}
                              className="text-xs px-2 py-1 rounded-full border"
                              style={{ borderColor: '#8ba88a', color: '#2d3e2c', whiteSpace: 'nowrap' }}
                            >
                              {modelNameById[id] || id}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            // ===== 직접선택 (요청하신 색상 그대로) =====
            <div className="pb-4 pt-6">
              {Object.entries(modelGroups).map(([groupName, models], groupIndex) => (
                <div key={groupName} className={groupIndex > 0 ? 'mt-6' : ''}>
                  {/* 그룹 제목 */}
                  <h4 className="text-sm font-bold mb-3 px-1" style={{ color: '#5d7c5b' }}>{groupName}</h4>

                  {/* 그룹 내 모델들 */}
                  <div className="space-y-2">
                    {models.map((model) => (
                      <label
                        key={model.id}
                        className={`flex items-center p-3 rounded-lg border cursor-pointer transition-all duration-200
                          ${selectedModels.includes(model.id) ? '' : 'border-gray-200'}
                          ${selectedModels.length >= 3 && !selectedModels.includes(model.id) ? 'opacity-50 cursor-not-allowed' : ''}`}
                        style={
                          selectedModels.includes(model.id)
                            ? { borderColor: 'rgba(139, 168, 138, 0.4)', backgroundColor: 'rgba(139, 168, 138, 0.05)' }
                            : {}
                        }
                        onMouseEnter={(e) => {
                          if (!selectedModels.includes(model.id) && selectedModels.length < 3) {
                            e.currentTarget.style.backgroundColor = 'rgba(139, 168, 138, 0.05)';
                            e.currentTarget.style.borderColor = 'rgba(139, 168, 138, 0.4)';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!selectedModels.includes(model.id)) {
                            e.currentTarget.style.backgroundColor = 'transparent';
                            e.currentTarget.style.borderColor = '#d1d5db';
                          }
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedModels.includes(model.id)}
                          onChange={() => {
                            if (selectedModels.includes(model.id)) {
                              if (selectedModels.length > 1) {
                                onModelSelect(selectedModels.filter((id) => id !== model.id));
                              }
                            } else {
                              if (selectedModels.length < 3) {
                                onModelSelect([...selectedModels, model.id]);
                              }
                            }
                          }}
                          disabled={selectedModels.length >= 3 && !selectedModels.includes(model.id)}
                          className="hidden"
                        />
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span style={{ color: '#2d3e2c' }}>{model.name}</span>
                            {model.price === 'cheap' && (
                              <span className="text-xs px-2 py-0.5 rounded-full font-semibold" style={{ backgroundColor: '#d1fae5', color: '#065f46' }}>
                                💰 저렴
                              </span>
                            )}
                            {model.price === 'expensive' && (
                              <span className="text-xs px-2 py-0.5 rounded-full font-semibold" style={{ backgroundColor: '#fee2e2', color: '#991b1b' }}>
                                💎 고가
                              </span>
                            )}
                          </div>
                          <div className="text-xs mt-1" style={{ color: '#6b7280' }}>{model.description}</div>
                        </div>

                        {selectedModels.includes(model.id) && (
                          <div
                            className="w-4 h-4 rounded-full flex items-center justify-center ml-2"
                            style={{ background: '#5d7c5b' }}
                          >
                            <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                          </div>
                        )}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-6 border-t flex justify-center">
          <button
            onClick={onClose}
            disabled={selectedModels.length === 0}
            className={`py-3 px-8 rounded-xl font-semibold transition-colors ${
              selectedModels.length === 0 ? 'bg-gray-300 text-gray-500 cursor-not-allowed' : 'text-white'
            }`}
            style={selectedModels.length > 0 ? { backgroundColor: '#8ba88a' } : {}}
            onMouseEnter={(e) => selectedModels.length > 0 && (e.target.style.backgroundColor = '#5d7c5b')}
            onMouseLeave={(e) => selectedModels.length > 0 && (e.target.style.backgroundColor = '#8ba88a')}
          >
            확인
          </button>
        </div>
      </div>
    </div>
  );
};

export default ModelSelectionModal;