import React from 'react';
import { X } from 'lucide-react';

const ModelSelectionModal = ({ isOpen, onClose, selectedModels, onModelSelect, onConfirm }) => {
  // 카테고리별 모델 그룹 (Gemini, Claude, Clova, GPT 순서)
  const modelGroups = {
    'Gemini': [
      { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', description: 'Google의 최고 성능 모델', price: 'expensive' },
      { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', description: 'Google의 빠른 고성능 모델', price: 'medium' },
      { id: 'gemini-2.0-flash-exp', name: 'Gemini 2.0 Flash Exp', description: 'Google의 실험 버전', price: 'expensive' },
      { id: 'gemini-2.0-flash-lite', name: 'Gemini 2.0 Flash Lite', description: 'Google의 경량 모델', price: 'cheap' },
    ],
    'Claude': [
      { id: 'claude-4-opus', name: 'Claude 4 Opus', description: 'Anthropic의 차세대 최고 성능', price: 'expensive' },
      { id: 'claude-3.7-sonnet', name: 'Claude 3.7 Sonnet', description: 'Anthropic의 고급 추론 모델', price: 'expensive' },
      { id: 'claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', description: 'Anthropic의 균형잡힌 모델', price: 'medium' },
      { id: 'claude-3.5-haiku', name: 'Claude 3.5 Haiku', description: 'Anthropic의 빠른 모델', price: 'cheap' },
      { id: 'claude-3-opus', name: 'Claude 3 Opus', description: 'Anthropic의 강력한 모델', price: 'expensive' },
    ],
    'Clova': [
      { id: 'clova-hcx-003', name: 'HCX-003', description: 'Naver의 고성능 한국어 AI', price: 'expensive' },
      { id: 'clova-hcx-dash-001', name: 'HCX-DASH-001', description: 'Naver의 빠른 한국어 AI', price: 'cheap' },
    ],
    'GPT': [
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

  const handleModelToggle = (modelId) => {
    if (selectedModels.includes(modelId)) {
      // Remove model if already selected
      if (selectedModels.length > 1) { // Ensure at least one model remains selected
        onModelSelect(selectedModels.filter(id => id !== modelId));
      }
    } else {
      // Add model if not selected and less than 3 models are currently selected
      if (selectedModels.length < 3) {
        onModelSelect([...selectedModels, modelId]);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-96 max-h-[75vh] flex flex-col relative"> 
        <div className="p-6">
          <X className="absolute top-3 right-3 w-6 h-6 cursor-pointer text-gray-500 hover:text-gray-700" onClick={onClose} />
          <h3 className="text-xl font-bold mb-2 text-left" style={{ color: '#2d3e2c' }}>AI 모델 선택</h3>
          <p className="text-sm text-gray-600 mb-0.1 text-left">최소 1개, 최대 3개의 AI 모델을 선택하세요</p>
        </div>
        
        <div className="flex-1 overflow-y-auto px-6 border-t">
          <div className="pb-4 pt-6">
            {Object.entries(modelGroups).map(([groupName, models], groupIndex) => (
              <div key={groupName} className={groupIndex > 0 ? 'mt-6' : ''}>
                {/* 그룹 제목 */}
                <h4 className="text-sm font-bold mb-3 px-1" style={{ color: '#5d7c5b' }}>
                  {groupName}
                </h4>
                
                {/* 그룹 내 모델들 */}
                <div className="space-y-2">
                  {models.map((model) => (
                    <label
                      key={model.id}
                      className={`flex items-center p-3 rounded-lg border cursor-pointer transition-all duration-200
                        ${selectedModels.includes(model.id) 
                          ? '' 
                          : 'border-gray-200'}
                        ${selectedModels.length >= 3 && !selectedModels.includes(model.id) 
                          ? 'opacity-50 cursor-not-allowed' 
                          : ''}`}
                      style={selectedModels.includes(model.id) 
                        ? { 
                            borderColor: 'rgba(139, 168, 138, 0.4)', 
                            backgroundColor: 'rgba(139, 168, 138, 0.05)' 
                          } 
                        : {}}
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
                        onChange={() => handleModelToggle(model.id)}
                        disabled={selectedModels.length >= 3 && !selectedModels.includes(model.id)}
                        className="hidden"
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span style={{ color: '#2d3e2c' }}>{model.name}</span>
                          {model.price === 'cheap' && (
                            <span className="text-xs px-2 py-0.5 rounded-full font-semibold" 
                                  style={{ backgroundColor: '#d1fae5', color: '#065f46' }}>
                              💰 저렴
                            </span>
                          )}
                          {model.price === 'expensive' && (
                            <span className="text-xs px-2 py-0.5 rounded-full font-semibold" 
                                  style={{ backgroundColor: '#fee2e2', color: '#991b1b' }}>
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
        </div>

        <div className="p-6 border-t flex justify-center">
          <button
            onClick={onClose}
            disabled={selectedModels.length === 0}
            className={`py-3 px-8 rounded-xl font-semibold transition-colors ${
              selectedModels.length === 0 
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                : 'text-white'
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