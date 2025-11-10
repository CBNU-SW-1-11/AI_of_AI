import React, { useEffect, useMemo, useState, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Plus, EllipsisVertical, Pencil, Trash2 } from "lucide-react";

const HISTORY_KEY = "aiofai:conversations";
const MESSAGES_KEY = "aiofai:messages";

const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [items, setItems] = useState([]);
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const menuRef = useRef(null);
  const inputRef = useRef(null);

  const currentCid = useMemo(() => {
    const sp = new URLSearchParams(location.search);
    return sp.get("cid") || null;
  }, [location.search]);

  // 초기 로드
  useEffect(() => {
    loadHistory();
  }, []);

  // storage 이벤트 리스너 (다른 탭에서 발생한 storage 이벤트)
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === HISTORY_KEY) {
        loadHistory();
      }
    };
    
    // 같은 탭에서 발생한 storage 이벤트도 감지 (custom event)
    const onCustomStorage = (e) => {
      if (e.detail && e.detail.key === HISTORY_KEY) {
        loadHistory();
      }
    };
    
    window.addEventListener('storage', onStorage);
    window.addEventListener('customstorage', onCustomStorage);
    
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('customstorage', onCustomStorage);
    };
  }, []);

  // 메뉴 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (e) => {
      // 더보기 버튼 클릭은 제외
      const isEllipsisButton = e.target.closest('button[aria-label="더보기"]');
      if (isEllipsisButton) return;
      
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpenId(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 편집 모드 시 input에 포커스
  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const loadHistory = () => {
    try {
      const raw = sessionStorage.getItem(HISTORY_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      // 최신순 정렬
      parsed.sort((a, b) => b.updatedAt - a.updatedAt);
      setItems(parsed);
    } catch {
      setItems([]);
    }
  };

  const writeItems = (next) => {
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    setItems(next);
    
    // storage 이벤트 수동 발생
    window.dispatchEvent(new StorageEvent('storage', {
      key: HISTORY_KEY,
      newValue: JSON.stringify(next)
    }));
  };

  const createNewChat = (models = []) => {
    const id = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
    const newItem = { 
      id, 
      title: "새 대화", 
      updatedAt: Date.now(),
      selectedModels: models
    };
    
    const existingItems = [...items];
    const next = [newItem, ...existingItems].slice(0, 100);
    writeItems(next);
    
    // 새 대화로 이동
    navigate(`/?cid=${id}`);
  };

  const openChat = (id) => {
    if (id !== currentCid) {
      navigate(`/?cid=${id}`);
    }
  };

  const handleRename = (item) => {
    setEditingId(item.id);
    setEditingTitle(item.title);
    setMenuOpenId(null);
  };

  const handleSaveRename = (id) => {
    if (!editingTitle.trim()) {
      setEditingId(null);
      return;
    }

    const updatedItems = items.map(item => 
      item.id === id 
        ? { ...item, title: editingTitle.trim(), updatedAt: Date.now() }
        : item
    );
    
    writeItems(updatedItems);
    setEditingId(null);
    setEditingTitle("");
  };

  const handleCancelRename = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  const handleDelete = (item) => {
    if (!window.confirm(`"${item.title}" 대화를 삭제하시겠습니까?`)) {
      return;
    }

    // 히스토리에서 삭제
    const updatedItems = items.filter(i => i.id !== item.id);
    writeItems(updatedItems);

    // 메시지 데이터에서도 삭제
    try {
      const allMessages = JSON.parse(sessionStorage.getItem(MESSAGES_KEY) || '{}');
      delete allMessages[item.id];
      sessionStorage.setItem(MESSAGES_KEY, JSON.stringify(allMessages));
    } catch (error) {
      console.error('메시지 삭제 실패:', error);
    }

    setMenuOpenId(null);

    // 현재 보고 있는 대화를 삭제한 경우 새 대화 생성
    if (currentCid === item.id) {
      const newId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
      const newItem = { 
        id: newId, 
        title: "새 대화", 
        updatedAt: Date.now(),
        selectedModels: [] // 빈 배열로 초기화
      };
      const next = [newItem, ...updatedItems].slice(0, 100);
      writeItems(next);
      navigate(`/?cid=${newId}`);
    }
  };

  const handleNewChatClick = () => {
    const event = new CustomEvent('open-model-selection', {
      detail: {
        onConfirm: (models) => {
          if (!models || models.length === 0) return;
          createNewChat(models);
        }
      }
    });
    window.dispatchEvent(event);
  };

  return (
    <div
      className="w-64 border-r p-4 h-full flex-shrink-0 transition-all duration-300 overflow-y-auto"
      style={{
        background: "rgba(245, 242, 234, 0.4)",
        backdropFilter: "blur(20px)",
        borderRightColor: "rgba(139, 168, 138, 0.15)",
        position: "relative"
      }}
    >
      {/* 헤더: 최근항목 + 새 채팅 버튼 */}
      <div className="flex items-center justify-between mb-4">
        <h2
          className="text-lg font-semibold"
          style={{ color: "#2d3e2c", fontSize: "1.2rem", fontWeight: 600 }}
        >
          최근항목
        </h2>
        <button
          aria-label="새 채팅"
          onClick={handleNewChatClick}
          className="p-2 rounded-lg transition-colors"
          style={{ color: "#2d3e2c" }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(93,124,91,0.08)")}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
        >
          <Plus className="w-5 h-5" />
        </button>
      </div>

      {/* 히스토리 리스트 */}
      <div className="space-y-3" style={{ overflow: "visible", position: "relative" }}>
        {items.length === 0 ? (
          <div className="text-xs" style={{ color: "rgba(45, 62, 44, 0.5)" }}>
            최근 항목이 없습니다.
          </div>
        ) : (
          items.map((it) => {
            const isActive = currentCid === it.id;
            const isEditing = editingId === it.id;
            const isMenuOpen = menuOpenId === it.id;
            
            return (
              <div
                key={it.id}
                className={`sidebar-item p-3 rounded-lg cursor-pointer transition-all duration-400 relative ${
                  isActive ? "ring-2" : ""
                }`}
                onClick={() => !isEditing && openChat(it.id)}
                title={!isEditing ? it.title || "제목 없음" : ""}
                style={{
                  background: "rgba(255, 255, 255, 0.8)",
                  backdropFilter: "blur(10px)",
                  border: `1px solid ${isActive ? "#8ba88a" : "rgba(139, 168, 138, 0.2)"}`,
                  borderRadius: "16px",
                  boxShadow: isActive ? "0 12px 40px rgba(93, 124, 91, 0.12)" : "none",
                  overflow: "visible",
                  zIndex: isMenuOpen ? 100 : 1
                }}
              >
                <div
                  className="shine-effect absolute top-0 left-0 w-full h-full pointer-events-none"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent, rgba(139, 168, 138, 0.1), transparent)",
                    transform: "translateX(-100%)",
                    transition: "transform 0.6s ease",
                  }}
                />

                {/* 더보기 버튼 */}
                {!isEditing && (
                  <button
                    type="button"
                    aria-label="더보기"
                    className="absolute top-2 right-2 p-1.5 rounded-md hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-200 z-10"
                    onClick={(e) => {
                      e.stopPropagation();
                      setMenuOpenId(menuOpenId === it.id ? null : it.id);
                    }}
                  >
                    <EllipsisVertical className="w-4 h-4" style={{ color: '#6b7280' }} />
                  </button>
                )}

                {/* 드롭다운 메뉴 */}
                {menuOpenId === it.id && (
                  <div
                    ref={menuRef}
                    className="absolute top-10 right-2 w-44 bg-white border border-gray-200 rounded-lg shadow-xl z-50"
                    onClick={(e) => e.stopPropagation()}
                    role="menu"
                  >
                    <button
                      className="w-full px-4 py-3 text-left text-sm hover:bg-gray-50 flex items-center gap-2 rounded-t-lg"
                      onClick={() => handleRename(it)}
                      role="menuitem"
                    >
                      <Pencil className="w-4 h-4 text-gray-600" />
                      <span className="text-gray-700">이름 수정</span>
                    </button>
                    <div className="border-t border-gray-100"></div>
                    <button
                      className="w-full px-4 py-3 text-left text-sm hover:bg-red-50 flex items-center gap-2 rounded-b-lg"
                      onClick={() => handleDelete(it)}
                      role="menuitem"
                    >
                      <Trash2 className="w-4 h-4 text-red-600" />
                      <span className="text-red-600">대화 삭제</span>
                    </button>
                  </div>
                )}

                <div className="flex flex-col w-full pr-6">
                  {isEditing ? (
                    <input
                      ref={inputRef}
                      type="text"
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          handleSaveRename(it.id);
                        } else if (e.key === 'Escape') {
                          handleCancelRename();
                        }
                      }}
                      onBlur={() => handleSaveRename(it.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                      style={{ color: "#5d7c5b", fontSize: "0.95rem", fontWeight: 600 }}
                    />
                  ) : (
                    <>
                      <h3
                        className="font-medium text-sm mb-1 truncate transition-colors duration-300"
                        style={{ color: "#5d7c5b", fontSize: "0.95rem", fontWeight: 600 }}
                      >
                        {it.title || "제목 없음"}
                      </h3>
                      
                      {/* AI 모델 표시 */}
                      {it.selectedModels && it.selectedModels.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-1">
                          {it.selectedModels.map((modelId, idx) => (
                            <span
                              key={idx}
                              className="text-xs px-2 py-0.5 rounded-full"
                              style={{
                                backgroundColor: 'rgba(139, 168, 138, 0.15)',
                                color: '#5d7c5b',
                                fontSize: '0.7rem',
                                fontWeight: 500
                              }}
                            >
                              {modelId}
                            </span>
                          ))}
                        </div>
                      )}
                      
                      <p
                        className="text-xs transition-colors duration-300 truncate"
                        style={{ color: "rgba(45, 62, 44, 0.5)", fontSize: "0.8rem", lineHeight: 1.4 }}
                      >
                        {new Date(it.updatedAt).toLocaleString('ko-KR')}
                      </p>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      <style jsx>{`
        .sidebar-item:hover {
          background: rgba(255, 255, 255, 0.9) !important;
          border-color: #8ba88a !important;
          transform: translateY(-4px) scale(1.02);
          box-shadow: 0 12px 40px rgba(93, 124, 91, 0.15);
        }
        .sidebar-item:hover .shine-effect {
          transform: translateX(100%);
        }
        .sidebar-item:hover h3 {
          color: #5d7c5b !important;
        }
        .sidebar-item:hover p {
          color: rgba(45, 62, 44, 0.7) !important;
        }
      `}</style>
    </div>
  );
};

export default Sidebar;